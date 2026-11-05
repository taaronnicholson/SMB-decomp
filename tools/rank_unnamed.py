#!/usr/bin/env python3
"""List the most-called routines and most-used RAM symbols that still have address-based names (for the naming pass)."""
import re, collections, glob, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
calls = collections.Counter(); ram = collections.Counter()
for f in glob.glob(os.path.join(ROOT, 'src/*.s')):
    for l in open(f):
        m = re.match(r'^\s+(JSR|JMP) ((?:F|B\d)_[0-9A-F]{4})\b', l)
        if m: calls[m.group(2)] += 1
        for r in re.findall(r'\b(zp_[0-9A-F]{2}|ram_[0-9A-F]{4})\b', l): ram[r] += 1
n = int(os.environ.get('N', '40'))
print('routines:', ', '.join(f'{k}:{v}' for k, v in calls.most_common(n)))
print('RAM:', ', '.join(f'{k}:{v}' for k, v in ram.most_common(n)))
print(len(calls), 'unnamed routines referenced;', len(ram), 'unnamed RAM symbols')
