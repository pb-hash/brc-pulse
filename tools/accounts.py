#!/usr/bin/env python3
"""Replays the chain archive into per-address records for the "My BRC" page.

    python3 tools/accounts.py archive site/a

Follows BrowserCoin's own state rules (src/chain/state.ts):
  transfer  sender -= amount + fee, nonce += 1; recipient += amount
  lock      sender -= amount + fee, nonce += 1; amount parked under lockId = sha256(encoded lock tx)
  redeem    lock deleted; recipient += lock.amount - fee
  block     miner += 50 BRC (halving every 210,000) + sum of the block's fees
Amounts are integers in wei (1 BRC = 1e8 wei).

Also keeps each address's flows hour by hour for its whole history (mined, received, sent including fees),
so the page can show what changed over the last day, week, month or year and draw the balance over time.

Writes one JSON file per address prefix (first 3 hex characters, 4,096 shards), so the page downloads
only the shard for the address it is asked about. Every record carries its balance and nonce at the
archived height; the page then applies newer blocks itself from the live helper servers.
"""
import hashlib, json, os, sys, collections, datetime

COIN = 100_000_000
CHAIN = bytes.fromhex('c01dfeed')
LOCK, RDM1 = b'LOCK', b'RDM1'
DEAD = '000000000000000000000000000000000000000000000000000000000000dead'
PREFIX = 3
RECENT = 60          # most recent activity rows kept per address
DAYS = 30            # daily mined history kept per address


def reward(height):
    h = height // 210_000
    return 0 if h >= 64 else (50 * COIN) >> h


def parse_txs(b, n, off):
    """Yields (kind, fields, encoded bytes) for each tx in a block body."""
    for _ in range(n):
        tag = b[off:off + 4]
        if tag == CHAIN:
            raw = b[off:off + 152]
            yield 't', dict(frm=raw[4:36].hex(), to=raw[36:68].hex(), amount=int.from_bytes(raw[68:76], 'big'),
                            fee=int.from_bytes(raw[76:84], 'big'), nonce=int.from_bytes(raw[84:88], 'big')), raw
            off += 152
        elif tag == LOCK:
            raw = b[off:off + 156]
            yield 'l', dict(frm=raw[8:40].hex(), amount=int.from_bytes(raw[40:48], 'big'), fee=int.from_bytes(raw[48:56], 'big'),
                            nonce=int.from_bytes(raw[56:60], 'big')), raw
            off += 156
        elif tag == RDM1:
            p = off + 4
            lock_id = b[p:p + 32].hex(); p += 32
            to = b[p:p + 32].hex(); p += 32
            amount = int.from_bytes(b[p:p + 8], 'big'); p += 8
            fee = int.from_bytes(b[p:p + 8], 'big'); p += 8
            sl = int.from_bytes(b[p:p + 2], 'big'); p += 2 + sl
            wc = b[p]; p += 1
            for _ in range(wc):
                p += 2 + int.from_bytes(b[p:p + 2], 'big')
            yield 'r', dict(lock=lock_id, to=to, amount=amount, fee=fee), b[off:p]
            off = p
        else:
            raise SystemExit(f'unknown transaction type {tag.hex()}')


def new():
    return dict(bal=0, nonce=0, mined=0, minedWei=0, inWei=0, outWei=0, feeWei=0, nIn=0, nOut=0,
                first=None, last=None, firstMined=None, lastMined=None, recent=collections.deque(maxlen=RECENT),
                days=collections.Counter(), payers=collections.Counter(), hours=collections.defaultdict(lambda: [0, 0, 0]))


