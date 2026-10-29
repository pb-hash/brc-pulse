BRC Pulse
=========

BrowserCoin, beat by beat. A live dashboard for the BrowserCoin (BRC) network.

BRC Pulse is a single web page, dist/brc-pulse.html. It reads the public
BrowserCoin helper servers straight from your browser. There is no server of
ours, no account, no cookies and no analytics.

Use it online:  https://pb-hash.github.io/brc-pulse/
Or download it: dist/brc-pulse.html, save it, and open the saved file. It
                connects and runs live from your desktop too.

Part of the BRC family, with BRC Vault (https://pb-hash.github.io/brc-vault/).

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
- A GitHub Action (.github/workflows/refresh.yml) rebuilds the page once a day
  so the snapshot and history stay current.

Privacy
-------
The published page carries a Content-Security-Policy: only its own script
runs (pinned by SHA-256), fonts are embedded in the page, and it can connect
only to the four helper servers above. It loads nothing from anywhere else.

Verify your copy
----------------
dist/SHA256.txt holds the SHA-256 of dist/brc-pulse.html:
    shasum -a 256 dist/brc-pulse.html
The hash changes with each daily refresh, because the embedded snapshot does.

Build
-----
Python 3, no packages needed.
    python3 tools/fetch_archive.py archive          # chain archive, cached
    python3 tools/history.py archive history.json   # daily history
    python3 build.py history.json                   # writes dist/ and docs/

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
