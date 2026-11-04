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
blob_tab = []
blob_bytes = set()
blob_start = {}
text_tab = []
refexpr = {}
dlohi_tab = []
stream_tab = []
struct_tab = []
refbank = {}
dwords_tab = []
import glob
_hint_lines = [ln for f in sorted(glob.glob(os.path.join(HERE, 'hints*.txt'))) for ln in open(f)]
for ln in _hint_lines:
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
    elif t[0] == 'dwords':  # dwords <bank> <addr> <n>  : n pointers to DATA in the same bank
        dwords_tab.append((bn(t[1]), int(t[2], 16), int(t[3])))
    elif t[0] == 'refbank':  # refbank <addr> <bank> : fixed-code operands equal to addr refer to this bank
        refbank[int(t[1], 16)] = int(t[2])
    elif t[0] == 'struct':  # struct <bank> <addr> <n> <fmt>  : n rows; fmt letters w=.word b=.byte
        struct_tab.append((bn(t[1]), int(t[2], 16), int(t[3]), t[4]))
    elif t[0] == 'stream':  # stream <bank> <addr> <len> : sound bytecode, one command per line
        stream_tab.append((bn(t[1]), int(t[2], 16), int(t[3])))
    elif t[0] == 'dlohi':   # dlohi <bank> <lo> <hi> <n> : split lo/hi tables of pointers to DATA (not traced)
        dlohi_tab.append((bn(t[1]), int(t[2], 16), int(t[3], 16), int(t[4])))
    elif t[0] == 'refexpr':  # refexpr <addr> <bank> <base> <off> : operand addr -> label(base)+off
        refexpr[int(t[1], 16)] = (int(t[2]), int(t[3], 16), int(t[4]))
    elif t[0] == 'text':    # text <bank> <addr> <len> [rev] : ASCII string (rev = stored reversed)
        text_tab.append((bn(t[1]), int(t[2], 16), int(t[3]), len(t) > 4 and t[4] == 'rev'))
    elif t[0] == 'blob':    # blob <bank> <addr> <len> <name> [comment...] : labelled data block, never code
        blob_tab.append((bn(t[1]), int(t[2], 16), int(t[3]), t[4], ' '.join(t[5:])))
    elif t[0] == 'ram':   # ram <addr> <name>
        ramnames[int(t[1], 16)] = t[2]
    elif t[0] == 'name':  # name <bank|f> <addr> <label>
        names[(bn(t[1]), int(t[2], 16))] = t[3]

for _b, _a, _n, _nm, _cm in blob_tab:
    names[(_b, _a)] = _nm; blob_start[(_b, _a)] = f'{_nm}: {_cm}' if _cm else _nm
    for _k in range(_n): blob_bytes.add((_b, _a + _k))

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
        if val == BANKSW or val == 0xC919: ncb = ra      # SwitchBank / SwitchBankKeepX
        elif val in BANKSW_DYN: ncb = None
        elif val == FARCALL:
            if None not in regs and ry < NB and (ra << 8 | rx) >= 0x8000:
                tgt = ra << 8 | rx
                farcalls.add((tgt, ry))
                push(tgt, ry if tgt < 0xC000 else None, why=why + ' farcall')
            else: unresolved.append((pc, 'farcall-dyn'))
        else: push(val, cb, why=why)
        if ncb is not None or nxt >= 0xC000: push(nxt, ncb, (None, None, None), why)
    elif mn == 'JMP' and m == 'abs':
        if val == FARCALL:                                   # tail-called far call: A=hi X=lo Y=bank
            if None not in regs and ry < NB and (ra << 8 | rx) >= 0x8000:
                tgt = ra << 8 | rx
                farcalls.add((tgt, ry)); push(tgt, ry if tgt < 0xC000 else None, why=why + ' farcall')
            else: unresolved.append((pc, 'farcall-dyn'))
        else: push(val, cb, nr, why)
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
            if any((p, pc + k) in code_bytes or (p, pc + k) in spec_bytes or (p, pc + k) in blob_bytes for k in range(l)): return None
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
        # pointer-table seeds: runs of >=4 words in data whose targets mostly decode as code
        if not os.environ.get('NOTAB'):
            for p in range(NB):
                base = 0xC000 if p == FIXED else 0x8000
                lo_, hi_ = (0xC000, 0x10000) if p == FIXED else (0x8000, 0xC000)
                for adj in (0, 1):
                    a = base
                    while a < base + 0x4000 - 1:
                        run = []; b = a
                        while b < base + 0x4000 - 1 and (p, b) not in code_bytes and (p, b + 1) not in code_bytes:
                            t = (byte(p, b) | byte(p, b + 1) << 8) + adj
                            if lo_ <= t < hi_ or (p != FIXED and 0xC000 <= t < 0x10000): run.append(t); b += 2
                            else: break
                        if len(run) >= 4:
                            ok = []
                            for t in run:
                                tp = FIXED if t >= 0xC000 else p
                                if (tp, t) in code_bytes: ok.append((tp, t)); continue
                                r = spec_try(tp, t, None if tp == FIXED else tp)
                                if r and len(r[0]) >= 4: ok.append((tp, t))
                            if len(ok) * 4 >= len(run) * 3:
                                for tp, t in ok: seeds.append((tp, t))
                        a = b if run else a + 1
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
    if p == FIXED and a in refbank: return refbank[a]
    if p != FIXED: return p
    c = ctx[(p, pc)]
    return next(iter(c)) if len(c) == 1 and None not in c else None

