#!/usr/bin/env python3
"""Builds BRC Pulse: one self-contained HTML page.

    python3 tools/fetch_archive.py archive          # download the chain archive (cached)
    python3 tools/history.py archive history.json   # daily history since launch
    python3 build.py history.json                   # writes dist/ and docs/

The page embeds a fresh snapshot of the last 800 blocks and the daily history, so it shows real data
even before it connects. Once open, it reads the public helper API directly from the browser.
The published page carries a Content-Security-Policy: its own script only (pinned by SHA-256), fonts
embedded in the page, and network access limited to the four helper servers. No analytics, no cookies,
no third-party requests.

    python3 build.py history.json --preview out.html   # variant without CSP, fonts from Google, for previews
"""
import base64, hashlib, json, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HELPERS = ['api1.browsercoin.org', 'api2.browsercoin.org', 'api1.cryptec.tech', 'api1.taitech.eu']
SITE = 'https://pb-hash.github.io/brc-pulse/'
DESC = 'BrowserCoin, beat by beat: the latest block, who is mining, a mining calculator, pools, helper servers and history since launch.'


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'brc-pulse-build'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def decode(h):
    return dict(h=int(h[0:8], 16), ts=int(h[200:216], 16), bits=int(h[216:224], 16), miner=h[232:296], ntx=int(h[296:304], 16))


def probe():
    out = []
    for host in HELPERS:
        t0 = time.time()
        try:
            r = get(f'https://{host}/tip', timeout=8)
            out.append(dict(host=host, ok=True, ms=round((time.time() - t0) * 1000), height=r['height']))
        except urllib.error.HTTPError as e:
            out.append(dict(host=host, ok=False, error=f'HTTP {e.code}'))
        except Exception:
            out.append(dict(host=host, ok=False, error='No response'))
    return out


def snapshot(hist):
    probes = probe()
    up = sorted((p for p in probes if p['ok']), key=lambda p: (-p['height'], p['ms']))
    if not up:
        sys.exit('no helper server answered')
    api = 'https://' + up[0]['host']
    tip, stats = get(api + '/tip'), get(api + '/stats')
    H = tip['height']
    rows = {}
    f = max(1, H - 799)
    while f <= H:
        for hx in get(f'{api}/blocks?fromHeight={f}&max=200')['blocks']:
            d = decode(hx); rows[d['h']] = d
        f += 200
    miners, idx, out_rows = [], {}, []
    for d in (rows[k] for k in sorted(rows)):
        if d['miner'] not in idx:
            idx[d['miner']] = len(miners); miners.append(d['miner'])
        out_rows.append([d['h'], d['ts'], d['bits'], idx[d['miner']], d['ntx']])
    days = hist['days'][:-1]  # the last archived day is partial
    return dict(
        at=int(time.time() * 1000), source=up[0]['host'], tip=H,
        stats=dict(peerCount=stats.get('peerCount'), minersActive=stats.get('minersActive')),
        mempool=0, miners=miners, rows=out_rows, helpers=probes,
        history=dict(days=[[d['d'], d['blocks'], d['hr'], d['miners'], d['top'], d['tx']] for d in days],
                     archivedHeight=hist['archivedHeight'], burnedWei=str(hist['burned']), tx=hist['tx'],
                     locks=hist['locks'], redeems=hist['redeems'], minersEver=hist['minersEver'])), probes


def font_face(family, path, weights):
    b64 = base64.b64encode(open(os.path.join(HERE, path), 'rb').read()).decode()
    return (f'@font-face {{ font-family: "{family}"; font-style: normal; font-weight: {weights}; font-display: swap; '
            f'src: url(data:font/woff2;base64,{b64}) format("woff2"); }}')


def main():
    args = sys.argv[1:]
    preview = None
    if '--preview' in args:
        i = args.index('--preview'); preview = args[i + 1]; del args[i:i + 2]
    hist = json.load(open(args[0] if args else 'history.json'))
    snap, probes = snapshot(hist)
    tpl = open(os.path.join(HERE, 'src', 'template.html')).read()
    html = tpl.replace('/*__SNAPSHOT__*/null', json.dumps(snap, separators=(',', ':')))

    if preview:
        fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                 '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400..700&family=Geist+Mono:wght@400;500&family=Manrope:wght@400..800&display=swap">')
        out = html.replace('<!--__FONTS__-->', fonts).replace('<!--__HEAD__-->\n', '')
        open(preview, 'w').write(out)
        print('preview', preview, len(out))
        return

    # Fonts © The Manrope Project Authors and © Vercel (Geist), SIL Open Font License 1.1, see fonts/.
    fonts = '<style>\n' + '\n'.join([
        font_face('Manrope', 'fonts/Manrope-Variable.subset.woff2', '200 800'),
        font_face('Geist', 'fonts/Geist-Variable.subset.woff2', '100 900'),
        font_face('Geist Mono', 'fonts/GeistMono-Variable.subset.woff2', '100 900'),
    ]) + '\n</style>'
    html = html.replace('<!--__FONTS__-->', fonts)
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    assert len(scripts) == 1, 'expected exactly one inline script'
    sha = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
    connect = ' '.join(f'https://{h}' for h in HELPERS)
    head = '\n'.join([
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        '<!-- Only this page\'s own script runs, and it can only talk to the BrowserCoin helper servers. -->',
        f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'sha256-{sha}\'; style-src \'unsafe-inline\'; '
        f'font-src data:; img-src data:; connect-src {connect}; base-uri \'none\'; form-action \'none\'">',
        '<meta name="referrer" content="no-referrer">',
        '<meta name="theme-color" content="#f5f6f8">',
        '<meta property="og:type" content="website">',
        '<meta property="og:title" content="BRC Pulse">',
        f'<meta property="og:description" content="{DESC}">',
        f'<meta property="og:url" content="{SITE}">',
        f'<meta property="og:image" content="{SITE}og.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]) + '\n'
    html = '<!doctype html>\n<html lang="en">\n' + html.replace('<!--__HEAD__-->\n', head)
    for p in ('dist/brc-pulse.html', 'docs/index.html'):
        open(os.path.join(HERE, p), 'w').write(html)
    digest = hashlib.sha256(html.encode()).hexdigest()
    open(os.path.join(HERE, 'dist', 'SHA256.txt'), 'w').write(f'{digest}  brc-pulse.html\n')
    print('tip', snap['tip'], 'from', snap['source'], 'helpers', [(p['host'], p['ok']) for p in probes], 'bytes', len(html), 'sha256', digest)


if __name__ == '__main__':
    main()