def main():
    src, out = sys.argv[1], sys.argv[2]
    files = sorted(f for f in os.listdir(src) if f.endswith('.json') and f[0].isdigit())
    A = collections.defaultdict(new)
    locks = {}
    height = ts = 0
    supply = 0
    base_hour = None

    def touch(addr, h):
        a = A[addr]
        if a['first'] is None: a['first'] = h
        a['last'] = h
        return a

    for f in files:
        for hx in json.load(open(os.path.join(src, f)))['blocks']:
            b = bytes.fromhex(hx)
            h = int.from_bytes(b[0:4], 'big'); t = int.from_bytes(b[100:108], 'big'); miner = b[116:148].hex()
            n = int.from_bytes(b[148:152], 'big')
            if h != height + 1 and not (h == 1 and height == 0):
                raise SystemExit(f'archive gap before block {h}')
            height, ts = h, t
            fees = 0
            for kind, x, raw in parse_txs(b, n, 152):
                fees += x['fee']
                if kind in 'tl':
                    s = touch(x['frm'], h)
                    if s['nonce'] != x['nonce']:
                        raise SystemExit(f'nonce mismatch at {h} for {x["frm"]}')
                    s['bal'] -= x['amount'] + x['fee']; s['nonce'] += 1
                    s['outWei'] += x['amount']; s['feeWei'] += x['fee']; s['nOut'] += 1
                    s['hours'][t // 3600][2] += x['amount'] + x['fee']
                    if s['bal'] < 0:
                        raise SystemExit(f'negative balance at {h} for {x["frm"]}')
                    if kind == 't':
                        r = touch(x['to'], h)
                        r['bal'] += x['amount']; r['inWei'] += x['amount']; r['nIn'] += 1
                        r['hours'][t // 3600][1] += x['amount']
                        r['payers'][x['frm']] += x['amount']
                        s['recent'].append([h, t, 'out', x['to'], x['amount'], x['fee']])
                        r['recent'].append([h, t, 'in', x['frm'], x['amount'], 0])
                    else:
                        locks[hashlib.sha256(raw).hexdigest()] = x['amount']
                        s['recent'].append([h, t, 'lock', '', x['amount'], x['fee']])
                else:
                    amount = locks.pop(x['lock'])
                    pay = amount - x['fee']
                    r = touch(x['to'], h)
                    if pay > 0:
                        r['bal'] += pay; r['inWei'] += pay; r['nIn'] += 1
                        r['hours'][t // 3600][1] += pay
                    r['recent'].append([h, t, 'redeem', '', pay, 0])
            m = touch(miner, h)
            got = reward(h) + fees
            supply += reward(h)
            m['bal'] += got; m['mined'] += 1; m['minedWei'] += got
            m['hours'][t // 3600][0] += got
            if base_hour is None: base_hour = t // 3600
            if m['firstMined'] is None: m['firstMined'] = h
            m['lastMined'] = h
            m['days'][datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%d')] += 1

    total = sum(a['bal'] for a in A.values()) + sum(locks.values())
    if total != supply:
        raise SystemExit(f'supply check failed: balances {total} != mined {supply}')

    today = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date()
    span = [(today - datetime.timedelta(days=i)).isoformat() for i in range(DAYS - 1, -1, -1)]
    ranked = sorted((a['bal'], k) for k, a in A.items())
    rank = {k: len(ranked) - i for i, (_, k) in enumerate(ranked)}
    holders = sum(1 for a in A.values() if a['bal'] > 0)
    shards = collections.defaultdict(dict)
    for k, a in A.items():
        rec = dict(b=str(a['bal']), n=a['nonce'], m=a['mined'], mw=str(a['minedWei']), iw=str(a['inWei']), ow=str(a['outWei']),
                   fw=str(a['feeWei']), ni=a['nIn'], no=a['nOut'], f=a['first'], l=a['last'], fm=a['firstMined'], lm=a['lastMined'],
                   rk=rank[k], d=[a['days'].get(d, 0) for d in span] if a['mined'] else None,
                   p=[[p, str(w)] for p, w in a['payers'].most_common(3)],
                   r=[[h, t, kind, cp, str(w), str(fe)] for h, t, kind, cp, w, fe in reversed(a['recent'])],
                   # hourly flows: [hours since hb, mined, received, sent + fees], wei (all below 2^53)
                   x=[[hr - base_hour, *v] for hr, v in sorted(a['hours'].items())])
        shards[k[:PREFIX]][k] = rec
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):
        if name.endswith('.json'): os.remove(os.path.join(out, name))
    size = 0
    for p, recs in shards.items():
        s = json.dumps(dict(h=height, t=ts, d0=span[0], hd=holders, hb=base_hour, a=recs), separators=(',', ':'))
        open(os.path.join(out, p + '.json'), 'w').write(s); size += len(s)
    meta = dict(h=height, t=ts, days=span, holders=holders, addresses=len(A),
                supply=str(supply), locked=str(sum(locks.values())), prefix=PREFIX)
    open(os.path.join(out, 'meta.json'), 'w').write(json.dumps(meta, separators=(',', ':')))
    print('height', height, 'addresses', len(A), 'holders', meta['holders'], 'shards', len(shards), 'bytes', size,
          'largest shard', max(len(json.dumps(dict(a=r))) for r in shards.values()), 'supply check ok')


if __name__ == '__main__':
    main()
