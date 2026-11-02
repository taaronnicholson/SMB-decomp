#!/usr/bin/env python3
"""Validate tools/lzdec.py against the real decompressor: run the emulator and compare memory after each call."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import emu, lzdec
root = os.path.dirname(HERE)
ROM = open(os.path.join(root, 'rom/game.nes'), 'rb').read()
nes = emu.NES(ROM); step = nes.step; cur = None; results = []
presses = {130, 131, 260, 261, 400, 401, 720, 721, 722, 800, 801}
def st():
    global cur
    if nes.PC == 0xFDEF and cur is None:
        cur = (nes.bank, nes.ram[0x51] | nes.ram[0x52] << 8, nes.ram[0x55] | nes.ram[0x56] << 8, bool(nes.P & 1), nes.S)
    step()
    if cur is not None and nes.S > cur[4]:
        bank, src, dst, ram, _ = cur; cur = None
        mine, end = lzdec.decompress(nes.prg[bank], src - 0x8000)
        if ram: got = bytes(nes.ram[(dst + i) & 0x7FF] for i in range(len(mine)))
        else: got = bytes(nes.vram[nes.nt(dst + i) if dst + i >= 0x2000 else dst + i] for i in range(len(mine)))
        ok = got == mine and end + 0x8000 == (nes.ram[0x51] | nes.ram[0x52] << 8)
        results.append((bank, src, dst, ram, len(mine), ok, got != mine))
nes.step = st
for f in range(int(sys.argv[1]) if len(sys.argv) > 1 else 900):
    nes.joy = 8 if f in presses else 0; nes.frame()
for r in results: print('bank %d src $%04X dst $%04X %s out %5d bytes  %s' % (r[0], r[1], r[2], 'RAM ' if r[3] else 'VRAM', r[4], 'MATCH' if r[5] else ('DATA DIFFERS' if r[6] else 'END PTR DIFFERS')))
print('all match' if all(r[5] for r in results) else 'MISMATCHES', len(results), 'calls')
