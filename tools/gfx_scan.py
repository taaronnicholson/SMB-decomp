#!/usr/bin/env python3
"""Drive the emulator through each stage and record every Decompress call (source block, size, output).
Prints a table and writes tools/gfx_blocks.json."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import emu, lzdec
root = os.path.dirname(HERE)
ROM = open(os.path.join(root, 'rom/game.nes'), 'rb').read()
DECOMP, PUTBYTE, STAGE_LOAD = 0xFDEF, 0xFD84, 0xC66C

def run(stage, frames=1300):
    nes = emu.NES(ROM); blocks = []; cur = None; step = nes.step; forced = [False]
    presses = {130, 131, 260, 261, 400, 401, 720, 721, 722, 800, 801}
    def st():
        nonlocal cur
        if nes.PC == STAGE_LOAD and stage is not None: nes.ram[0x93] = stage
        if nes.PC == DECOMP and cur is None:
            cur = dict(bank=nes.bank, src=nes.ram[0x51] | nes.ram[0x52] << 8, s0=nes.S, out=bytearray(),
                       dst=nes.ram[0x55] | nes.ram[0x56] << 8, ram=bool(nes.P & 1), frame=nes.frames)
        step()
        if cur is not None and nes.S > cur['s0']:           # returned from Decompress
            cur['end'] = nes.ram[0x51] | nes.ram[0x52] << 8; blocks.append(cur); cur = None
    nes.step = st
    for f in range(frames):
        nes.joy = 8 if f in presses else 0; nes.frame()
    return blocks, nes
allb = {}
for stg in [None, 0, 1, 2, 3, 4, 5]:
    try: blocks, nes = run(stg)
    except Exception as e: print('stage', stg, 'error', e); continue
    for b in blocks:
        k = (b['bank'], b['src']); e = allb.setdefault(k, dict(bank=b['bank'], src=b['src'], end=b['end'], size=len(lzdec.decompress(nes.prg[b['bank']], b['src'] - 0x8000)[0]), ram=b['ram'], dsts=set(), stages=set()))
        e['stages'].add(-1 if stg is None else stg); e['dsts'].add(b['dst'])
print('unique compressed blocks:', len(allb))
rows = []
for (bank, src), b in sorted(allb.items()):
    rows.append(dict(bank=bank, src=src, end=b['end'], insize=b['end'] - src, outsize=b['size'], ram=b['ram'], dsts=sorted(b['dsts']), stages=sorted(b['stages'])))
    print(f"bank {bank} ${src:04X}-${b['end']-1:04X} ({b['end']-src:5d} B) -> {b['size']:5d} B {'RAM' if b['ram'] else 'VRAM'} dst {','.join('$%04X' % d for d in sorted(b['dsts']))} stages {sorted(b['stages'])}")
json.dump(rows, open(os.path.join(HERE, 'gfx_blocks.json'), 'w'), indent=1)
