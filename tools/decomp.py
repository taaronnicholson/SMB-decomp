#!/usr/bin/env python3
"""Trace-based 6502 disassembler for the UxROM image -> ca65 sources.

Run from anywhere:  python3 -I tools/decomp.py
Reads rom/game.nes + tools/hints.txt, writes src/bankN.s and src/fixed.s
"""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dis6502 import OPS, LEN

rom = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read()
NB = rom[4]; FIXED = NB - 1
PRG = [rom[16 + i * 16384:16 + (i + 1) * 16384] for i in range(NB)]
BANKSW = 0xC90D                    # LDA #n / JSR BANKSW
BANKSW_DYN = {0xC917}              # bank taken from RAM: context unknown afterwards

def byte(p, a): return PRG[p][a & 0x3FFF]
def phys(pc, cb): return FIXED if pc >= 0xC000 else cb
def bn(t): return FIXED if t == 'f' else int(t)

# ---- hints ----------------------------------------------------------------
entries, words_tab, lohi_tab, names, datas = [], [], [], {}, []
ramnames = {}
for ln in open(os.path.join(HERE, 'hints.txt')):
    t = ln.split(';')[0].split()
    if not t: continue
    if t[0] == 'entry':   # entry <bank|f> <addr> [curbank|-]
        cb = int(t[3]) if len(t) > 3 and t[3] != '-' else (None if t[1] == 'f' else int(t[1]))
        entries.append((int(t[2], 16), cb))
    elif t[0] == 'words': # words <bank|f> <addr> <n> [tgtbank]  : n code pointers (lo,hi pairs)
        words_tab.append((bn(t[1]), int(t[2], 16), int(t[3]), int(t[4]) if len(t) > 4 else None))
    elif t[0] == 'lohi':  # lohi <bank|f> <lo> <hi> <n> [tgtbank|-] [adj]
        lohi_tab.append((bn(t[1]), int(t[2], 16), int(t[3], 16), int(t[4]),
                         int(t[5]) if len(t) > 5 and t[5] != '-' else None, int(t[6]) if len(t) > 6 else 0))
    elif t[0] == 'ram':   # ram <addr> <name>
        ramnames[int(t[1], 16)] = t[2]
    elif t[0] == 'name':  # name <bank|f> <addr> <label>
        names[(bn(t[1]), int(t[2], 16))] = t[3]

# ---- tracing ---------------------------------------------------------------
instr = {}                          # (p, pc) -> (opcode, len)
ctx = collections.defaultdict(set)  # (p, pc) -> set of cb seen
seen, queue = set(), collections.deque()
unresolved, bad = [], []

FARCALL = 0xCEEE                   # A=hi, X=lo, Y=bank: calls $hilo in bank Y, restores bank
WR_A = {'LDA','PLA','TXA','TYA','ADC','SBC','AND','ORA','EOR'}
WR_X = {'LDX','TAX','TSX','INX','DEX'}
WR_Y = {'LDY','TAY','INY','DEY'}

def push(pc, cb, regs=(None, None, None), why=''):
    if pc < 0x8000: return
    if pc < 0xC000 and cb is None:
        unresolved.append((pc, why)); return
    st = (pc, cb, regs)
    if st not in seen:
        seen.add(st); queue.append(st)

for i in range(3):
    push(byte(FIXED, 0x3FFA + 2 * i) | byte(FIXED, 0x3FFB + 2 * i) << 8, None, why='vector')
for a, cb in entries: push(a, cb, why='entry')
for b, a, n, tb in words_tab:
    for i in range(n):
        t = byte(b, a + 2 * i) | byte(b, a + 2 * i + 1) << 8
        push(t, tb if tb is not None else (None if b == FIXED else b), why=f'words {b}:{a:04X}')
for b, lo, hi, n, tb, adj in lohi_tab:
    for i in range(n):
        t = (byte(b, lo + i) | byte(b, hi + i) << 8) + adj
        push(t, tb if tb is not None else (None if b == FIXED else b), why=f'lohi {b}:{lo:04X}')