labels = {}   # (p,a) -> name
badlabels = set()
def want(p, a):
    if p is None or (p, a) in badlabels: return None
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

autoram = set()
def ramname(a):
    if a in ramnames: return ramnames[a]
    autoram.add(a)
    return f'zp_{a:02X}' if a < 0x100 else f'ram_{a:04X}'

def fmt_instr(p, pc):
    o, l = instr[(p, pc)]; mn, m = OPS[o]
    val = int.from_bytes(bytes(byte(p, pc + 1 + k) for k in range(l - 1)), 'little') if l > 1 else 0
    def sym(a):
        if a in HW: return HW[a]
        if a in refexpr and p == FIXED:
            rb, base, off = refexpr[a]; nm = want(rb, base)
            if nm: return f'{nm}{off:+d}'
        if a < 0x2000 or 0x6000 <= a < 0x7FFF: return ramname(a)
        b = res_bank(a, p, pc)
        if b is not None:
            if (b, a - 1) in word_cells and (b, a) not in labels:   # high byte of a pointer word
                return f'{want(b, a - 1)}+1'
            n = want(b, a)
            if n: return n
        return f'${a:04X}'
    if m in ('imp',): return mn
    if m == 'acc': return f'{mn} a'
    if m == 'imm': return f'{mn} #${val:02X}'
    if m == 'rel':
        t = pc + 2 + (val - 256 if val > 127 else val)
        nm = want(p, t)
        if not nm: return f'.byte ${o:02X},${val:02X}   ; {mn} $%04X (target not an instruction start)' % t
        return f'{mn} {nm}'
    if m in ('zp', 'zpx', 'zpy', 'izx', 'izy'):
        s = ramname(val)
        return {'zp': f'{mn} {s}', 'zpx': f'{mn} {s},x', 'zpy': f'{mn} {s},y',
                'izx': f'{mn} ({s},x)', 'izy': f'{mn} ({s}),y'}[m]
    if m == 'ind': return f'{mn} ({ramname(val) if val < 0x2000 else "$%04X" % val})'
    s = sym(val)
    if val < 0x100: s = f'a:{s}'
    return {'abs': f'{mn} {s}', 'abx': f'{mn} {s},x', 'aby': f'{mn} {s},y'}[m]

# auto-detect tables of code pointers sitting in data: >=4 consecutive words that each
# point at a known instruction start (same bank, or fixed bank)
auto_tables = []
for p in range(NB):
    base = 0xC000 if p == FIXED else 0x8000
    a = base
    while a < base + 0x4000 - 1:
        run = []
        b = a
        while b < base + 0x4000 - 1 and (p, b) not in code_bytes and (p, b + 1) not in code_bytes:
            t = byte(p, b) | byte(p, b + 1) << 8
            tp = FIXED if t >= 0xC000 else (p if p != FIXED else None)
            if tp is not None and t >= 0x8000 and (tp, t) in starts: run.append((b, t, tp)); b += 2
            else: break
        same = sum(1 for _b, _t, tp in run if tp == p)
        if len(run) >= 4 and same * 2 >= len(run):      # most targets must lie in the table's own bank
            auto_tables.append((p, a, run)); a = b
        else: a += 1
# word tables of code pointers (from hints) get .word emission
word_cells = {}   # (p, addr) -> label string for a word starting there
for b, a, n, tb in words_tab:
    for i in range(n):
        t = byte(b, a + 2 * i) | byte(b, a + 2 * i + 1) << 8
        tbk = tb if tb is not None else (FIXED if t >= 0xC000 else b if b != FIXED else None)
        if t >= 0xC000: tbk = FIXED
        nm = want(tbk, t) if tbk is not None else None
        if nm: word_cells[(b, a + 2 * i)] = nm
for p, a, run in auto_tables:
    for b, t, tp in run:
        nm = want(tp, t)
        if nm: word_cells[(p, b)] = nm
