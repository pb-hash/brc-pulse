#!/bin/sh
# Runs every BRC Pulse page check. Needs BRC Post next to this folder (../brc-post), with its
# test fixtures built (npm test there), because Pulse's kit and fixtures come from BRC Post.
set -e
POST=../brc-post
(cd $POST && node test/pulse-fixture.mjs && node test/giveaway-fixture.mjs && node tools/build-pulse-kit.mjs)
cmp $POST/dist/brc-kit.js vendor/brc-kit.js || { echo "vendor/brc-kit.js is out of date: copy $POST/dist/brc-kit.js"; exit 1; }
mkdir -p build-test
python3 build.py history.json --official $POST/build/pulse-official.json --releases $POST/build/pulse-releases > /dev/null && cp dist/brc-pulse.html build-test/stamps.html
python3 tests/stamp_page_test.py build-test/stamps.html $POST/build/pulse-fixture.json build-test
for v in open open-nolaunch drawn drawn-nocommit drawn-late drawn-moved; do
  python3 build.py history.json --official $POST/build/giveaway-official.json --giveaway $POST/build/giveaway-$v.json > /dev/null || exit 1; cp dist/brc-pulse.html build-test/gv-$v.html
done
python3 build.py history.json --official $POST/build/giveaway-official.json --giveaway $POST/build/giveaway-drawn.json --releases $POST/build/giveaway-releases > /dev/null || exit 1; cp dist/brc-pulse.html build-test/gv-drawn-rel.html
python3 tests/giveaway_page_test.py build-test/gv-open.html build-test/gv-drawn.html $POST/build/giveaway-chain.json $POST/build/giveaway-fixture.json $POST/build/seal-core.mjs build-test build-test/gv-drawn-nocommit.html build-test/gv-drawn-late.html build-test/gv-open-nolaunch.html build-test/gv-drawn-moved.html build-test/gv-drawn-rel.html
git checkout -q dist docs 2>/dev/null || true   # test builds never replace the published page
