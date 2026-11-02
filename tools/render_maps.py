#!/usr/bin/env python3
"""Render each area's tile map to build/maps/area_NN.png (derived from the ROM, git-ignored).

Tileset record (bank 0, 8 bytes at $8C9B + 8*t, t = last byte of the area header):
  +0 tile-properties block (LZ, to RAM $03A4)   +2 tile-graphics block (LZ, to PPU $1530)
  +4 metatile planes: TL, TR, BL, BR, 240 bytes each   +6 attribute (palette) plane, 240 bytes
Bank of the two LZ blocks: B0_8C95[t].  Shared background tiles: LZ block bank0:$88A7 -> PPU $1000.
Background pattern table is at $1000. Colours are placeholders (one tint per attribute value).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lzdec
from PIL import Image
ROOT = os.path.dirname(HERE)
rom = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read()
PRG = [rom[16 + i * 16384:16 + (i + 1) * 16384] for i in range(rom[4])]
b0 = PRG[0]
def w0(a): return b0[a - 0x8000] | b0[a - 0x7FFF] << 8
LO, HI, BANK, N = 0x83B9, 0x83D1, 0x83E9, 24
TINT = [(0, 0, 0), (60, 60, 90)], [(0, 0, 0), (50, 90, 50)], [(0, 0, 0), (110, 60, 40)], [(0, 0, 0), (110, 100, 40)]
def shade(attr, c):
    base = [(0, 0, 0), (0.45, 0.45, 0.45), (0.75, 0.75, 0.75), (1, 1, 1)][c]
    r, g, b = [(0.6, 0.7, 1.0), (0.6, 1.0, 0.6), (1.0, 0.7, 0.5), (1.0, 0.95, 0.5)][attr & 3]
    k = base[0] if isinstance(base, tuple) else base
    return (int(255 * k * r), int(255 * k * g), int(255 * k * b))
def tileset(t):
    rec = 0x8C9B + 8 * t
    props, gfx, planes, attr = w0(rec), w0(rec + 2), w0(rec + 4), w0(rec + 6)
    bank = b0[0x8C95 - 0x8000 + t]
    chr_ = bytearray(4096)
    shared, _ = lzdec.decompress(b0, 0x88A7 - 0x8000); chr_[0:len(shared)] = shared
    g, _ = lzdec.decompress(PRG[bank], gfx - 0x8000); chr_[0x530:0x530 + len(g)] = g
    pl = [b0[planes - 0x8000 + k * 240:planes - 0x8000 + (k + 1) * 240] for k in range(4)]
    at = b0[attr - 0x8000:attr - 0x8000 + 240]
    return chr_, pl, at
def tile_img(chr_, n, attr):
    im = Image.new('RGB', (8, 8))
    for y in range(8):
        lo, hi = chr_[n * 16 + y], chr_[n * 16 + y + 8]
        for x in range(8): im.putpixel((x, y), shade(attr, ((lo >> (7 - x)) & 1) | ((hi >> (7 - x)) & 1) << 1))
    return im
if __name__ == '__main__':
    out = os.path.join(ROOT, 'build/maps'); os.makedirs(out, exist_ok=True); cache = {}
    for i in range(N):
        h = b0[LO - 0x8000 + i] | b0[HI - 0x8000 + i] << 8; bank = b0[BANK - 0x8000 + i]
        hdr = b0[h - 0x8000:h - 0x8000 + 12]; base = hdr[1] | hdr[2] << 8; width = 8 << hdr[3]; rows = hdr[4]; t = hdr[11]
        if t not in cache: cache[t] = tileset(t)
        chr_, pl, at = cache[t]; tiles = {}
        img = Image.new('RGB', (width * 16, (rows - 2) * 16))
        for r in range(2, rows):
            for c in range(width):
                a = base + r * width + c - 0x8000
                m = PRG[bank][a] if 0 <= a < 0x4000 else 0
                for k, (dx, dy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
                    key = (pl[k][m] if m < 240 else 0, at[m] if m < 240 else 0)
                    if key not in tiles: tiles[key] = tile_img(chr_, key[0], key[1])
                    img.paste(tiles[key], (c * 16 + dx, (r - 2) * 16 + dy))
        img.save(os.path.join(out, f'area_{i:02d}.png')); print(f'area {i:2d}: tileset {t}, {width}x{rows - 2} tiles -> area_{i:02d}.png')
