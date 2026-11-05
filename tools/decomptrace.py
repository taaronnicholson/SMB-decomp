#!/usr/bin/env python3
"""List calls to the game's decompressor (Decompress = $FDEF / $FDE9) while the emulator runs."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import emu
root = os.path.dirname(HERE)
nes = emu.NES(open(os.path.join(root, 'rom/game.nes'), 'rb').read())
seen = []
step = nes.step
def st():
    if nes.PC in (0xFDEF, 0xFDE9):
        ptr = nes.ram[0x51] | nes.ram[0x52] << 8 if False else None
    step()
nes.step = st
# find the pointer variable names from the source: ptr_lo/hi = $51/$52 ; dest = $55/$56
def st2():
    if nes.PC in (0xFDEF, 0xFDE9):
        seen.append((nes.frames, nes.bank, nes.ram[0x51] | nes.ram[0x52] << 8, nes.ram[0x55] | nes.ram[0x56] << 8, nes.P & 1 if nes.PC == 0xFDEF else 0))
    step()
nes.step = st2
presses = {}
for a in sys.argv[2:]:
    if a.startswith('--press='):
        for it in a[8:].split(','): k, f = it.split('@'); presses[int(f)] = {'START': 8, 'A': 1, 'B': 2}[k]
for f in range(int(sys.argv[1])):
    nes.joy = presses.get(f, 0); nes.frame()
for fr, b, src, dst, c in seen:
    print(f'frame {fr:5d}: bank {b} src ${src:04X} -> dst ${dst:04X}  (carry {c})')