farcalls = set()
while queue:
    pc, cb, regs = queue.popleft()
    ra, rx, ry = regs
    p = phys(pc, cb)
    o = byte(p, pc)
    if o not in OPS: bad.append((p, pc, o)); continue
    mn, m = OPS[o]; l = LEN[m]
    instr[(p, pc)] = (o, l); ctx[(p, pc)].add(cb)
    val = int.from_bytes(bytes(byte(p, pc + 1 + k) for k in range(l - 1)), 'little') if l > 1 else 0
    nxt = pc + l
    why = f'{mn}@{p}:{pc:04X}'
    # register constant tracking
    na, nx, ny = ra, rx, ry
    if mn in WR_A or (m == 'acc'): na = val if (mn == 'LDA' and m == 'imm') else None
    if mn in WR_X: nx = val if (mn == 'LDX' and m == 'imm') else None
    if mn in WR_Y: ny = val if (mn == 'LDY' and m == 'imm') else None
    if mn == 'TAX': nx = ra
    if mn == 'TAY': ny = ra
    if mn == 'TXA': na = rx
    if mn == 'TYA': na = ry
    nr = (na, nx, ny)
    if m == 'rel':
        push(nxt + (val - 256 if val > 127 else val), cb, nr, why); push(nxt, cb, nr, why)
    elif mn == 'JSR':
        ncb = cb
        if val == BANKSW: ncb = ra
        elif val in BANKSW_DYN: ncb = None
        elif val == FARCALL:
            if None not in regs and ry < NB and (ra << 8 | rx) >= 0x8000:
                tgt = ra << 8 | rx
                farcalls.add((tgt, ry))
                push(tgt, ry if tgt < 0xC000 else None, why=why + ' farcall')
            else: unresolved.append((pc, 'farcall-dyn'))
        else: push(val, cb, why=why)
        if ncb is not None or nxt >= 0xC000: push(nxt, ncb, (None, None, None), why)
    elif mn == 'JMP' and m == 'abs': push(val, cb, nr, why)
    elif mn in ('RTS', 'RTI', 'BRK') or (mn == 'JMP' and m == 'ind'): pass
    else: push(nxt, cb, nr, why)

# ---- speculative code discovery -------------------------------------------------
# Decode from plausible seeds; accept a block only if every path decodes cleanly to a terminator.
TERM = {'RTS', 'RTI'}
spec_bytes = set()

def spec_try(p, start, cb):
    base = 0xC000 if p == FIXED else 0x8000
    got = {}; work = [start]; ncalls = []
    while work:
        pc = work.pop()
        while True:
            if pc < base or pc >= base + 0x4000: return None
            if (p, pc) in instr or pc in got: break
            if (p, pc) in code_bytes: return None            # lands inside known instruction
            o = byte(p, pc)
            if o not in OPS or o == 0x00: return None
            mn, m = OPS[o]; l = LEN[m]
            if pc + l > base + 0x4000: return None
            if any((p, pc + k) in code_bytes or (p, pc + k) in spec_bytes for k in range(l)): return None
            val = int.from_bytes(bytes(byte(p, pc + 1 + k) for k in range(l - 1)), 'little') if l > 1 else 0
            if mn in ('STA', 'STX', 'STY') and m == 'abs' and val >= 0x8000: return None
            got[pc] = (o, l)
            if m == 'rel':
                t = pc + 2 + (val - 256 if val > 127 else val)
                if t == pc: return None
                work.append(t)
            elif mn == 'JSR':
                if val < 0x8000 and val not in (): return None
                ncalls.append(val)
            elif mn == 'JMP' and m == 'abs':
                if val < 0x8000: return None
                ncalls.append(val); break
            elif mn == 'JMP' or mn in TERM: break
            pc += l
    first = got[start][0]
    if OPS[first][0] in TERM or len(got) < 3: return None
    return got, ncalls

def spec_commit(p, got, cb):
    for pc, (o, l) in got.items():
        instr[(p, pc)] = (o, l); ctx[(p, pc)].add(cb)
        for k in range(l): code_bytes.add((p, pc + k)); spec_bytes.add((p, pc + k))

code_bytes = set()
for (p, a), (o, l) in instr.items():
    for k in range(l): code_bytes.add((p, a + k))

if not os.environ.get('NOSPEC'):
    changed = True
    while changed:
        changed = False
        seeds = []
        for (p, a), (o, l) in list(instr.items()):
            mn, m = OPS[o]; base = 0xC000 if p == FIXED else 0x8000
            if mn in TERM or (mn == 'JMP') :
                n = a + l
                if base <= n < base + 0x4000 and (p, n) not in code_bytes: seeds.append((p, n))
            val = int.from_bytes(bytes(byte(p, a + 1 + k) for k in range(l - 1)), 'little') if l > 1 else 0
            if mn in ('JSR', 'JMP') and m == 'abs' and val >= 0x8000:
                tp = FIXED if val >= 0xC000 else (p if p != FIXED else None)
                if tp is not None and (tp, val) not in code_bytes: seeds.append((tp, val))
                if tp is None:                     # fixed code -> switched space, bank unknown: try all
                    for q in range(FIXED):
                        if (q, val) not in code_bytes: seeds.append((q, val, 6))
        for sd in sorted(set(seeds)):
            p, a = sd[0], sd[1]; need = sd[2] if len(sd) > 2 else 3
            if (p, a) in code_bytes: continue
            r = spec_try(p, a, None if p == FIXED else p)
            if r and len(r[0]) >= need:
                spec_commit(p, r[0], None if p == FIXED else p); changed = True

