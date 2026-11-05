"""Play stage 1 with random inputs and report which routines write/read each still-unnamed RAM byte (and the values written).
Usage: LABELS=/tmp/labels.json python3 -I tools/decomp.py; python3 -I tools/watch_ram.py <seed> <frames> /tmp/labels.json [hex addrs...]"""
import sys, os, json, re, collections, bisect
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import emu
ROM = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read()
labels = json.load(open(sys.argv[3]))
auto = re.compile(r'^(?:F|B\d)_[0-9A-F]{4}$')
byb = collections.defaultdict(list)
for p, a, n in labels:
    byb[p].append((a, n))
for p in byb: byb[p].sort()
def routine(bank, pc):
    b = 7 if pc >= 0xC000 else bank
    L = byb[b]; i = bisect.bisect_right([a for a, _ in L], pc) - 1
    while i >= 0 and (auto.match(L[i][1]) or L[i][1].startswith('Tbl_')): i -= 1
    return L[i][1] if i >= 0 else '?'

# unnamed RAM from the current source
src = ''.join(open(os.path.join(ROOT, f'src/{n}.s')).read() for n in ['bank0', 'bank1', 'bank2', 'bank3', 'bank4', 'bank5', 'bank6', 'fixed'])
watch = {int(m[3:], 16) if m.startswith('zp_') else int(m[4:], 16) for m in set(re.findall(r'\b(zp_[0-9A-F]{2}|ram_[0-9A-F]{4})\b', src))}
extra = [int(x, 16) for x in sys.argv[4:]]
if extra: watch = set(extra)

nes = emu.NES(ROM); step = nes.step
cur = {'pc': 0}
W = collections.defaultdict(lambda: collections.defaultdict(set))   # addr -> routine -> values written
R = collections.defaultdict(collections.Counter)
rd0, wr0 = nes.rd, nes.wr
def rd(a):
    v = rd0(a)
    if a < 0x800 and a in watch and recording[0]: R[a][routine(nes.bank, cur['pc'])] += 1
    return v
def wr(a, v):
    if a < 0x800 and a in watch and recording[0]:
        s = W[a][routine(nes.bank, cur['pc'])]
        if len(s) < 12: s.add(v & 255)
    wr0(a, v)
nes.rd = rd; nes.wr = wr
recording = [False]
def st():
    cur['pc'] = nes.PC
    if nes.PC == 0xC66C and not recording[0]: nes.ram[0x93] = 0
    step()
nes.step = st
start = {130, 131, 260, 261, 400, 401, 720, 721, 722, 800, 801}
for f in range(1250):
    nes.joy = 8 if f in start else 0; nes.frame()
recording[0] = True
r = nes.ram
if os.environ.get('STAGE'): r[0x93] = int(os.environ['STAGE'], 16)
if os.environ.get('FORCE'): r[0x72C] = int(os.environ['FORCE'], 16)     # force a game_state at the start
last_gs = [r[0x72C]]
import random
random.seed(int(sys.argv[1]))
N = int(sys.argv[2])
pat = 0; hold = 0
for f in range(N):
    if hold == 0:
        pat = random.choice([0x80, 0x80, 0x81, 0x82, 0x83, 0x40, 0x41, 0x20, 0x10, 0x00, 0x82, 0xA0, 0x92])
        hold = random.randint(5, 40)
    hold -= 1
    nes.joy = pat
    r[0x7A] = 99     # invulnerable
    if os.environ.get('NOINPUT'): nes.joy = 0
    nes.frame()
    if r[0x72C] != last_gs[0]: print(f'frame {f}: game_state {last_gs[0]:02X} -> {r[0x72C]:02X}'); last_gs[0] = r[0x72C]
out = {}
for a in sorted(watch):
    if a in W or a in R:
        out[a] = (dict((k, sorted(v)) for k, v in W[a].items()), dict(R[a].most_common(4)))
for a, (w, rr) in out.items():
    name = f'zp_{a:02X}' if a < 0x100 else f'ram_{a:04X}'
    ws = '; '.join(f'{k}={",".join("%02X" % x for x in v[:8])}' for k, v in list(w.items())[:4])
    print(f'{name} W[{ws}] R[{",".join(rr)}]')
