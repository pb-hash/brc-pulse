#!/usr/bin/env python3
"""Bitcoin figures for BRC Pulse's estimated value, fetched when the site is built.

    python3 tools/btc.py btc.json

Writes Bitcoin's price (USD), mining difficulty, block height and block subsidy now, plus one row a day
since the Sandglass fork (Jul 22, 2026): [date, average USD price that day, difficulty in effect at noon UTC,
subsidy]. Everything comes from mempool.space's public API, at build time only, so visitors' browsers
never contact it. If mempool.space can't be reached the build falls back to data/btc.json (a copy committed
with each release) and the page says how old the figures are.
"""
import datetime as dt, json, sys, time, urllib.request

API = 'https://mempool.space/api'
SINCE = '2026-07-22'   # the Sandglass fork: BrowserCoin's current hash, the one the energy figures describe


def get(path, timeout=30):
    req = urllib.request.Request(API + path, headers={'User-Agent': 'brc-pulse-build'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def subsidy(height):
    halvings = height // 210000
    return 50 / 2 ** halvings if halvings < 64 else 0


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else 'btc.json'
    prices = sorted((p['time'], p['USD']) for p in get('/v1/historical-price?currency=USD')['prices'] if p.get('USD'))
    adj = sorted((a[0], a[1], a[2]) for a in get('/v1/mining/difficulty-adjustments/1y'))   # [time, height, difficulty]
    height = int(get('/blocks/tip/height'))
    hr = get('/v1/mining/hashrate/3d')
    diff = float(hr['currentDifficulty'])
    usd_at, usd = prices[-1]
    assert usd > 1000 and diff > 1e12 and height > 900000, 'Bitcoin figures look wrong'

    days, d = [], dt.date.fromisoformat(SINCE)
    today = dt.datetime.now(dt.timezone.utc).date()
    while d < today:
        t0 = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())
        day_prices = [p for t, p in prices if t0 <= t < t0 + 86400]
        if not day_prices:   # older prices are daily or weekly: take the nearest one before the day ends
            before = [p for t, p in prices if t < t0 + 86400]
            day_prices = before[-1:]
        noon = t0 + 43200
        at_noon = [a for a in adj if a[0] <= noon]
        if day_prices and at_noon:
            _, h, df = at_noon[-1]
            days.append([d.isoformat(), round(sum(day_prices) / len(day_prices), 2), df, subsidy(h)])
        d += dt.timedelta(days=1)

    out = dict(at=int(time.time() * 1000), src='mempool.space', usd=usd, usdAt=usd_at * 1000, diff=diff,
               height=height, subsidy=subsidy(height), days=days)
    json.dump(out, open(out_path, 'w'), separators=(',', ':'))
    print('btc', out_path, 'usd', usd, 'difficulty', f'{diff:.4g}', 'height', height, 'days', len(days))


if __name__ == '__main__':
    main()
