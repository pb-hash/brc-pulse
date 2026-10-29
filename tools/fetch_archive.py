#!/usr/bin/env python3
"""Downloads the BrowserCoin chain archive (swompythesecond/browsercoin-archive) into a folder.
Chunks already on disk are kept; the newest chunk is always refreshed because it may still be filling.

    python3 tools/fetch_archive.py archive
"""
import json, os, sys, urllib.request

BASE = 'https://raw.githubusercontent.com/swompythesecond/browsercoin-archive/main/browsercoin-pow-v5/'


def fetch(name):
    req = urllib.request.Request(BASE + name, headers={'User-Agent': 'brc-pulse-build'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'archive'
    os.makedirs(out, exist_ok=True)
    raw = fetch('manifest.json')
    manifest = json.loads(raw)
    open(os.path.join(out, 'manifest.json'), 'wb').write(raw)
    chunks = manifest['chunks']
    got = 0
    for i, c in enumerate(chunks):
        path = os.path.join(out, c['file'])
        if os.path.exists(path) and i < len(chunks) - 1:
            continue
        open(path, 'wb').write(fetch('blocks/' + c['file'])); got += 1
    print('archived height', manifest['archivedHeight'], 'chunks', len(chunks), 'downloaded', got)


if __name__ == '__main__':
    main()
