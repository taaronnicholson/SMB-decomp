#!/usr/bin/env python3
"""Find LZ blocks in the unclassified gaps: try the decoder at every offset inside each gap and keep starts that decode cleanly,
end exactly at the end of the gap (within 2 bytes) and give a plausible tile-sized output. Appends to tools/gfx_extra.json.
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
def try_decode(b, a, limit):
    try: d, end = lzdec.decompress(P[b], a - 0x8000)
    except Exception: return None
    end += 0x8000
    if end > limit or not (32 <= len(d) <= 4096 and len(d) % 8 == 0 and end - a >= 12): return None
    return d, end
for b, s, e in gaps:
    if b == 7 or e - s < 24: continue
    # chains: blocks separated by at most 2 padding bytes; accept when the last one ends within 2 bytes of the end of the gap
    for a0 in range(s, min(s + 4, e - 8)):
        chain = []; pos = a0
        while True:
            hit = None
            for skip in (0, 1, 2):
                r = try_decode(b, pos + skip, e)
                if r: hit = (pos + skip, r); break
            if not hit: break
            a, (d, end) = hit; chain.append(dict(bank=b, src=a, end=end, insize=end - a, outsize=len(d))); pos = end
            if e - pos <= 2: break
        if chain and e - chain[-1]['end'] in (0, 1, 2):
            rows += chain; break
ep = os.path.join(HERE, 'gfx_extra.json')
old = json.load(open(ep)) if os.path.exists(ep) else []          # keep blocks found earlier (they are no longer in the gaps)
have = {(r['bank'], r['src']) for r in old}
merged = sorted(old + [r for r in rows if (r['bank'], r['src']) not in have], key=lambda r: (r['bank'], r['src']))
json.dump(merged, open(ep, 'w'), indent=1)
print(len(merged), 'extra LZ blocks (', len(merged) - len(old), 'new )')
