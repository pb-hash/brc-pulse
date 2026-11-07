"""The English / 中文 switch in BRC Pulse, in headless Chromium, offline (the page replays its snapshot).

Usage: python3 tests/i18n_page_test.py <brc-pulse.html> <giveaway-open.html> <seal-core.mjs from BRC Post> <out-dir>

The switch only changes words. Signed messages, addresses and the giveaway's data are never changed.
"""
import json, re, subprocess, sys, pathlib
from playwright.sync_api import sync_playwright, expect

page_path, gv_path, seal_core, out = sys.argv[1], sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
HAN = re.compile(r"[一-鿿]")
passed = []
def ok(m): passed.append(m); print('ok -', m)

# A message signed by a throwaway key whose words are exactly a button's words.
signed = subprocess.run(['node', '--input-type=module', '-e', f"""
import * as c from '{pathlib.Path(seal_core).resolve()}';
import {{ randomBytes }} from 'node:crypto';
const w = c.walletFromPrivateKeyHex(randomBytes(32).toString('hex'));
process.stdout.write(c.signMessage(w, 'Check it').armored);
"""], capture_output=True, text=True, check=True).stdout

ENGLISH_LEFT = """(root) => {
  const skip = (e) => { for (; e; e = e.parentElement) { if (/^(SCRIPT|STYLE|CODE|PRE|KBD|SAMP|TEXTAREA)$/.test(e.tagName) || e.getAttribute('translate') === 'no' || (typeof e.className === 'string' && /(^|\\s)(mono|addr|signed-msg|wordmark)(\\s|$)/.test(e.className))) return true; } return false; };
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
  const w = document.createTreeWalker(document.querySelector(root), NodeFilter.SHOW_TEXT);
  let all = 0; const left = [];
  for (let n; (n = w.nextNode());) {
    const t = n.data.replace(/\\s+/g, ' ').trim();
    if (!/[a-z]{3,}/.test(t) || !n.parentElement || skip(n.parentElement) || !vis(n.parentElement)) continue;
    all++;
    const words = t.replace(/\\b(BrowserCoin|BRC|Vault|Pulse|Post|Works|Cryptec|Pool|Tabpool|brcove|drand|pb-hash|github|io|brc|pulse|https?|api\\d?|browsercoin|org|cryptec|tech|taitech|eu|kH|MH|UTC|Sandglass|Argon2id|PPLNS|archive)\\b/g, '');
    if (/[a-z]{3,}/.test(words) && !/[\\u4e00-\\u9fff]/.test(t)) left.push(t.slice(0, 80));
  }
  return { all, left };
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors = []
    ctx = b.new_context(viewport={'width': 1280, 'height': 900}, locale='en-US')
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    page = ctx.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(pathlib.Path(page_path).resolve().as_uri())
    page.wait_for_timeout(2500)
    expect(page.locator('[data-lang-toggle]')).to_have_text('中文')
    assert not HAN.search(page.evaluate('() => document.body.innerText').replace('中文', '').replace('以上规则为中文翻译', ''))
    ok('an English browser gets English, with a 中文 button in the top bar')

    page.click('[data-lang-toggle]')
    expect(page.locator('[data-lang-toggle]')).to_have_text('EN')
    assert page.evaluate('document.documentElement.lang') == 'zh-CN'
    page.wait_for_timeout(1500)
    cover = page.evaluate(ENGLISH_LEFT, 'body')
    print('   visible text left in English:', len(cover['left']), 'of', cover['all'], cover['left'][:12])
    assert len(cover['left']) <= max(4, cover['all'] // 12), cover['left']
    page.screenshot(path=str(out / 'zh-1-dashboard.png'), full_page=True)
    ok(f"中文 switches the dashboard to Chinese ({cover['all'] - len(cover['left'])} of {cover['all']} visible texts)")

    page.wait_for_timeout(3000)  # live replay keeps changing the page: new text arrives in Chinese too
    cover2 = page.evaluate(ENGLISH_LEFT, 'body')
    assert len(cover2['left']) <= max(4, cover2['all'] // 12), cover2['left']
    ok('text the page writes later (new blocks, timers) arrives in Chinese too')

    page.click('[data-lang-toggle]')
    page.wait_for_timeout(500)
    text = page.evaluate('() => document.body.innerText').replace('中文', '')
    assert not HAN.search(text), HAN.findall(text)[:20]
    ok('EN switches back to English with no Chinese left')

    page.click('[data-lang-toggle]')
    page.evaluate("location.hash = '#stamp'"); page.wait_for_timeout(600)
    page.fill('#stamp-receipt', signed)
    page.click('#stamp-go')
    expect(page.locator('#stamp-result')).to_be_visible(timeout=20000)
    expect(page.locator('#stamp-result .signed-msg')).to_have_text('Check it')
    expect(page.locator('#stamp-result')).to_contain_text(HAN)
    assert page.input_value('#stamp-receipt') == signed
    page.screenshot(path=str(out / 'zh-2-check.png'), full_page=True)
    ok('Check it in Chinese shows a signed message exactly as signed, never translated')

    page.locator('#stamp-file').set_input_files({'name': 'Copy', 'mimeType': 'text/plain', 'buffer': b'hello'})
    page.wait_for_timeout(800)
    assert 'Copy' in page.locator('#stamp-file-name').text_content() and '复制' not in page.locator('#stamp-file-name').text_content()
    ok('a file name shows exactly as it is, even when it is a word the page translates')

    order = "() => [...document.querySelectorAll('#stamp-latest, #stamp-drand')].map((b) => [...b.querySelectorAll('*')].filter((e) => e.parentElement === b).map((e) => e.tagName + '.' + e.className).join(','))"
    zh_order = page.evaluate(order)
    page.click('[data-lang-toggle]'); page.wait_for_timeout(300)
    en_order = page.evaluate(order)
    page.click('[data-lang-toggle]'); page.wait_for_timeout(300)
    assert zh_order == en_order, (zh_order, en_order)
    ok('values and their Copy buttons keep their order in Chinese')

    page.reload(); page.wait_for_timeout(1500)
    expect(page.locator('[data-lang-toggle]')).to_have_text('EN')
    ok('the choice is remembered on this device after a reload')
    ctx.close()

    # The giveaway page in Chinese: same data, the rules translated, and a note that English rules govern.
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='zh-CN')
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    page = ctx.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(pathlib.Path(gv_path).resolve().as_uri() + '#giveaway')
    page.wait_for_timeout(2500)
    expect(page.locator('[data-lang-toggle]')).to_have_text('EN')
    expect(page.locator('#gv-rules')).to_contain_text(HAN)
    expect(page.locator('.gv-zh-note')).to_be_visible()
    gv = json.loads(re.search(r'const GIVE = (\{.*?\});\n', open(gv_path).read()).group(1))
    fp = gv['eligible']['fingerprint']
    assert fp in page.locator('#gv-rules-more').text_content(), 'the eligible list fingerprint must show exactly'
    width = page.evaluate('() => document.documentElement.scrollWidth')
    assert width <= 390, f'page is {width}px wide on a phone'
    page.screenshot(path=str(out / 'zh-3-giveaway-phone.png'), full_page=True)
    page.click('[data-lang-toggle]'); page.wait_for_timeout(300)
    expect(page.locator('.gv-zh-note')).to_be_hidden()
    ok('the giveaway page in Chinese: rules translated with an "English governs" note, fingerprint exact, fits a phone')
    ctx.close()

    assert not errors, errors
    ok('no page errors')
    b.close()
print(f'\n{len(passed)} Pulse language checks passed')
