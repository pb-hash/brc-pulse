"""Headless check of BRC Pulse's "Check a stamp" view against a simulated chain.
Usage: python3 tests/stamp_page_test.py dist/brc-pulse.html <pulse-fixture.json from brc-seal test/pulse-fixture.mjs> <out-dir>"""
import json, pathlib, sys, re
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

page_path, fx_path, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
fx = json.load(open(fx_path))
blocks = {int(k): v for k, v in fx['blocks'].items()}
FAKE_DRAND = {'on': False}
DRAND_HOSTS = {'drand.cloudflare.com', 'api.drand.sh', 'api2.drand.sh', 'api3.drand.sh'}
HELPERS = {'api1.browsercoin.org', 'api2.browsercoin.org', 'api1.cryptec.tech', 'api1.taitech.eu'}
calls = []
LIAR = {'host': None, 'mode': None}
DOWN = set()
CORS = {'Access-Control-Allow-Origin': '*'}
def handle(route):
    u = urlparse(route.request.url)
    if u.hostname in DOWN: return route.abort()
    if u.hostname in DRAND_HOSTS:
        if u.path.endswith('/public/latest'):
            b = dict(fx['beacon'], round=fx['beacon']['round'] + 1) if FAKE_DRAND['on'] else fx['beacon']
            return route.fulfill(json=b, headers=CORS)
        return route.fulfill(status=404, body='')
    if u.hostname in HELPERS:
        calls.append(u.path + '?' + u.query)
        inflate = LIAR['mode'] == 'inflate' and u.hostname == LIAR['host']
        if u.path == '/tip':
            import hashlib
            if inflate: return route.fulfill(json={'height': 99999, 'tipHash': hashlib.sha256(bytes.fromhex(fx['fakeBlock'][:296])).hexdigest()}, headers=CORS)
            tiphash = hashlib.sha256(bytes.fromhex(blocks[fx['tip']][:296])).hexdigest()
            return route.fulfill(json={'height': fx['tip'], 'tipHash': tiphash}, headers=CORS)
        if u.path == '/blocks':
            q = parse_qs(u.query); f = int(q['fromHeight'][0]); m = int(q.get('max', ['100'])[0])
            out = []
            for h in range(f, f + m):
                if inflate and h == 99999: out.append(fx['fakeBlock'])
                elif h in blocks:
                    if LIAR['mode'] == 'fork' and u.hostname == LIAR['host'] and h == 92510:
                        out.append('0001695e' + blocks[92509][8:])  # a different block claiming height 92,510
                    else: out.append(blocks[h])
            return route.fulfill(json={'blocks': out}, headers=CORS)
        if u.path == '/stats':
            return route.fulfill(json={'peerCount': 9}, headers=CORS)
        return route.fulfill(status=404, body='')
    if u.scheme == 'file': return route.continue_()
    return route.abort()

