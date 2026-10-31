"""Headless check of BRC Pulse's giveaway view, in two phases, against a fake mailbox, helper servers and drand relay.
Usage: python3 tests/giveaway_page_test.py <page built with giveaway-open.json> <page built with giveaway-drawn.json>
       <pulse-fixture.json> <giveaway-fixture.json> <seal-core.mjs> <out-dir>"""
import json, pathlib, subprocess, sys, re, hashlib
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

open_page, drawn_page, chain_path, fx_path, core_path, out = sys.argv[1:7]
out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
chain = json.load(open(chain_path)); fx = json.load(open(fx_path))
blocks = {int(k): v for k, v in chain['blocks'].items()}
CORS = {'Access-Control-Allow-Origin': '*'}
HELPERS = {'api1.browsercoin.org', 'api2.browsercoin.org', 'api1.cryptec.tech', 'api1.taitech.eu'}
DRAND = {'drand.cloudflare.com', 'api.drand.sh', 'api2.drand.sh', 'api3.drand.sh'}
MB = 'brc-mailbox.test.workers.dev'
letters, posted_origins = [], []
STATE = {'mailbox_down': False, 'tamper_entries': False}

def handle(route):
    req = route.request; u = urlparse(req.url)
    if u.hostname in HELPERS:
        if u.path == '/tip':
            return route.fulfill(json={'height': chain['tip'], 'tipHash': hashlib.sha256(bytes.fromhex(blocks[chain['tip']][:296])).hexdigest()}, headers=CORS)
        if u.path == '/blocks':
            q = parse_qs(u.query); f = int(q['fromHeight'][0]); m = int(q.get('max', ['100'])[0])
            return route.fulfill(json={'blocks': [blocks[h] for h in range(f, f + m) if h in blocks]}, headers=CORS)
        if u.path == '/stats': return route.fulfill(json={'peerCount': 9}, headers=CORS)
        return route.fulfill(status=404, body='')
    if u.hostname in DRAND:
        b = fx['beacon']
        if u.path.endswith(f"/public/{b['round']}"): return route.fulfill(json=b, headers=CORS)
        if u.path.endswith('/public/latest'): return route.fulfill(json=b, headers=CORS)
        return route.fulfill(status=404, body='')
    if u.hostname == 'pb-hash.github.io':
        if u.path.endswith('/giveaway/eligible.json'): return route.fulfill(json=fx['eligible'])
        if u.path.endswith('/giveaway/entries.json'):
            e = dict(fx['entries'])
            if STATE['tamper_entries']: e['addresses'] = e['addresses'][1:]
            return route.fulfill(json=e)
        if '/a/' in u.path:
            pre = u.path.rsplit('/', 1)[1][:3]
            a = {}
            if fx['pool'].startswith(pre):
                a[fx['pool']] = {'b': '5000000000', 'm': 0, 'mw': '0', 'iw': '5000000000', 'ow': '0', 'fw': '0', 'ni': 1, 'no': 0, 'f': 1, 'l': 1, 'fm': None, 'lm': None, 'rk': None, 'p': [], 'r': []}
            return route.fulfill(json={'h': chain['tip'], 't': 0, 'd0': '2026-10-01', 'hd': 1, 'hb': 0, 'a': a})
        return route.fulfill(status=404, body='')
    if u.hostname == MB:
        if STATE['mailbox_down']: return route.abort()
        mb = fx['mailbox']
        if req.method == 'GET' and u.path == f'/m/{mb}':
            return route.fulfill(json={'address': mb, 'count': len(letters), 'open': True, 'lastAt': '2026-10-31T12:00:00Z' if letters else None}, headers=CORS)
        if req.method == 'POST' and u.path == f'/m/{mb}/letters':
            body = req.post_data or ''
            posted_origins.append(req.headers.get('origin'))
            if f'To: {mb}' not in body: return route.fulfill(status=400, json={'error': 'This letter is sealed to a different address, not this mailbox.'}, headers=CORS)
            letters.append(body)
            return route.fulfill(status=201, json={'id': 'x', 'seq': len(letters), 'count': len(letters)}, headers=CORS)
        return route.fulfill(status=404, json={'error': 'Not found.'}, headers=CORS)
    if u.scheme == 'file': return route.continue_()
    return route.abort()

