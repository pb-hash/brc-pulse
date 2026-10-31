Release postmarks for BRC Pulse's "Is this BRC Works file genuine?"

One file per release, named <tool>-<version>.txt (for example brc-vault-1.1.0.txt), holding the
whole chain-signed block (-----BEGIN BRC CHAIN SIGNED MESSAGE----- to the end) that the BRC Works
release address signed in BRC Post, as BRC Pulse → Stamps gives it back once checked: with its
Lock ID: and Block: lines. The build refuses a release without them. Make the message with BRC Post's tools/release-message.mjs.
The page checks each one on the chain, and that it was signed by the release address in
BRC Post's src/official.js, before calling a file genuine.
