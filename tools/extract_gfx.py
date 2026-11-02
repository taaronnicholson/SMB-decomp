#!/usr/bin/env python3
"""Decompress every block listed in tools/gfx_blocks.json into build/gfx/<name>.bin and render
grayscale 2bpp tile sheets (build/gfx/<name>.png). Output is derived from the ROM and is git-ignored."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lzdec
from emu import png
ROOT = os.path.dirname(HERE)
rom = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read()
PRG = [rom[16 + i * 16384:16 + (i + 1) * 16384] for i in range(rom[4])]
GRAY = [(0, 0, 0), (96, 96, 96), (176, 176, 176), (255, 255, 255)]
def sheet(data, path, cols=16):
    n = len(data) // 16; rows = (n + cols - 1) // cols
    W, H = cols * 8, max(rows, 1) * 8; img = bytearray(W * H * 3)
    for t in range(n):
        for y in range(8):
            lo, hi = data[t * 16 + y], data[t * 16 + y + 8]
            for x in range(8):
                c = GRAY[((lo >> (7 - x)) & 1) | ((hi >> (7 - x)) & 1) << 1]
                o = ((t // cols * 8 + y) * W + (t % cols) * 8 + x) * 3; img[o:o + 3] = bytes(c)
    png(path, W, H, img)
if __name__ == '__main__':
    out = os.path.join(ROOT, 'build/gfx'); os.makedirs(out, exist_ok=True)
    for r in json.load(open(os.path.join(HERE, 'gfx_blocks.json'))):
        data, end = lzdec.decompress(PRG[r['bank']], r['src'] - 0x8000)
        assert end + 0x8000 == r['end'], (hex(r['src']), hex(end + 0x8000), hex(r['end']))
        name = f"Gfx_B{r['bank']}_{r['src']:04X}"
        open(os.path.join(out, name + '.bin'), 'wb').write(data)
        if len(data) % 16 == 0: sheet(data, os.path.join(out, name + '.png'))
        print(f"{name}: {r['end'] - r['src']:5d} -> {len(data):5d} bytes ({len(data) // 16} tiles)" + ('' if len(data) % 16 == 0 else '  [not a whole number of tiles]'))