# ---- classify bytes ----------------------------------------------------------
starts = set(instr)

def res_bank(a, p, pc):
    """physical bank an absolute address a refers to, from the instruction at (p,pc)"""
    if a >= 0xC000: return FIXED
    if a < 0x8000: return None
    if p != FIXED: return p
    c = ctx[(p, pc)]
    return next(iter(c)) if len(c) == 1 and None not in c else None

labels = {}   # (p,a) -> name
def want(p, a):
    if p is None: return None
    if (p, a) in code_bytes and (p, a) not in starts: return None   # mid-instruction
    labels.setdefault((p, a), names.get((p, a), (f'F_{a:04X}' if p == FIXED else f'B{p}_{a:04X}')))
    return labels[(p, a)]

# ---- symbols for hardware ------------------------------------------------------
HW = {0x2000:'PPUCTRL',0x2001:'PPUMASK',0x2002:'PPUSTATUS',0x2003:'OAMADDR',0x2004:'OAMDATA',
      0x2005:'PPUSCROLL',0x2006:'PPUADDR',0x2007:'PPUDATA',0x4014:'OAMDMA',0x4015:'SND_CHN',
      0x4016:'JOY1',0x4017:'JOY2'}
for i, n in enumerate(['SQ1_VOL','SQ1_SWEEP','SQ1_LO','SQ1_HI','SQ2_VOL','SQ2_SWEEP','SQ2_LO','SQ2_HI',
                       'TRI_LINEAR','APU_4009','TRI_LO','TRI_HI','NOISE_VOL','APU_400D','NOISE_LO','NOISE_HI',
                       'DMC_FREQ','DMC_RAW','DMC_START','DMC_LEN']):
    HW[0x4000 + i] = n

def fmt_instr(p, pc):
    o, l = instr[(p, pc)]; mn, m = OPS[o]
    val = int.from_bytes(bytes(byte(p, pc + 1 + k) for k in range(l - 1)), 'little') if l > 1 else 0
    def sym(a):
        if a in HW: return HW[a]
        if a in ramnames: return ramnames[a]
        b = res_bank(a, p, pc)
        if b is not None:
            n = want(b, a)
            if n: return n
        return f'${a:04X}'
    if m in ('imp',): return mn
    if m == 'acc': return f'{mn} a'
    if m == 'imm': return f'{mn} #${val:02X}'
    if m == 'rel':
        t = pc + 2 + (val - 256 if val > 127 else val)
        return f'{mn} {want(p, t) or "$%04X" % t}'
    if m in ('zp', 'zpx', 'zpy', 'izx', 'izy'):
        s = ramnames.get(val, f'${val:02X}')
        return {'zp': f'{mn} {s}', 'zpx': f'{mn} {s},x', 'zpy': f'{mn} {s},y',
                'izx': f'{mn} ({s},x)', 'izy': f'{mn} ({s}),y'}[m]
    if m == 'ind': return f'{mn} (${val:04X})'
    s = sym(val)
    if val < 0x100: s = f'a:{s}'
    return {'abs': f'{mn} {s}', 'abx': f'{mn} {s},x', 'aby': f'{mn} {s},y'}[m]

# word tables of code pointers (from hints) get .word emission
word_cells = {}   # (p, addr) -> label string for a word starting there
for b, a, n, tb in words_tab:
    for i in range(n):
        t = byte(b, a + 2 * i) | byte(b, a + 2 * i + 1) << 8
        tbk = tb if tb is not None else (FIXED if t >= 0xC000 else b if b != FIXED else None)
        if t >= 0xC000: tbk = FIXED
        nm = want(tbk, t) if tbk is not None else None
        if nm: word_cells[(b, a + 2 * i)] = nm