for b, a, n in dwords_tab:
    for i in range(n):
        t = byte(b, a + 2 * i) | byte(b, a + 2 * i + 1) << 8
        tp = FIXED if t >= 0xC000 else b
        nm = want(tp, t)
        if nm: word_cells[(b, a + 2 * i)] = nm
lo_cells = {}
for b, lo, hi, n in dlohi_tab:
    for i in range(n):
        t = byte(b, lo + i) | byte(b, hi + i) << 8
        nm = want(FIXED if t >= 0xC000 else b, t)
        if nm: lo_cells[(b, lo + i)] = ('<', nm, 0); lo_cells[(b, hi + i)] = ('>', nm, 0)
# lo/hi tables: emit as .byte <label / .byte >label
for b, lo, hi, n, tb, adj in lohi_tab:
    for i in range(n):
        t = (byte(b, lo + i) | byte(b, hi + i) << 8) + adj
        tbk = FIXED if t >= 0xC000 else (tb if tb is not None else (b if b != FIXED else None))
        nm = want(tbk, t) if tbk is not None else None
        if nm:
            lo_cells[(b, lo + i)] = ('<', nm, adj); lo_cells[(b, hi + i)] = ('>', nm, adj)

STREAM_CMD = {0xF4: 'tempo', 0xF6: 'envelope', 0xF7: 'pitch_mod', 0xFA: 'duty', 0xFB: 'song_transpose',
              0xFC: 'chan_transpose', 0xFD: 'sweep'}
stream_cells = {}   # (p, addr) -> (nbytes, comment)
_starts = {(b, a) for b, a, n in stream_tab}
for b, a, n in stream_tab:
    q = a; end = a + n
    while q < end:
        o = byte(b, q)
        if o in STREAM_CMD: stream_cells[(b, q)] = (2, STREAM_CMD[o]); q += 2
        elif o == 0xF5: stream_cells[(b, q)] = (3, 'new pattern list'); q += 3
        elif o in (0xF8, 0xF9, 0xFE, 0xFF):
            stream_cells[(b, q)] = (1, {0xF8: 'key off', 0xF9: 'hold', 0xFE: 'end of song', 0xFF: 'next pattern'}[o]); q += 1
        else:                                   # run of notes / lengths
            r = q
            while r < end and byte(b, r) < 0x80 and r - q < 12 and (r == q or (b, r) not in _starts): r += 1
            stream_cells[(b, q)] = (r - q, ''); q = r

text_cells = {}    # (p, addr) -> (len, rev)
for b, a, n, rev in text_tab:
    if all((b, a + k) not in code_bytes for k in range(n)): text_cells[(b, a)] = (n, rev)

struct_rows = {}   # (p, addr) -> fmt
for b, a, n, fmt in struct_tab:
    sz = sum(2 if c in 'wp' else 1 for c in fmt)
    for i in range(n):
        struct_rows[(b, a + i * sz)] = fmt

