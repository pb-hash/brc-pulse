Release postmarks for BRC Pulse's "Is this BRC Works file genuine?"

One file per release, named <tool>-<version>.txt (for example brc-vault-1.1.0.txt), holding the
whole chain-signed block (-----BEGIN BRC CHAIN SIGNED MESSAGE----- to the end) that the BRC Works
release address signed in BRC Seal. Make the message with BRC Seal's tools/release-message.mjs.
The page checks each one on the chain, and that it was signed by the release address in
BRC Seal's src/official.js, before calling a file genuine.
