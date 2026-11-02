#!/usr/bin/env python3
"""Find LZ blocks in the unclassified gaps: try the decoder at every offset inside each gap and keep starts that decode cleanly,
end exactly at the end of the gap (within 2 bytes) and give a plausible tile-sized output. Writes tools/gfx_extra.json.
Run after `make regen` (needs the gap report from decomp.py)."""
import os, re, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lzdec
ROOT = os.path.dirname(HERE)
rom = open(os.path.join(ROOT, 'rom/game.nes'), 'rb').read(); P = [rom[16 + i * 16384:16 + (i + 1) * 16384] for i in range(8)]
env = dict(os.environ, GAPS='400')
txt = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'decomp.py')], env=env, capture_output=True, text=True, cwd=ROOT).stdout
gaps = [(int(m.group(1)), int(m.group(2), 16), int(m.group(3), 16) + 1) for m in re.finditer(r'bank (\d) \$([0-9A-F]+)-\$([0-9A-F]+) \(', txt)]
rows = []
for b, s, e in gaps:
    if b == 7 or e - s < 24: continue
    for a in range(s, e - 8):
        try: d, end = lzdec.decompress(P[b], a - 0x8000)
        except Exception: continue
        end += 0x8000
        if e - end in (0, 1, 2) and 32 <= len(d) <= 4096 and len(d) % 8 == 0 and end - a >= 12:
            rows.append(dict(bank=b, src=a, end=end, insize=end - a, outsize=len(d)))
            break
json.dump(rows, open(os.path.join(HERE, 'gfx_extra.json'), 'w'), indent=1)
print(len(rows), 'extra LZ blocks found in gaps')
