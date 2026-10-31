BRC Pulse
=========

BrowserCoin, beat by beat. A live dashboard for the BrowserCoin (BRC) network.

BRC Pulse is a single web page, dist/brc-pulse.html. It reads the public
BrowserCoin helper servers straight from your browser. There is no server of
ours, no account, no cookies and no analytics.

Use it online:  https://pb-hash.github.io/brc-pulse/
Or download it: dist/brc-pulse.html, save it, and open the saved file. It
                connects and runs live from your desktop too.

BRC Works: Vault (https://pb-hash.github.io/brc-vault/) · Pulse.
Independent tools by pb-hash. Not part of the official BrowserCoin project.

What it shows
-------------
- The latest block, who found it, and a live timer against the 2:30 target.
  The logo's frame is the timer, and its pulse redraws on every new block.
- Who is finding blocks over 24 h or 6 h, with the 50% majority line. A miner
  or pool past half could rewrite recent history, so this is the number to
  watch.
- The last 144 blocks as a heartbeat strip, plus the 8 most recent blocks.
- A mining calculator: your share, expected BRC per day, and solo odds at the
  current network hashrate.
- The pools, with fees and payouts, and each pool's 24 h share where its
  payout address is confirmed from the pool's own public stats.
- Helper server status, including the likely cause of the app's
  "1/2 helper server" message.
- History since launch from the full chain archive: concentration, hashrate
  and miners per day.
- Supply, burned coins, script locks and the countdown to the first halving.

Check it
--------
https://pb-hash.github.io/brc-pulse/#stamp checks proof straight from the
chain, in your browser: postmark receipts of files, messages signed on the
chain and mailbox links made in BRC Seal, and whether a BRC Works file you were
given is a genuine release. Nothing you check is uploaded.

My BRC
------
Paste any address (https://pb-hash.github.io/brc-pulse/#my) to see its
balance, the blocks it found and its 30-day mining, who pays it (pool payouts),
and its recent transfers. Click any miner name on the dashboard to look it up.

- Balances come from replaying the whole chain with BrowserCoin's own rules
  (tools/accounts.py, following src/chain/state.ts): transfers, script locks
  and redeems, and 50 BRC plus fees per block found. The replay checks every
  nonce, never lets a balance go negative, and confirms that all balances plus
  locked coins equal exactly 50 BRC times the blocks mined.
- The page then applies every newer block itself, fetched from the helper
  servers, so the balance is current to the latest block.
- Your address never leaves your browser in full: the index is split into
  small files by the first three characters of the address, and the page finds
  yours on your device. It is remembered on your device only, until you click
  Forget.

How it gets its data
--------------------
- Live: every 6 seconds the page asks the fastest synced helper server
  (api1/api2.browsercoin.org, api1.cryptec.tech, api1.taitech.eu) for new
  blocks, and re-checks all helpers every minute. Block headers are decoded in
  the page. Hashrate is the expected work behind each block's difficulty,
  divided by elapsed time.
- Snapshot: each build embeds the last 800 blocks and a daily history replayed
  from the chain archive (github.com/swompythesecond/browsercoin-archive), so
  the page shows real data before it connects. If it can't reach the network
  at all, it replays the last 20 real blocks at 20x speed and says so.
- A GitHub Action (.github/workflows/pages.yml) rebuilds and publishes the
  site every hour: snapshot, history and the My BRC index. Nothing is
  committed; GitHub Pages serves the workflow's output.

Privacy
-------
The published page carries a Content-Security-Policy: only its own script
runs (pinned by SHA-256), fonts are embedded in the page, and it can connect
only to the four helper servers above and to this site (for the My BRC
index). It loads nothing from anywhere else.

Verify your copy
----------------
dist/SHA256.txt holds the SHA-256 of dist/brc-pulse.html:
    shasum -a 256 dist/brc-pulse.html
The hash changes whenever the page is rebuilt, because the embedded snapshot
does. The copy in dist/ is updated with code changes; the hourly published
page has a fresher snapshot.

Build
-----
Python 3, no packages needed.
    python3 tools/fetch_archive.py archive          # chain archive, cached
    python3 tools/history.py archive history.json   # daily history
    python3 tools/accounts.py archive _site/a       # My BRC address index
    python3 build.py history.json --site _site      # the site, plus dist/

Pool labels
-----------
Pool names are shown only where a payout address is confirmed from the pool's
own public stats (currently Cryptec Pool and Tabpool). Pool operators: post
your payout address in the BrowserCoin Discord or open an issue here, and it
will be added.

Brand
-----
brand/ holds the BRC Pulse mark (SVG and PNG, light, dark and app icon), the
social preview image and gen_logo.py, which draws the mark's geometry.

Credits and license
-------------------
Community project, not made by the BrowserCoin developers. MIT License, see
LICENSE. Fonts: Manrope (The Manrope Project Authors) and Geist / Geist Mono
(Vercel), SIL Open Font License 1.1, see fonts/.
