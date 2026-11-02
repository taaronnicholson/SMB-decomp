#!/usr/bin/env python3
"""Run the emulator and report which code writes CHR-RAM (pattern tables) and where.
Usage: python3 -I tools/chrtrace.py <frames> [--press=START@n,...]"""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import emu
root = os.path.dirname(HERE)
nes = emu.NES(open(os.path.join(root, 'rom/game.nes'), 'rb').read())
log = collections.defaultdict(lambda: [0, 1 << 16, 0, set()])   # (bank,pc) -> count, minaddr, maxaddr, frames
orig = nes.wr; cur_pc = [0]
def wr(a, v):
    if (a & 7) == 7 and 0x2000 <= a < 0x4000 and (nes.vaddr & 0x3FFF) < 0x2000:
        pc = cur_pc[0]; b = nes.bank if pc < 0xC000 else 7
        e = log[(b, pc)]; e[0] += 1; ad = nes.vaddr & 0x3FFF; e[1] = min(e[1], ad); e[2] = max(e[2], ad); e[3].add(nes.frames)
    orig(a, v)
nes.wr = wr
step = nes.step
def st():
    cur_pc[0] = nes.PC; step()
nes.step = st
presses = {}
for a in sys.argv[2:]:
    if a.startswith('--press='):
        for it in a[8:].split(','): k, f = it.split('@'); presses[int(f)] = {'START': 8, 'A': 1, 'B': 2}[k]
for f in range(int(sys.argv[1])):
    nes.joy = presses.get(f, 0); nes.frame()
for (b, pc), (n, lo, hi, fr) in sorted(log.items(), key=lambda kv: -kv[1][0]):
    print(f'bank {b} pc {pc:04X}: {n:5d} writes, PPU ${lo:04X}-${hi:04X}, frames {min(fr)}..{max(fr)}')
