#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Build the documented Checkmk MKP archive layout, without a running site."""
import io
import argparse
import json
import pathlib
import pprint
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'dist'
VERSION = '1.0.4'

def add(tar, name, content, mode=0o644):
    entry = tarfile.TarInfo(name)
    entry.size, entry.mode = len(content), mode
    entry.mtime = 1793232000
    tar.addfile(entry, io.BytesIO(content))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-url', default='', help='Public repository or project URL (optional)')
    args = parser.parse_args()
    if args.download_url and not args.download_url.startswith('https://'):
        parser.error('--download-url must use HTTPS')
    paths = sorted(p for p in (ROOT / 'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files = [str(p.relative_to(ROOT / 'src')) for p in paths]
    manifest = {
        'name': 'morpheus', 'title': 'HPE Morpheus Monitoring', 'version': VERSION,
        'author': 'Pawel Wladzinski <pawel.wladzinski@vayana.pl>',
        'description': 'Read-only Morpheus 9.1 API collector, health checks, datastores, multipath, clusters, hypervisors, hardware and VM piggyback. Configure API credentials and discover platform, infrastructure and VM services.',
        'download_url': args.download_url, 'version.packaged': '2.4.0',
        'version.min_required': '2.4.0', 'version.usable_until': '2.5.0',
        'files': {'cmk_addons_plugins': files},
    }
    inner = io.BytesIO()
    with tarfile.open(fileobj=inner, mode='w') as tar:
        for p, name in zip(paths, files):
            add(tar, name, p.read_bytes(), 0o755 if p.parent.name == 'libexec' else 0o644)
    OUT.mkdir(exist_ok=True)
    output = OUT / ('morpheus-' + VERSION + '.mkp')
    with tarfile.open(output, 'w:gz') as tar:
        add(tar, 'info', pprint.pformat(manifest).encode())
        add(tar, 'info.json', json.dumps(manifest, indent=2).encode())
        add(tar, 'cmk_addons_plugins.tar', inner.getvalue())
    print(output)

if __name__ == '__main__':
    main()
