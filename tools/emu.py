#!/usr/bin/env python3
"""Tiny NES (UxROM) emulator for inspecting graphics: runs the ROM, captures CHR-RAM/nametables/palettes.
Not cycle accurate. Usage: python3 -I tools/emu.py <frames> [out.png] [--press=START@frame,...]"""
import os, sys, zlib, struct
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from dis6502 import OPS, LEN

class NES:
    def __init__(self, rom):
        self.nb = rom[4]; self.prg = [rom[16 + i * 16384:16 + (i + 1) * 16384] for i in range(self.nb)]
        self.bank = 0; self.ram = bytearray(0x800)
        self.vram = bytearray(0x4000); self.pal = bytearray(32); self.oam = bytearray(256)
        self.ctrl = self.mask = 0; self.vbl = False; self.s0 = False; self.reads2002 = 0
        self.vaddr = 0; self.latch = False; self.rbuf = 0; self.scx = self.scy = 0
        self.mirror_h = (rom[6] & 1) == 0
        self.joy = 0; self.joy_shift = 0; self.strobe = 0; self.oamaddr = 0
        self.A = self.X = self.Y = 0; self.S = 0xFD; self.P = 0x24
        self.PC = self.rd16(0xFFFC); self.nmi = False; self.frames = 0; self.trace = False
    def rd16(self, a): return self.rd(a) | self.rd(a + 1) << 8
    def nt(self, a):
        a = (a - 0x2000) & 0xFFF; t = a >> 10
        t = (t >> 1) if self.mirror_h else (t & 1)
        return 0x2000 + t * 0x400 + (a & 0x3FF)
    def rd(self, a):
        if a < 0x2000: return self.ram[a & 0x7FF]
        if a < 0x4000:
            r = a & 7
            if r == 2:
                v = (0x80 if self.vbl else 0) | (0x40 if self.s0 else 0)
                self.vbl = False; self.latch = False
                self.reads2002 += 1
                if self.reads2002 > 40: self.s0 = True      # fake sprite-0 hit after a while
                return v
            if r == 4: return self.oam[self.oamaddr]
            if r == 7:
                v = self.rbuf; ad = self.vaddr & 0x3FFF
                if ad >= 0x3F00: v = self.pal[ad & 0x1F]; self.rbuf = self.vram[self.nt(ad) if ad >= 0x2000 else ad]
                else: self.rbuf = self.vram[self.nt(ad) if 0x2000 <= ad < 0x3F00 else ad]
                self.vaddr += 32 if self.ctrl & 4 else 1
                return v
            return 0
        if a == 0x4016:
            v = (self.joy >> self.joy_shift) & 1 if self.joy_shift < 8 else 1
            if not self.strobe: self.joy_shift += 1
            return v | 0x40
        if a < 0x8000: return 0
        if a < 0xC000: return self.prg[self.bank][a - 0x8000]
        return self.prg[self.nb - 1][a - 0xC000]
    def wr(self, a, v):
        v &= 0xFF
        if a < 0x2000: self.ram[a & 0x7FF] = v; return
        if a < 0x4000:
            r = a & 7
            if r == 0: self.ctrl = v
            elif r == 1: self.mask = v
            elif r == 3: self.oamaddr = v
            elif r == 4: self.oam[self.oamaddr] = v; self.oamaddr = (self.oamaddr + 1) & 255
            elif r == 5:
                if not self.latch: self.scx = v
                else: self.scy = v
                self.latch = not self.latch
            elif r == 6:
                if not self.latch: self.vaddr = (v & 0x3F) << 8 | (self.vaddr & 0xFF)
                else: self.vaddr = (self.vaddr & 0xFF00) | v
                self.latch = not self.latch
            elif r == 7:
                ad = self.vaddr & 0x3FFF
                if ad >= 0x3F00:
                    i = ad & 0x1F
                    if i & 3 == 0: i &= 0x0F; self.pal[i] = v; self.pal[i | 0x10] = v
                    else: self.pal[i] = v
                elif ad >= 0x2000: self.vram[self.nt(ad)] = v
                else: self.vram[ad] = v
                self.vaddr += 32 if self.ctrl & 4 else 1
            return
        if a == 0x4014:
            for i in range(256): self.oam[(self.oamaddr + i) & 255] = self.rd((v << 8) + i)
            return
        if a == 0x4016:
            if self.strobe and not (v & 1): self.joy_shift = 0
            self.strobe = v & 1; return
        if a >= 0x8000: self.bank = v & 7
    # ---- CPU ----
    def push(self, v): self.ram[0x100 + self.S] = v & 255; self.S = (self.S - 1) & 255
    def pull(self): self.S = (self.S + 1) & 255; return self.ram[0x100 + self.S]
    def setnz(self, v): v &= 255; self.P = (self.P & 0x7D) | (v & 0x80) | (2 if v == 0 else 0); return v
    def ea(self, m, pc):
        r = self.rd
        if m == 'zp': return r(pc + 1)
        if m == 'zpx': return (r(pc + 1) + self.X) & 255
        if m == 'zpy': return (r(pc + 1) + self.Y) & 255
        if m == 'abs': return r(pc + 1) | r(pc + 2) << 8
        if m == 'abx': return ((r(pc + 1) | r(pc + 2) << 8) + self.X) & 0xFFFF
        if m == 'aby': return ((r(pc + 1) | r(pc + 2) << 8) + self.Y) & 0xFFFF
        if m == 'izx':
            z = (r(pc + 1) + self.X) & 255; return r(z) | r((z + 1) & 255) << 8
        if m == 'izy':
            z = r(pc + 1); return ((r(z) | r((z + 1) & 255) << 8) + self.Y) & 0xFFFF
    def step(self):
        pc = self.PC; o = self.rd(pc); mn, m = OPS[o]; l = LEN[m]
        a = None if m in ('imp', 'acc', 'imm', 'rel', 'ind') else self.ea(m, pc)
        nxt = (pc + l) & 0xFFFF
        def val(): return self.rd(pc + 1) if m == 'imm' else (self.A if m == 'acc' else self.rd(a))
        def store(v):
            if m == 'acc': self.A = v & 255
            else: self.wr(a, v)
        P = self.P
        if mn == 'LDA': self.A = self.setnz(val())
        elif mn == 'LDX': self.X = self.setnz(val())
        elif mn == 'LDY': self.Y = self.setnz(val())
        elif mn == 'STA': self.wr(a, self.A)
        elif mn == 'STX': self.wr(a, self.X)
        elif mn == 'STY': self.wr(a, self.Y)
        elif mn in ('TAX',): self.X = self.setnz(self.A)
        elif mn == 'TAY': self.Y = self.setnz(self.A)
        elif mn == 'TXA': self.A = self.setnz(self.X)
        elif mn == 'TYA': self.A = self.setnz(self.Y)
        elif mn == 'TSX': self.X = self.setnz(self.S)
        elif mn == 'TXS': self.S = self.X
        elif mn == 'AND': self.A = self.setnz(self.A & val())
        elif mn == 'ORA': self.A = self.setnz(self.A | val())
        elif mn == 'EOR': self.A = self.setnz(self.A ^ val())
        elif mn in ('ADC', 'SBC'):
            v = val() if mn == 'ADC' else val() ^ 255
            t = self.A + v + (P & 1)
            c = 1 if t > 255 else 0; ov = (~(self.A ^ v) & (self.A ^ t) & 0x80) != 0
            self.A = t & 255; self.setnz(self.A); self.P = (self.P & 0xBE) | c | (0x40 if ov else 0)
        elif mn in ('CMP', 'CPX', 'CPY'):
            reg = {'CMP': self.A, 'CPX': self.X, 'CPY': self.Y}[mn]; t = reg - val()
            self.setnz(t & 255); self.P = (self.P & 0xFE) | (1 if t >= 0 else 0)
        elif mn == 'BIT':
            v = val(); self.P = (self.P & 0x3D) | (v & 0xC0) | (2 if (self.A & v) == 0 else 0)
        elif mn in ('INC', 'DEC'):
            v = self.setnz(self.rd(a) + (1 if mn == 'INC' else -1)); self.wr(a, v)
        elif mn == 'INX': self.X = self.setnz(self.X + 1)
        elif mn == 'INY': self.Y = self.setnz(self.Y + 1)
        elif mn == 'DEX': self.X = self.setnz(self.X - 1)
        elif mn == 'DEY': self.Y = self.setnz(self.Y - 1)
        elif mn in ('ASL', 'LSR', 'ROL', 'ROR'):
            v = val(); c = P & 1
            if mn == 'ASL': nc = v >> 7; v = v << 1
            elif mn == 'LSR': nc = v & 1; v = v >> 1
            elif mn == 'ROL': nc = v >> 7; v = v << 1 | c
            else: nc = v & 1; v = v >> 1 | c << 7
            v = self.setnz(v); self.P = (self.P & 0xFE) | nc; store(v)
        elif m == 'rel':
            cond = {'BPL': not P & 0x80, 'BMI': P & 0x80, 'BVC': not P & 0x40, 'BVS': P & 0x40,
                    'BCC': not P & 1, 'BCS': P & 1, 'BNE': not P & 2, 'BEQ': P & 2}[mn]
            if cond:
                d = self.rd(pc + 1); nxt = (nxt + (d - 256 if d > 127 else d)) & 0xFFFF
        elif mn == 'JMP':
            nxt = (self.rd(pc + 1) | self.rd(pc + 2) << 8) if m == 'abs' else None
            if m == 'ind':
                p = self.rd(pc + 1) | self.rd(pc + 2) << 8
                nxt = self.rd(p) | self.rd((p & 0xFF00) | ((p + 1) & 0xFF)) << 8
        elif mn == 'JSR':
            r = (pc + 2) & 0xFFFF; self.push(r >> 8); self.push(r & 255)
            nxt = self.rd(pc + 1) | self.rd(pc + 2) << 8
        elif mn == 'RTS': nxt = (self.pull() | self.pull() << 8) + 1 & 0xFFFF
        elif mn == 'RTI': self.P = self.pull() | 0x20; nxt = self.pull() | self.pull() << 8
        elif mn == 'PHA': self.push(self.A)
        elif mn == 'PLA': self.A = self.setnz(self.pull())
        elif mn == 'PHP': self.push(self.P | 0x30)
        elif mn == 'PLP': self.P = self.pull() | 0x20
        elif mn == 'CLC': self.P &= 0xFE
        elif mn == 'SEC': self.P |= 1
        elif mn == 'CLI': self.P &= 0xFB
        elif mn == 'SEI': self.P |= 4
        elif mn == 'CLD': self.P &= 0xF7
        elif mn == 'SED': self.P |= 8
        elif mn == 'CLV': self.P &= 0xBF
        elif mn == 'BRK': raise RuntimeError(f'BRK at {pc:04X}')
        self.PC = nxt
    def frame(self):
        # visible part, then vblank
        self.s0 = False; self.reads2002 = 0
        for _ in range(9000): self.step()
        self.vbl = True; self.frames += 1
        if self.ctrl & 0x80:
            self.push(self.PC >> 8); self.push(self.PC & 255); self.push(self.P & ~0x10)
            self.P |= 4; self.PC = self.rd16(0xFFFA)
        for _ in range(900): self.step()
        self.vbl = False