# ---- emit -------------------------------------------------------------------------
def emit_bank(p):
    base = 0xC000 if p == FIXED else 0x8000
    # first pass formats instructions (this populates labels)
    text = {}
    for a in range(base, base + 0x4000):
        if (p, a) in instr: text[a] = fmt_instr(p, a)
    out = []; a = base
    while a < base + 0x4000:
        if (p, a) in blob_start: out.append(f'; {blob_start[(p, a)]}')
        lab = [labels[(p, a)]] if (p, a) in labels else []
        for x in lab: out.append(f'{x}:'); emitted.add((p, a))
        if a in text:
            out.append('    ' + text[a]); a += instr[(p, a)][1]; continue
        if (p, a) in word_cells:
            if (p, a + 1) in labels:   # a label points at the high byte: split the word
                out.append(f'    .byte <{word_cells[(p, a)]}'); out.append(f'{labels[(p, a + 1)]}:'); emitted.add((p, a + 1))
                out.append(f'    .byte >{word_cells[(p, a)]}')
            else: out.append(f'    .word {word_cells[(p, a)]}')
            a += 2; continue
        if (p, a) in lo_cells:
            k, nm, adj = lo_cells[(p, a)]
            out.append(f'    .byte {k}({nm}{"-%d" % -adj if adj < 0 else "+%d" % adj if adj else ""})'); a += 1; continue
        if (p, a) in text_cells:
            n, rev = text_cells[(p, a)]
            st = ''.join(chr(byte(p, a + k)) for k in range(n))
            out.append(f'    .byte "{st}"' + (f'   ; reads: "{st[::-1]}"' if rev else ''))
            a += n; continue
        if (p, a) in stream_cells:
            n, cm = stream_cells[(p, a)]
            out.append('    .byte ' + ','.join(f'${byte(p, a + k):02X}' for k in range(n)) + (f'   ; {cm}' if cm else ''))
            a += n; continue
        if (p, a) in struct_rows:
            fmt = struct_rows[(p, a)]; vals = []; q = a
            for c in fmt:
                if c == 'w': vals.append(('.word', f'${byte(p, q) | byte(p, q + 1) << 8:04X}')); q += 2
                elif c == 'p':
                    t = byte(p, q) | byte(p, q + 1) << 8
                    nm = want(FIXED if t >= 0xC000 else p, t)
                    vals.append(('.word', nm or f'${t:04X}')); q += 2
                else: vals.append(('.byte', f'${byte(p, q):02X}')); q += 1
            groups = []
            for d, v in vals:
                if groups and groups[-1][0] == d: groups[-1][1].append(v)
                else: groups.append((d, [v]))
            for d, vs in groups: out.append(f'    {d} ' + ', '.join(vs))
            a = q; continue
        # long fill runs
        n = 0
        while (a + n < base + 0x4000 and byte(p, a + n) == byte(p, a)
               and (n == 0 or ((p, a + n) not in labels and a + n not in text
                               and (p, a + n) not in word_cells and (p, a + n) not in lo_cells
                               and (p, a + n) not in struct_rows and (p, a + n) not in stream_cells
                               and (p, a + n) not in text_cells))):
            n += 1
        if n >= 8:
            out.append(f'    .res {n}, ${byte(p, a):02X}'); a += n; continue
        # data run until next label / instr / special cell
        run = []
        while a < base + 0x4000 and len(run) < 16 and (run == [] or ((p, a) not in labels and a not in text
                                   and (p, a) not in word_cells and (p, a) not in lo_cells
                                   and (p, a) not in struct_rows and (p, a) not in stream_cells
                                   and (p, a) not in text_cells)):
            run.append(byte(p, a)); a += 1
        out.append('    .byte ' + ','.join(f'${x:02X}' for x in run))
    return out

os.makedirs(os.path.join(ROOT, 'src'), exist_ok=True)
for i in range(3): want(FIXED, byte(FIXED, 0x3FFA + 2 * i) | byte(FIXED, 0x3FFB + 2 * i) << 8)
for (_b, _a) in blob_start: want(_b, _a)
# two rounds so labels created by later banks (cross refs) appear in earlier outputs
emitted = set()
for _ in range(2):          # let cross-bank references create their labels
    banks = {p: emit_bank(p) for p in range(NB)}
for _ in range(12):         # then drop labels that could not be emitted (inside a cell, etc.)
    emitted = set()
    banks = {p: emit_bank(p) for p in range(NB)}
    missing = {k for k in labels if k not in emitted}
    if not missing: break
    badlabels |= missing
    for k in missing: labels.pop(k, None)
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
    f.write('\n; unnamed RAM locations referenced by code\n')
    for a in sorted(autoram - set(ramnames)):
        f.write((f'zp_{a:02X} = ${a:02X}' if a < 0x100 else f'ram_{a:04X} = ${a:04X}') + '\n')

ncode = len(code_bytes)
print('auto pointer tables:', len(auto_tables), 'words:', sum(len(r) for _,_,r in auto_tables))
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
if os.environ.get('DBG'):
    k = (FIXED, 0xC5EA); print('ctx C5EA', ctx.get(k), instr.get(k), (0, 0x8245) in starts, (0,0x8245) in code_bytes)

if os.environ.get('GAPS'):
    described = set(code_bytes) | set(blob_bytes)
    for (b, a), (n, _) in stream_cells.items(): described |= {(b, a + k) for k in range(n)}
    for (b, a), (n, _) in text_cells.items(): described |= {(b, a + k) for k in range(n)}
    for (b, a), fmt in struct_rows.items(): described |= {(b, a + k) for k in range(sum(2 if c in 'wp' else 1 for c in fmt))}
    for (b, a) in word_cells: described |= {(b, a), (b, a + 1)}
    for (b, a) in lo_cells: described.add((b, a))
    tot = 0; allgaps = []
    for p in range(NB):
        base = 0xC000 if p == FIXED else 0x8000; a = base
        while a < base + 0x4000:
            if (p, a) in described: a += 1; continue
            s0 = a
            while a < base + 0x4000 and (p, a) not in described: a += 1
            allgaps.append((a - s0, p, s0)); tot += a - s0
    print(f'unclassified bytes: {tot} of {NB * 16384} ({100 * tot / (NB * 16384):.1f}%)')
    for n, p, s0 in sorted(allgaps, reverse=True)[:int(os.environ.get("GAPS"))]: print(f'  bank {p} ${s0:04X}-${s0 + n - 1:04X} ({n} bytes)')
