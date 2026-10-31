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

    python3 build.py history.json --preview out.html --accounts site/a   # preview variant (no CSP, Google fonts,
                                                                        # a few sample My BRC addresses embedded)
    python3 build.py history.json --site _site          # the published site: page, preview image (My BRC index
                                                        # files are written into _site/a by tools/accounts.py)
"""
import base64, hashlib, json, os, re, shutil, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HELPERS = ['api1.browsercoin.org', 'api2.browsercoin.org', 'api1.cryptec.tech', 'api1.taitech.eu']
# drand quicknet relays (League of Entropy), for stamps' "made after" beacon. Signatures are checked in the page.
DRAND = ['drand.cloudflare.com', 'api.drand.sh', 'api2.drand.sh', 'api3.drand.sh']
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

    def opt(flag):
        if flag in args:
            i = args.index(flag); v = args[i + 1]; del args[i:i + 2]; return v
        return None
    preview, accounts, site = opt('--preview'), opt('--accounts'), opt('--site')
    give_path = opt('--giveaway') or os.path.join(HERE, 'giveaway', 'config.json')
    give = json.load(open(give_path)) if os.path.exists(give_path) else None
    hist = json.load(open(args[0] if args else 'history.json'))
    snap, probes = snapshot(hist)
    tpl = open(os.path.join(HERE, 'src', 'template.html')).read()
    # drand checking and the giveaway code, built from BRC Seal's src/drand-core.js and src/giveaway-core.js
    # (see vendor/README.txt).
    kit = open(os.path.join(HERE, 'vendor', 'brc-kit.js')).read().strip()
    tpl = tpl.replace('/*__DRAND__*/', kit + '\nvar BRCDrand = BRCKit.drand, BRCGiveaway = BRCKit.giveaway;')
    # Version (VERSION file) and a build code from the page's code alone, so it changes
    # whenever the code does and never because of the hourly data.
    version = open(os.path.join(HERE, 'VERSION')).read().strip()
    assert re.fullmatch(r'\d+\.\d+\.\d+(-test\.\d+)?', version), f'VERSION {version!r} is not like 1.2.3 or 1.2.3-test.4'
    build_id = hashlib.sha256(tpl.encode()).hexdigest()[:8]
    tpl = tpl.replace('<!--__VERSION__-->', version).replace('<!--__BUILD__-->', build_id)
    # The giveaway's settings (giveaway/config.json): addresses, times, published list fingerprints.
    tpl = tpl.replace('/*__GIVEAWAY__*/null', json.dumps(give, separators=(',', ':')))
    html = tpl.replace('/*__SNAPSHOT__*/null', json.dumps(snap, separators=(',', ':')))

    if preview and accounts:
        # Sample addresses for My BRC: the labelled pools and today's busiest miners.
        tally = {}
        for r in snap['rows']:
            tally[r[3]] = tally.get(r[3], 0) + 1
        picks = ['ff811ae0d83c0bde47bc10db95d1e869641d897975c1fe7fc61884efa6d5c698', '89d081ad360f4ee55e704b449b6f4491619fa8bddf0c35eedaafa0b6a306b768']
        picks += [snap['miners'][i] for i, _ in sorted(tally.items(), key=lambda kv: -kv[1])[:4] if snap['miners'][i] not in picks]
        sample = None
        for a in picks:
            shard = json.load(open(os.path.join(accounts, a[:3] + '.json')))
            if sample is None:
                sample = dict(h=shard['h'], t=shard['t'], d0=shard['d0'], hd=shard['hd'], hb=shard.get('hb'), a={})
            if a in shard['a']:
                sample['a'][a] = shard['a'][a]
        html = tpl.replace('/*__SNAPSHOT__*/null', json.dumps(dict(snap, accounts=sample), separators=(',', ':')))
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
    connect = ' '.join(f'https://{h}' for h in HELPERS + DRAND)
    if give and give.get('service'):
        svc = give['service']
        assert re.fullmatch(r'https://[a-z0-9.-]+', svc), 'giveaway service must be a bare https origin'
        connect += ' ' + svc
    head = '\n'.join([
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        '<!-- Only this page\'s own script runs, and it can only talk to the BrowserCoin helper servers, the drand beacon and the BRC Mailbox. -->',
        f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'sha256-{sha}\'; style-src \'unsafe-inline\'; '
        f'font-src data:; img-src data:; connect-src {connect} https://pb-hash.github.io; base-uri \'none\'; form-action \'none\'">',
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
    if site:
        os.makedirs(site, exist_ok=True)
        open(os.path.join(site, 'index.html'), 'w').write(html)
        open(os.path.join(site, '.nojekyll'), 'w').write('')
        shutil.copy(os.path.join(HERE, 'brand', 'brc-pulse-social.png'), os.path.join(site, 'og.png'))
        # The giveaway's published lists, next to the page (giveaway/eligible.json, giveaway/entries.json).
        gdir = os.path.join(HERE, 'giveaway')
        if os.path.isdir(gdir):
            os.makedirs(os.path.join(site, 'giveaway'), exist_ok=True)
            for f in os.listdir(gdir):
                if f.endswith('.json') and f != 'config.json':
                    shutil.copy(os.path.join(gdir, f), os.path.join(site, 'giveaway', f))
    os.makedirs(os.path.join(HERE, 'dist'), exist_ok=True)
    open(os.path.join(HERE, 'dist', 'brc-pulse.html'), 'w').write(html)
    digest = hashlib.sha256(html.encode()).hexdigest()
    open(os.path.join(HERE, 'dist', 'SHA256.txt'), 'w').write(f'{digest}  brc-pulse.html\n')
    print('tip', snap['tip'], 'from', snap['source'], 'helpers', [(p['host'], p['ok']) for p in probes], 'bytes', len(html), 'sha256', digest)


if __name__ == '__main__':
    main()