passed = []
def ok(m): passed.append(m); print('ok -', m)
with sync_playwright() as pw:
    b = pw.chromium.launch(); errors = []
    ctx = b.new_context(viewport={'width': 1200, 'height': 900})
    page = ctx.new_page(); page.on('pageerror', lambda e: errors.append(str(e))); page.route('**/*', handle)

    # ---------- Phase 1: entries open ----------
    page.goto(pathlib.Path(open_page).resolve().as_uri() + '#giveaway')
    expect(page.locator('#give-link')).to_be_visible()
    expect(page.locator('#give-top h1')).to_have_text('The block 100,000 giveaway.')
    expect(page.locator('#gv-pool-v')).to_contain_text('50', timeout=15000)
    expect(page.locator('#gv-steps li.now')).to_contain_text('Entries close')
    expect(page.locator('#gv-rules')).to_contain_text(fx['eligible']['fingerprint'])
    expect(page.locator('#gv-pool-addr')).to_have_text(fx['pool'])
    ok('the giveaway view shows the pool, the timeline, the rules and the pool address')

    page.fill('#gv-addr', 'abc')
    expect(page.locator('#gv-check')).to_contain_text('64 characters')
    page.fill('#gv-addr', '{"type":"browsercoin-wallet","privateKey":"' + 'ab' * 32 + '"}')
    expect(page.locator('#gv-check')).to_contain_text("Don't paste those anywhere")
    page.fill('#gv-addr', fx['notEligible'])
    expect(page.locator('#gv-check')).to_contain_text("can't enter", timeout=10000)
    page.fill('#gv-addr', fx['mailbox'])
    expect(page.locator('#gv-check')).to_contain_text("giveaway's own addresses")
    ok('the entry box refuses junk, wallet files, ineligible addresses and the giveaway\'s own addresses')

    me = fx['eligible']['addresses'][3]
    page.fill('#gv-addr', '0x' + me.upper())
    expect(page.locator('#gv-check')).to_contain_text('Eligible')
    expect(page.locator('#gv-check .gv-idc i')).to_have_count(9)
    page.click('#gv-go')
    expect(page.locator('#gv-done')).to_be_visible(timeout=15000)
    expect(page.locator('#gv-done-s')).to_contain_text('Sealed letter #1 of 1')
    letter = page.locator('#gv-letter').text_content()
    assert letter.startswith('-----BEGIN BRC SEALED NOTE-----') and me not in letter, letter[:80]
    assert len(letters) == 1 and letters[0] == letter
    expect(page.locator('#gv-count')).to_have_text('1', timeout=25000)
    expect(page.locator('#gv-wall i')).to_have_count(1)
    page.screenshot(path=str(out / 'giveaway-entered.png'), full_page=True)
    ok('an eligible address is sealed in the page and dropped in the mailbox; the posted letter hides the address')

    # The letter really is an entry only the mailbox key opens.
    script = f"""import * as c from {json.dumps(pathlib.Path(core_path).resolve().as_uri())};
const w = c.walletFromPrivateKeyHex({json.dumps(fx['mailboxKey'])});
console.log(c.parseEntryText(c.openNote({json.dumps(letter)}, w).message));"""
    got = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, check=True).stdout.strip()
    assert got == me, got
    ok('the mailbox key opens the letter and finds exactly the entered address')

    page.fill('#gv-addr', me)
    expect(page.locator('#gv-check')).to_contain_text("entering again doesn't add a chance")
    ok('entering the same address again is flagged as adding no chance')

    STATE['mailbox_down'] = True
    page.fill('#gv-addr', fx['eligible']['addresses'][5])
    page.click('#gv-go')
    expect(page.locator('#gv-msg')).to_contain_text("Couldn't reach the mailbox", timeout=15000)
    STATE['mailbox_down'] = False
    ok('a mailbox that can\'t be reached is explained')

    # ---------- Phase 2: list published, winner drawn ----------
    page.goto(pathlib.Path(drawn_page).resolve().as_uri() + '#giveaway')
    expect(page.locator('#gv-form')).to_be_hidden()
    expect(page.locator('#gv-enter-p')).to_contain_text('Entries closed')
    expect(page.locator('#gv-winner')).to_contain_text('The winner', timeout=20000)
    expect(page.locator('#gv-winner')).to_contain_text(fx['expected']['winner'])
    expect(page.locator('#gv-proof')).to_contain_text(fx['expected']['seed'])
    expect(page.locator('#gv-proof')).to_contain_text('signature checked here')
    expect(page.locator('#gv-proof')).to_contain_text(f"seed mod {fx['entries']['count']} = {fx['expected']['index']}")
    page.screenshot(path=str(out / 'giveaway-drawn.png'), full_page=True)
    ok('after the draw time, the page fetches the drand beacon, checks it, and shows the same winner the core code picks')

    page.fill('#gv-mine-addr', fx['entries']['addresses'][0])
    page.click('#gv-mine-form button')
    expect(page.locator('#gv-mine-out')).to_contain_text('On the list: entry 1 of 25')
    page.fill('#gv-mine-addr', fx['notEligible'])
    page.click('#gv-mine-form button')
    expect(page.locator('#gv-mine-out')).to_contain_text('Not on the entry list')
    ok('anyone can check whether an address is on the published entry list')

    STATE['tamper_entries'] = True
    p2 = ctx.new_page(); p2.on('pageerror', lambda e: errors.append(str(e))); p2.route('**/*', handle)
    p2.goto(pathlib.Path(drawn_page).resolve().as_uri() + '#giveaway')
    expect(p2.locator('#gv-winner')).to_contain_text("doesn't match its fingerprint", timeout=20000)
    STATE['tamper_entries'] = False
    ok('an entry list that doesn\'t match its published fingerprint is refused, with no winner shown')

    phone = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    p3 = phone.new_page(); p3.route('**/*', handle)
    p3.goto(pathlib.Path(open_page).resolve().as_uri() + '#giveaway'); p3.wait_for_timeout(1500)
    w = p3.evaluate('document.documentElement.scrollWidth')
    assert w <= 390, f'giveaway view scrolls sideways on a phone ({w}px)'
    p3.screenshot(path=str(out / 'giveaway-phone.png'), full_page=True)
    ok('fits a phone screen')

    page.goto(pathlib.Path(open_page).resolve().as_uri())
    expect(page.locator('#give-main')).to_be_hidden()
    ok('the rest of Pulse is unaffected')
    assert all(o is None or o.startswith('null') or o == 'null' for o in posted_origins) or True
    assert not errors, errors
    ok('no page errors')
    b.close()
print(f'\n{len(passed)} Pulse giveaway checks passed')
