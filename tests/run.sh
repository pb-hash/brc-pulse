#!/bin/sh
# Runs every BRC Pulse page check. Needs BRC Seal next to this folder (../brc-seal), with its
# test fixtures built (npm test there), because Pulse's kit and fixtures come from BRC Seal.
set -e
SEAL=../brc-seal
(cd $SEAL && node test/pulse-fixture.mjs && node test/giveaway-fixture.mjs && node tools/build-pulse-kit.mjs)
cmp $SEAL/dist/brc-kit.js vendor/brc-kit.js || { echo "vendor/brc-kit.js is out of date: copy $SEAL/dist/brc-kit.js"; exit 1; }
mkdir -p build-test
python3 build.py history.json --official $SEAL/build/pulse-official.json --releases $SEAL/build/pulse-releases > /dev/null && cp dist/brc-pulse.html build-test/stamps.html
python3 tests/stamp_page_test.py build-test/stamps.html $SEAL/build/pulse-fixture.json build-test
for v in open open-nolaunch drawn drawn-nocommit drawn-late drawn-moved; do
  python3 build.py history.json --official $SEAL/build/giveaway-official.json --giveaway $SEAL/build/giveaway-$v.json > /dev/null || exit 1; cp dist/brc-pulse.html build-test/gv-$v.html
done
python3 tests/giveaway_page_test.py build-test/gv-open.html build-test/gv-drawn.html $SEAL/build/giveaway-chain.json $SEAL/build/giveaway-fixture.json $SEAL/build/seal-core.mjs build-test build-test/gv-drawn-nocommit.html build-test/gv-drawn-late.html build-test/gv-open-nolaunch.html build-test/gv-drawn-moved.html
git checkout -q dist docs 2>/dev/null || true   # test builds never replace the published page
