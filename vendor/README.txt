brc-drand.js checks drand quicknet beacon signatures (BLS12-381) inside the page,
so a stamp's "made after" moment doesn't depend on trusting a drand relay.
It is built from BRC Seal's src/drand-core.js with:  node tools/build-drand-bundle.mjs
(@noble/curves 1.9.7 and @noble/hashes 1.8.0, MIT License.)
