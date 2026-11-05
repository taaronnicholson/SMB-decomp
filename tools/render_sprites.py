#!/usr/bin/env python3
"""Render every entity animation group (bank 1 table $8D7D) for a stage using the emulator's CHR/palettes.

An entity's group is (ent_flags >> 3) & $1F. Group = word table: entry f is an offset (relative to its own address) to frame f.
Frame = count byte + count * 6-byte sprites: dx(16) dy(16) tile attr; tile is added to the group's tile base ram[$0120+group].
Usage: python3 -I tools/render_sprites.py <stage> [frames=1250]   -> build/sprites/stage<N>_groups.png"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import emu
from PIL import Image, ImageDraw
ROOT = os.path.dirname(HERE)
rom = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read()
b1 = rom[16 + 16384:16 + 2 * 16384]
def by(a): return b1[a - 0x8000]
def wd(a): return by(a) | by(a + 1) << 8
GROUPS = 31
def frames_of(g):
    P = wd(0x8D7D + 2 * g); n = wd(P) // 2
    return [P + 2 * f + wd(P + 2 * f) for f in range(n)]
def sprites_of(ptr):
    n = by(ptr); out = []
    for k in range(n):
        a = ptr + 1 + 6 * k
        sx = by(a) | by(a + 1) << 8; sy = by(a + 2) | by(a + 3) << 8
        sx -= 65536 if sx > 32767 else 0; sy -= 65536 if sy > 32767 else 0
        out.append((sx, sy, by(a + 4), by(a + 5)))
    return out
def draw_frame(nes, img, ox, oy, g, ptr):
    base = nes.ram[0x120 + g]
    for sx, sy, t, at in sprites_of(ptr):
        tile = (base + t) & 255
        for y in range(8):
            lo, hi = nes.vram[tile * 16 + y], nes.vram[tile * 16 + y + 8]
            for x in range(8):
                c = ((lo >> (7 - x)) & 1) | ((hi >> (7 - x)) & 1) << 1
                if not c: continue
                xx = 7 - x if at & 0x40 else x; yy = 7 - y if at & 0x80 else y
                px, py = ox + sx + xx, oy + sy + yy
                if 0 <= px < img.width and 0 <= py < img.height:
                    img.putpixel((px, py), emu.PALETTE[nes.pal[16 + (at & 3) * 4 + c] & 63])
                # note: bit 5 of attr (behind background) is ignored here
if __name__ == '__main__':
    stage = int(sys.argv[1]); nfr = int(sys.argv[2]) if len(sys.argv) > 2 else 1250
    nes = emu.NES(rom); step = nes.step
    presses = {130, 131, 260, 261, 400, 401, 720, 721, 722, 800, 801}
    def st():
        if nes.PC == 0xC66C: nes.ram[0x93] = stage
        step()
    nes.step = st
    for f in range(nfr):
        nes.joy = 8 if f in presses else 0; nes.frame()
    CELL = 48; cols = 8
    rows = sum(1 for g in range(GROUPS)) ; sheets = []
    out = os.path.join(ROOT, 'build/sprites'); os.makedirs(out, exist_ok=True)
    maxf = max(len(frames_of(g)) for g in range(GROUPS))
    W = 40 + min(maxf, 12) * CELL; H = GROUPS * CELL
    img = Image.new('RGB', (W, H), (40, 40, 60)); d = ImageDraw.Draw(img)
    for g in range(GROUPS):
        d.text((2, g * CELL + 18), f'g{g}', fill=(255, 255, 0))
        for f, ptr in enumerate(frames_of(g)[:12]):
            draw_frame(nes, img, 40 + f * CELL + CELL // 2, g * CELL + CELL // 2 + 8, g, ptr)
    img.save(os.path.join(out, f'stage{stage}_groups.png'))
    print('tile bases', [nes.ram[0x120 + g] for g in range(GROUPS)])
    print('wrote', os.path.join(out, f'stage{stage}_groups.png'), img.size)