passed = []
def ok(m): passed.append(m); print('ok -', m)
with sync_playwright() as pw:
    b = pw.chromium.launch()
    page = b.new_page(viewport={'width': 1200, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route('**/*', handle)
    page.goto(pathlib.Path(page_path).resolve().as_uri() + '#stamp')
    expect(page.locator('#stamp-top h1')).to_be_visible()
    expect(page.locator('#stamp-latest-h')).to_have_text('Block 92,524', timeout=15000)  # tip 92,530 minus 6
    expect(page.locator('#stamp-drand-h')).to_contain_text('Round 33,522,523, Oct 30, 2026, 2:35:33 PM UTC', timeout=15000)
    ok('#stamp opens the Check a stamp view and shows the latest drand beacon (signature checked) and a settled block for new stamps')

    page.fill('#stamp-receipt', fx['receipt'])
    page.locator('#stamp-file').set_input_files({'name': 'lease-v3.txt', 'mimeType': 'text/plain', 'buffer': bytes.fromhex(fx['fileHex'])})
    expect(page.locator('#stamp-file-name')).to_have_text('lease-v3.txt')
    page.click('#stamp-go')
    expect(page.locator('#stamp-result')).to_be_visible(timeout=20000)
    v = page.locator('#stamp-verdict')
    expect(v).to_have_class(re.compile('good'))
    expect(v).to_contain_text('Existed by')
    expect(v).to_contain_text('The stamp was made after Oct 30, 2026, 2:35:33 PM UTC')
    expect(page.locator('#stamp-facts')).to_contain_text('Stamp made after (drand)')
    expect(page.locator('#stamp-facts')).to_contain_text('signature checked')
    facts = page.locator('#stamp-facts')
    expect(facts).to_contain_text('92,510')
    expect(v).to_contain_text('it may be older')
    expect(facts).to_contain_text('Matches the receipt exactly')
    expect(page.locator('#stamp-facts')).to_contain_text('Block 92,500')
    expect(page.locator('#stamp-updated pre')).to_contain_text('Block: 92510')
    expect(facts).to_contain_text('3 independent operators agree')
    page.screenshot(path=str(out / 'pulse-stamp-good.png'), full_page=True)
    ok('finds the lock by searching recent blocks, dates it, checks the after-block and the file')

    fixed = page.locator('#stamp-updated pre').inner_text()
    n0 = len(calls)
    page.fill('#stamp-receipt', fixed)
    page.click('#stamp-go')
    expect(v).to_have_class(re.compile('good'), timeout=20000)
    page_calls = [c for c in calls[n0:] if c.startswith('/blocks') and 'max=200' in c]
    assert not page_calls, f'a receipt with Block: should not scan, got {page_calls}'
    ok('a receipt with its block number is checked with no searching')

    page.locator('#stamp-file').set_input_files({'name': 'lease-v4.txt', 'mimeType': 'text/plain', 'buffer': bytes.fromhex(fx['fileHex']).replace(b'3', b'4')})
    expect(page.locator('#stamp-file-name')).to_have_text('lease-v4.txt')
    page.click('#stamp-go')
    expect(v).to_have_class(re.compile('bad'), timeout=20000)
    expect(facts).to_contain_text("Doesn't match")
    ok('a changed file is flagged')

    page.fill('#stamp-receipt', fx['edited'])
    page.click('#stamp-go')
    expect(v).to_contain_text('holds a different stamp', timeout=20000)
    ok('an edited receipt is caught')

    page.fill('#stamp-receipt', fx['missing'])
    page.click('#stamp-go')
    expect(v).to_contain_text("isn't on the chain", timeout=30000)
    ok('with an After line, the whole range since that block is searched and a missing lock is reported')

    page.fill('#stamp-receipt', fx['fakeReceiptNoBlock'])  # not on the honest chain, no After line
    page.click('#stamp-go')
    expect(v).to_contain_text("isn't in the last 8,000 blocks", timeout=30000)
    expect(page.locator('#stamp-older')).to_be_visible()
    ok('without an After line, a lock not in recent blocks is reported, with a way to search older blocks')

    page.fill('#stamp-receipt', fx['badDrand'])
    page.click('#stamp-go')
    expect(page.locator('#stamp-msg')).to_contain_text('drand beacon is not genuine')
    ok('a receipt with a forged drand beacon is refused')

    page.fill('#stamp-receipt', 'hello')
    page.click('#stamp-go')
    expect(page.locator('#stamp-msg')).to_contain_text('not a BRC stamp receipt')
    ok('a paste that is not a receipt is explained')

    page.locator('#stamp-file').set_input_files({'name': 'lease-v3.txt', 'mimeType': 'text/plain', 'buffer': bytes.fromhex(fx['fileHex'])})
    expect(page.locator('#stamp-file-name')).to_have_text('lease-v3.txt')
    for liar in sorted(HELPERS):  # whichever helper the page picks first, one run makes it the liar
        LIAR.update(host=liar, mode='fork')
        page.fill('#stamp-receipt', fixed)
        page.click('#stamp-go')
        expect(v).to_contain_text('Helper servers disagree', timeout=20000)
    LIAR.update(host=None, mode=None)
    ok('a helper server reporting a different block is caught, whether or not it is the one the page reads from')

    LIAR.update(host='api1.taitech.eu', mode='inflate')
    for rc in (fx['fakeReceipt'], fx['fakeReceiptNoBlock']):
        page.fill('#stamp-receipt', rc)
        page.click('#stamp-go')
        expect(page.locator('#stamp-result')).to_be_visible(timeout=30000)
        expect(v).not_to_have_class(re.compile('good'))
        expect(v).not_to_contain_text('Existed by')
    LIAR.update(host=None, mode=None)
    ok('a lying helper that claims a higher tip and invents a block cannot produce a stamp')

    DOWN.update({'api1.cryptec.tech', 'api1.taitech.eu'})
    page.fill('#stamp-receipt', fixed)
    page.click('#stamp-go')
    expect(v).to_contain_text('Found, not yet confirmed', timeout=20000)
    expect(v).to_have_class(re.compile('warn'))
    DOWN.clear()
    ok('with only one operator reachable, the stamp is shown as not yet confirmed')

    page.fill('#stamp-receipt', fx['wrongOwner'])
    page.click('#stamp-go')
    expect(facts).to_contain_text("Owner line was wrong", timeout=20000)
    expect(page.locator('#stamp-updated pre')).to_contain_text('Owner: ' + fx['owner'])
    ok('a wrong Owner line is explained and a corrected receipt offered')

    FAKE_DRAND['on'] = True
    p3 = b.new_page(); p3.route('**/*', handle)
    p3.goto(pathlib.Path(page_path).resolve().as_uri() + '#stamp')
    expect(p3.locator('#stamp-latest-h')).to_be_visible(timeout=15000)
    p3.wait_for_timeout(1500)
    expect(p3.locator('#stamp-drand')).to_be_hidden()
    p3.close(); FAKE_DRAND['on'] = False
    ok('a drand relay serving a beacon that does not verify is never shown')

    page.goto(pathlib.Path(page_path).resolve().as_uri() + '#share')
    expect(page.locator('#stamp-top')).to_be_hidden()
    ok('the network view is unaffected')

    ph = b.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True)
    ph.route('**/*', handle)
    ph.goto(pathlib.Path(page_path).resolve().as_uri() + '#stamp')
    ph.fill('#stamp-receipt', fx['receipt'])
    ph.click('#stamp-go')
    expect(ph.locator('#stamp-result')).to_be_visible(timeout=20000)
    assert ph.evaluate('document.documentElement.scrollWidth') <= 390
    ph.screenshot(path=str(out / 'pulse-stamp-phone.png'), full_page=True)
    ok('fits a phone screen')
    assert not errors, errors
    ok('no page errors')
    b.close()
print(f'\n{len(passed)} Pulse stamp checks passed')