# ---- rendering ----
PALETTE = [(84,84,84),(0,30,116),(8,16,144),(48,0,136),(68,0,100),(92,0,48),(84,4,0),(60,24,0),(32,42,0),(8,58,0),(0,64,0),(0,60,0),(0,50,60),(0,0,0),(0,0,0),(0,0,0),
           (152,150,152),(8,76,196),(48,50,236),(92,30,228),(136,20,176),(160,20,100),(152,34,32),(120,60,0),(84,90,0),(40,114,0),(8,124,0),(0,118,40),(0,102,120),(0,0,0),(0,0,0),(0,0,0),
           (236,238,236),(76,154,236),(120,124,236),(176,98,236),(228,84,236),(236,88,180),(236,106,100),(212,136,32),(160,170,0),(116,196,0),(76,208,32),(56,204,108),(56,180,204),(60,60,60),(0,0,0),(0,0,0),
           (236,238,236),(168,204,236),(188,188,236),(212,178,236),(236,174,236),(236,174,212),(236,180,176),(228,196,144),(204,210,120),(180,222,120),(168,226,144),(152,226,180),(160,214,228),(160,162,160),(0,0,0),(0,0,0)]
def png(path, w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    def ch(t, d): c = struct.pack('>I', len(d)) + t + d; return c + struct.pack('>I', zlib.crc32(t + d))
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))
def tile_px(chr_, base, t, x, y):
    lo = chr_[base + t * 16 + y]; hi = chr_[base + t * 16 + y + 8]
    return ((lo >> (7 - x)) & 1) | ((hi >> (7 - x)) & 1) << 1
