#!/usr/bin/env python3
"""Render each area's tile map to build/maps/area_NN.png (derived from the ROM, git-ignored).

Tileset record (bank 0, 8 bytes at $8C9B + 8*t, t = last byte of the area header):
  +0 tile-properties block (LZ, to RAM $03A4)   +2 tile-graphics block (LZ, to PPU $1530)
  +4 metatile planes: TL, TR, BL, BR, 240 bytes each   +6 attribute (palette) plane, 240 bytes
Bank of the two LZ blocks: B0_8C95[t].  Shared background tiles: LZ block bank0:$88A7 -> PPU $1000.
Background pattern table is at $1000. Background colours come from the area's palette set (header byte 5).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lzdec
from PIL import Image, ImageDraw
from emu import PALETTE
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
def bg_palette(set_no):
    """16 NES colour indices (4 palettes x 4) of palette set `set_no` (bank 0 tables $8040/$8049)."""
    p = b0[0x8040 - 0x8000 + set_no] | b0[0x8049 - 0x8000 + set_no] << 8
    return b0[p - 0x8000:p - 0x8000 + 16]
def tile_img(chr_, n, attr, pal):
    im = Image.new('RGB', (8, 8))
    for y in range(8):
        lo, hi = chr_[n * 16 + y], chr_[n * 16 + y + 8]
        for x in range(8): im.putpixel((x, y), PALETTE[pal[(attr & 3) * 4 + (((lo >> (7 - x)) & 1) | ((hi >> (7 - x)) & 1) << 1)] & 63])
    return im
def spawns(area):
    """Entity spawn records for an area from bank 1 ($9F25 pointer table): [(type, y, x, flags, params)]"""
    b1 = PRG[1]
    def by(a): return b1[a - 0x8000]
    p = by(0x9F25 + 2 * area) | by(0x9F26 + 2 * area) << 8
    while by(p) != 0xFF: p += 1
    p += 1; out = []
    while by(p) != 0xFF and len(out) < 60:
        out.append((by(p), by(p + 1) | by(p + 2) << 8, by(p + 3) | by(p + 4) << 8, by(p + 5), tuple(by(p + 6 + k) for k in range(4)))); p += 10
    return out
def one_time(area):
    """8-byte one-time objects after the zp_B4 section: [(flag, type, y, x)]"""
    b1 = PRG[1]
    def by(a): return b1[a - 0x8000]
    p = by(0x9F25 + 2 * area) | by(0x9F26 + 2 * area) << 8
    while by(p) != 0xFF: p += 1
    p += 1
    while by(p) != 0xFF: p += 10
    p += 3; n = 0
    while by(p) != 0xFE and n < 200:
        p += 1 if by(p) == 0xFF else 3; n += 1
    if by(p) != 0xFE: return []
    p += 1; out = []
    while by(p) != 0xFF and len(out) < 20:
        out.append((by(p), by(p + 1), by(p + 2) | by(p + 3) << 8, by(p + 4) | by(p + 5) << 8)); p += 8
    return out
def overlay(img, area, balloons=()):
    d = ImageDraw.Draw(img)
    for r, c in balloons:                         # map tile $C4 = balloon (spawned as type $01 at level load)
        d.ellipse((c * 16, (r - 2) * 16, c * 16 + 15, (r - 2) * 16 + 15), outline=(80, 255, 255), width=2)
    for flag, typ, y, x in one_time(area):
        d.rectangle((x - 6, y - 32 - 6, x + 6, y - 32 + 6), outline=(80, 255, 80), width=2)
        d.text((x + 8, y - 32 + 2), f'{typ:02X}*', fill=(80, 255, 80))
    for typ, y, x, fl, pr in spawns(area):
        px, py = x, y - 32                       # first two map rows are not stored
        d.rectangle((px - 5, py - 5, px + 5, py + 5), outline=(255, 40, 40))
        d.text((px + 7, py - 5), f'{typ:02X}', fill=(255, 255, 0))

if __name__ == '__main__':
    out = os.path.join(ROOT, 'build/maps'); os.makedirs(out, exist_ok=True); cache = {}
    for i in range(N):
        h = b0[LO - 0x8000 + i] | b0[HI - 0x8000 + i] << 8; bank = b0[BANK - 0x8000 + i]
        hdr = b0[h - 0x8000:h - 0x8000 + 12]; base = hdr[1] | hdr[2] << 8; width = 8 << hdr[3]; rows = hdr[4]; t = hdr[11]
        if t not in cache: cache[t] = tileset(t)
        pal = bg_palette(hdr[5])
        chr_, pl, at = cache[t]; tiles = {}
        img = Image.new('RGB', (width * 16, (rows - 2) * 16)); balloons = []
        for r in range(2, rows):
            for c in range(width):
                a = base + r * width + c - 0x8000
                m = PRG[bank][a] if 0 <= a < 0x4000 else 0
                if m == 0xC4: balloons.append((r, c))
                for k, (dx, dy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
                    key = (pl[k][m] if m < 240 else 0, at[m] if m < 240 else 0)
                    if key not in tiles: tiles[key] = tile_img(chr_, key[0], key[1], pal)
                    img.paste(tiles[key], (c * 16 + dx, (r - 2) * 16 + dy))
        img.save(os.path.join(out, f'area_{i:02d}.png'))
        ov = img.copy(); overlay(ov, i, balloons); ov.save(os.path.join(out, f'area_{i:02d}_spawns.png')); print(f'area {i:2d}: tileset {t}, {width}x{rows - 2} tiles -> area_{i:02d}.png')
