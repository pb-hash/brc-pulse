#!/usr/bin/env python3
"""Who can enter the BRC Works giveaway: every address that received BRC in the 30 days up to a cutoff block.

    python3 tools/fetch_archive.py archive
    python3 tools/giveaway_eligible.py archive <cutoff height> [out.json]

"Received BRC" means any of: mined a block (block reward), was paid in a transfer, or was paid out of a
hash-locked payment (redeem). The window is every block from the cutoff block back to 30 days (by block
time) before it. The output lists the addresses sorted, with a fingerprint that anyone can recompute:

    SHA-256("BRC Works giveaway eligible v1\\n" + addresses sorted, one per line)

This is the same fingerprint BRC Seal and BRC Pulse compute (giveaway-core.js eligibleFingerprint), so the
published list can be rebuilt from the public chain archive and checked line for line.
"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from accounts import parse_txs  # the same transaction reader as "My BRC"

WINDOW = 30 * 24 * 3600
DEAD = '000000000000000000000000000000000000000000000000000000000000dead'


def blocks(src):
    files = sorted(f for f in os.listdir(src) if f.endswith('.json') and f[0].isdigit())
    for f in files:
        for hx in json.load(open(os.path.join(src, f)))['blocks']:
            yield bytes.fromhex(hx)


def fingerprint(addresses):
    return hashlib.sha256(('BRC Works giveaway eligible v1\n' + '\n'.join(sorted(set(addresses)))).encode()).hexdigest()


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, cutoff = sys.argv[1], int(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else None
    # First pass: block times, to find where the window starts.
    times = {}
    for b in blocks(src):
        h = int.from_bytes(b[0:4], 'big')
        if h > cutoff:
            break
        times[h] = int.from_bytes(b[100:108], 'big')
    if cutoff not in times:
        raise SystemExit(f'block {cutoff} is not in the archive yet (archive ends at {max(times) if times else 0})')
    cutoff_ts = times[cutoff]
    start = min(h for h, t in times.items() if t >= cutoff_ts - WINDOW)
    # Second pass: everyone who received BRC in the window.
    got = set()
    locks = {}
    for b in blocks(src):
        h = int.from_bytes(b[0:4], 'big')
        if h > cutoff:
            break
        n = int.from_bytes(b[148:152], 'big')
        inside = h >= start
        for kind, x, raw in parse_txs(b, n, 152):
            if kind == 'l':
                locks[hashlib.sha256(raw).hexdigest()] = x['amount']
            elif kind == 't' and inside and x['amount'] > 0:
                got.add(x['to'])
            elif kind == 'r':
                amount = locks.pop(x['lock'], 0)
                if inside and amount - x['fee'] > 0:
                    got.add(x['to'])
        if inside:
            got.add(b[116:148].hex())
    got.discard(DEAD)
    addresses = sorted(got)
    result = {
        'v': 1,
        'rule': 'Received BRC (block reward, transfer or redeem) in the 30 days up to and including the cutoff block.',
        'cutoff': cutoff, 'cutoffTime': cutoff_ts, 'fromHeight': start, 'fromTime': times[start],
        'count': len(addresses), 'fingerprint': fingerprint(addresses), 'addresses': addresses,
    }
    text = json.dumps(result, indent=1)
    if out:
        open(out, 'w').write(text + '\n')
    print(f'{len(addresses)} eligible addresses, blocks {start}-{cutoff}, fingerprint {result["fingerprint"]}', file=sys.stderr)
    if not out:
        print(text)


if __name__ == '__main__':
    main()
