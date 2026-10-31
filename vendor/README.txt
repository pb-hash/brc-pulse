brc-kit.js is BRC Seal code that BRC Pulse runs in the page:
- drand quicknet beacon checking (BLS12-381), so a stamp's "made after" moment and the giveaway draw
  don't depend on trusting a drand relay;
- the giveaway: sealing an entry to the giveaway mailbox, list fingerprints, and the draw.
It is built from BRC Seal's src/drand-core.js and src/giveaway-core.js with:  node tools/build-pulse-kit.mjs
(@noble/curves, @noble/hashes, @noble/ed25519, @noble/ciphers, @scure/bip39, @scure/base; MIT License.)