# lo/hi tables: emit as .byte <label / .byte >label
lo_cells = {}
for b, lo, hi, n, tb, adj in lohi_tab:
    for i in range(n):
        t = (byte(b, lo + i) | byte(b, hi + i) << 8) + adj
        tbk = FIXED if t >= 0xC000 else (tb if tb is not None else (b if b != FIXED else None))
        nm = want(tbk, t) if tbk is not None else None
        if nm:
            lo_cells[(b, lo + i)] = ('<', nm, adj); lo_cells[(b, hi + i)] = ('>', nm, adj)

# ---- emit -------------------------------------------------------------------------
def emit_bank(p):
    base = 0xC000 if p == FIXED else 0x8000
    # first pass formats instructions (this populates labels)
    text = {}
    for a in range(base, base + 0x4000):
        if (p, a) in instr: text[a] = fmt_instr(p, a)
    out = []; a = base
    while a < base + 0x4000:
        lab = [labels[(p, a)]] if (p, a) in labels else []
        for x in lab: out.append(f'{x}:')
        if a in text:
            out.append('    ' + text[a]); a += instr[(p, a)][1]; continue
        if (p, a) in word_cells:
            if (p, a + 1) in labels:   # a label points at the high byte: split the word
                out.append(f'    .byte <{word_cells[(p, a)]}'); out.append(f'{labels[(p, a + 1)]}:')
                out.append(f'    .byte >{word_cells[(p, a)]}')
            else: out.append(f'    .word {word_cells[(p, a)]}')
            a += 2; continue
        if (p, a) in lo_cells:
            k, nm, adj = lo_cells[(p, a)]
            out.append(f'    .byte {k}({nm}{"-%d" % -adj if adj < 0 else "+%d" % adj if adj else ""})'); a += 1; continue
        # data run until next label / instr / special cell
        run = []
        while a < base + 0x4000 and len(run) < 16 and (run == [] or ((p, a) not in labels and a not in text
                                   and (p, a) not in word_cells and (p, a) not in lo_cells)):
            run.append(byte(p, a)); a += 1
        out.append('    .byte ' + ','.join(f'${x:02X}' for x in run))
    return out

os.makedirs(os.path.join(ROOT, 'src'), exist_ok=True)
# two rounds so labels created by later banks (cross refs) appear in earlier outputs
for _ in range(2):
    banks = {p: emit_bank(p) for p in range(NB)}
for p in range(NB):
    name = 'fixed' if p == FIXED else f'bank{p}'
    seg = 'FIXED' if p == FIXED else f'BANK{p}'
    with open(os.path.join(ROOT, 'src', name + '.s'), 'w') as f:
        f.write(f'; {name}: PRG bank {p} (${0xC000 if p == FIXED else 0x8000:04X}-${0xFFFF if p == FIXED else 0xBFFF:04X})\n')
        f.write('; generated by tools/decomp.py from rom/game.nes\n\n')
        f.write(f'.segment "{seg}"\n\n')
        f.write('\n'.join(banks[p]) + '\n')

with open(os.path.join(ROOT, 'src', 'hardware.inc'), 'w') as f:
    f.write('; NES hardware registers\n')
    for a, n in sorted(HW.items()): f.write(f'{n} = ${a:04X}\n')
    f.write('\n; RAM (names inferred from usage)\n')
    for a, n in sorted(ramnames.items()): f.write(f'{n} = ${a:04X}\n')

ncode = len(code_bytes)
print(f'speculative code bytes: {len(spec_bytes)}')
print(f'code bytes: {ncode} of {NB*16384} ({100*ncode/(NB*16384):.1f}%)')
for p in range(NB):
    c = sum(1 for k in code_bytes if k[0] == p)
    print(f'  bank {p}: {c} code bytes ({100*c/16384:.1f}%)')
print('invalid opcodes reached:', len(bad), bad[:10])
ur = collections.Counter((a, w.split('@')[0]) for a, w in unresolved)
print('far calls resolved:', len(farcalls))
print('unresolved targets:', len(unresolved))
for (a, w), n in sorted(ur.items())[:60]: print('   ', f'{a:04X}', w)

if os.environ.get('MAP'):
    for p in range(NB):
        base = 0xC000 if p == FIXED else 0x8000
        runs = []; a = base
        while a < base + 0x4000:
            if (p, a) in code_bytes: a += 1; continue
            s0 = a
            while a < base + 0x4000 and (p, a) not in code_bytes: a += 1
            runs.append((s0, a))
        print(f'bank {p} data/unreached runs:', ' '.join(f'{s:04X}-{e-1:04X}({e-s})' for s, e in runs if e - s >= 8))
