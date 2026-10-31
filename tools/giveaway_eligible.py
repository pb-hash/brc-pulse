#!/usr/bin/env python3
"""Who can enter the BRC Works giveaway, from the public chain archive.

    python3 tools/fetch_archive.py archive
    python3 tools/giveaway_eligible.py archive <cutoff height> [out.json]

An address can enter if, at the cutoff block, either:
  - it held at least 50 BRC (one block reward), or
  - it was paid by a known mining pool (POOLS below) in the 30 days up to the cutoff block,
    so pool miners who haven't reached 50 BRC yet can enter too.
The cutoff block has already passed when the giveaway is announced, so nobody can split coins into
extra addresses afterwards, and a pool only pays for real mining.

Balances follow BrowserCoin's own state rules, exactly as "My BRC" does (tools/accounts.py):
transfers, locks, redeems, block rewards (50 BRC, halving every 210,000) plus fees. As a check,
every balance plus every coin still locked must add up to the coins mined so far.

The output lists the addresses sorted, with a fingerprint anyone can recompute:
    SHA-256("BRC Works giveaway eligible v1\\n" + addresses sorted, one per line)
the same fingerprint BRC Post and BRC Pulse compute (giveaway-core.js eligibleFingerprint).
"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from accounts import parse_txs, reward, COIN  # the same transaction reader and rules as "My BRC"

WINDOW = 30 * 24 * 3600
MIN_BALANCE = 50 * COIN
DEAD = '000000000000000000000000000000000000000000000000000000000000dead'
# Mining pools whose payouts count (the same addresses BRC Pulse names). Their own addresses can't enter.
POOLS = {
    'ff811ae0d83c0bde47bc10db95d1e869641d897975c1fe7fc61884efa6d5c698': 'Cryptec Pool',
    '89d081ad360f4ee55e704b449b6f4491619fa8bddf0c35eedaafa0b6a306b768': 'Tabpool',
}
RULE = ('Held at least 50 BRC at the cutoff block, or was paid by a known mining pool ('
        + ', '.join(sorted(POOLS.values())) + ') in the 30 days up to and including the cutoff block.')


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
    # First pass: block times, to find where the 30-day window starts.
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
    # Second pass: replay every balance up to the cutoff, and note pool payouts in the window.
    bal, locks, pool_paid, mined = {}, {}, set(), 0
    for b in blocks(src):
        h = int.from_bytes(b[0:4], 'big')
        if h > cutoff:
            break
        n = int.from_bytes(b[148:152], 'big')
        fees = 0
        for kind, x, raw in parse_txs(b, n, 152):
            if kind == 't':
                bal[x['frm']] = bal.get(x['frm'], 0) - x['amount'] - x['fee']
                bal[x['to']] = bal.get(x['to'], 0) + x['amount']
                fees += x['fee']
                if h >= start and x['frm'] in POOLS and x['amount'] > 0:
                    pool_paid.add(x['to'])
            elif kind == 'l':
                bal[x['frm']] = bal.get(x['frm'], 0) - x['amount'] - x['fee']
                fees += x['fee']
                locks[hashlib.sha256(raw).hexdigest()] = x['amount']
            elif kind == 'r':
                amount = locks.pop(x['lock'], 0)
                bal[x['to']] = bal.get(x['to'], 0) + amount - x['fee']
                fees += x['fee']
        miner = b[116:148].hex()
        bal[miner] = bal.get(miner, 0) + reward(h) + fees
        mined += reward(h)
    # Every coin is in a balance or a lock: if not, the archive or this replay is wrong.
    assert sum(bal.values()) + sum(locks.values()) == mined, 'balances do not add up to the coins mined'
    assert min(bal.values()) >= 0, 'a balance went below zero'
    rich = {a for a, v in bal.items() if v >= MIN_BALANCE}
    got = (rich | pool_paid) - {DEAD, *POOLS}
    addresses = sorted(got)
    result = {
        'v': 2,
        'rule': RULE,
        'cutoff': cutoff, 'cutoffTime': cutoff_ts, 'fromHeight': start, 'fromTime': times[start],
        'minBalance': MIN_BALANCE, 'pools': POOLS,
        'byBalance': len(rich - {DEAD, *POOLS}), 'byPoolPayout': len(pool_paid - rich - {DEAD, *POOLS}),
        'count': len(addresses), 'fingerprint': fingerprint(addresses), 'addresses': addresses,
    }
    text = json.dumps(result, indent=1)
    if out:
        open(out, 'w').write(text + '\n')
    print(f'{len(addresses)} eligible addresses at block {cutoff} ({result["byBalance"]} holding 50+ BRC, '
          f'{result["byPoolPayout"]} more paid by a pool since block {start}), fingerprint {result["fingerprint"]}', file=sys.stderr)
    if not out:
        print(text)


if __name__ == '__main__':
    main()