def render_chr(nes, path, pal=(0x0F, 0x16, 0x27, 0x30)):
    W = 256; img = bytearray(W * 256 * 3)
    for half in range(2):
        for t in range(256):
            for y in range(8):
                for x in range(8):
                    c = PALETTE[pal[tile_px(nes.vram, half * 0x1000, t, x, y)] & 63]
                    px = (t % 16) * 8 + x + 0; py = half * 128 + (t // 16) * 8 + y
                    o = (py * W + px) * 3; img[o:o + 3] = bytes(c)
    png(path, W, 256, img)
def render_screen(nes, path):
    bgbase = 0x1000 if nes.ctrl & 0x10 else 0
    img = bytearray(256 * 240 * 3)
    base = 0x2000 + ((nes.ctrl & 3) * 0x400)
    for ty in range(30):
        for tx in range(32):
            t = nes.vram[nes.nt(base + ty * 32 + tx)]
            at = nes.vram[nes.nt(base + 0x3C0 + (ty // 4) * 8 + tx // 4)]
            sh = ((ty // 2) & 1) * 4 + ((tx // 2) & 1) * 2; pi = (at >> sh) & 3
            for y in range(8):
                for x in range(8):
                    c = tile_px(nes.vram, bgbase, t, x, y)
                    col = PALETTE[nes.pal[0] & 63] if c == 0 else PALETTE[nes.pal[pi * 4 + c] & 63]
                    o = ((ty * 8 + y) * 256 + tx * 8 + x) * 3; img[o:o + 3] = bytes(col)
    sp = 0x1000 if nes.ctrl & 0x08 else 0
    for i in range(63, -1, -1):
        sy, t, at, sx = nes.oam[i * 4:i * 4 + 4]
        if sy >= 0xEF: continue
        for y in range(8):
            for x in range(8):
                xx = 7 - x if at & 0x40 else x; yy = 7 - y if at & 0x80 else y
                c = tile_px(nes.vram, sp, t, xx, yy)
                if c and sx + x < 256 and sy + 1 + y < 240:
                    o = ((sy + 1 + y) * 256 + sx + x) * 3; img[o:o + 3] = bytes(PALETTE[nes.pal[0x10 + (at & 3) * 4 + c] & 63])
    png(path, 256, 240, img)

if __name__ == '__main__':
    root = os.path.dirname(HERE)
    nes = NES(open(os.path.join(root, 'rom/game.nes'), 'rb').read())
    n = int(sys.argv[1]); out = sys.argv[2] if len(sys.argv) > 2 else None
    presses = {}
    for a in sys.argv[3:]:
        if a.startswith('--press='):
            for it in a[8:].split(','): k, f = it.split('@'); presses[int(f)] = {'A': 1, 'B': 2, 'SELECT': 4, 'START': 8, 'UP': 16, 'DOWN': 32, 'LEFT': 64, 'RIGHT': 128}[k]
    for f in range(n):
        nes.joy = presses.get(f, 0)
        nes.frame()
    print('frames', nes.frames, 'PC', hex(nes.PC), 'bank', nes.bank, 'ctrl', hex(nes.ctrl), 'mask', hex(nes.mask))
    if out:
        render_screen(nes, out + '.screen.png'); render_chr(nes, out + '.chr.png')
        print('wrote', out + '.screen.png', out + '.chr.png')
