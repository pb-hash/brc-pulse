#!/usr/bin/env python3
"""Recompute the BRC Works block 100,000 giveaway winner yourself. Python 3 only, nothing to install.

    python3 check_draw.py                  # after Fri Nov 13, 2026, 18:00 UTC
    python3 check_draw.py entries.json     # with a copy of the list you saved yourself

It fetches the published entry list and drand's beacon for the draw round from two drand relays run by
different operators, checks the list against the fingerprint fixed on the chain, and prints the winner.
(BRC Pulse also checks drand's BLS signature; that needs a crypto library, so here two relays must agree.)
"""
import hashlib, json, sys, urllib.request

FINGERPRINT = 'ad6fee323340c04975b2fb1781f087c950b45f509118486a2b6a345d04337202'  # signed on the chain, block 99,670
ROUND = 33929812                                                                   # signed on the chain, block 93,319
LIST = 'https://pb-hash.github.io/brc-pulse/giveaway/entries.json'
QUICKNET = '52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971'
RELAYS = ['https://api.drand.sh', 'https://drand.cloudflare.com']
sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
get = lambda url: json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'check_draw.py'}), timeout=20))

data = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else get(LIST)
entries = sorted(set(data['addresses']))
assert sha('BRC Works giveaway list v1\n' + '\n'.join(entries)) == FINGERPRINT, 'list does not match the fingerprint on the chain'
try:
    sigs = {get(f'{r}/{QUICKNET}/public/{ROUND}')['signature'] for r in RELAYS}
except urllib.error.HTTPError as e:
    sys.exit('drand has not published the draw round yet: it comes out Fri Nov 13, 2026, 18:00 UTC' if e.code == 425 else e)
assert len(sigs) == 1, 'the drand relays disagree'
sig = sigs.pop()
seed = sha(f'BRC Works giveaway draw v1\n{FINGERPRINT}\n{ROUND}\n{sig}')
i = int(seed, 16) % len(entries)
print(f'{len(entries)} entries, list matches the chain\ndrand round {ROUND} signature {sig}\nseed {seed}')
print(f'winner: position {i + 1} of {len(entries)} in sorted order\n{entries[i]}')
