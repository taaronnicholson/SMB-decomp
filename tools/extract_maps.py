#!/usr/bin/env python3
"""Dump each area's tile map (one byte per 16x16 tile) to build/maps/area_NN.txt as a hex grid.
Width = 8 << log2width, rows = header height. Output is derived from the ROM and git-ignored."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rom = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read()
PRG = [rom[16 + i * 16384:16 + (i + 1) * 16384] for i in range(rom[4])]
LO, HI, BANK, N = 0x83B9, 0x83D1, 0x83E9, 24
out = os.path.join(ROOT, 'build/maps'); os.makedirs(out, exist_ok=True)
for i in range(N):
    h = PRG[0][LO - 0x8000 + i] | PRG[0][HI - 0x8000 + i] << 8
    bank = PRG[0][BANK - 0x8000 + i]
    hdr = PRG[0][h - 0x8000:h - 0x8000 + 12]
    base = hdr[1] | hdr[2] << 8; width = 8 << hdr[3]; rows = hdr[4]
    def cell(r, c):
        a = base + r * width + c - 0x8000          # physical offset in the map bank
        return f'{PRG[bank][a]:02X}' if 0 <= a < 0x4000 and r >= 2 else '--'   # rows 0-1 are phantom (above the playfield)
    with open(os.path.join(out, f'area_{i:02d}.txt'), 'w') as f:
        f.write(f'area {i}: bank {bank} base ${base:04X} width {width} rows {rows} header ${h:04X} {hdr.hex(" ")}  (data starts at base+2*width; rows 0-1 are not stored)\n')
        for r in range(rows):
            f.write(f'{r:3d} ' + ' '.join(cell(r, c) for c in range(width)) + '\n')
    print(f'area {i:2d}: bank {bank} ${base:04X} {width:3d}x{rows:<3d} tiles')
