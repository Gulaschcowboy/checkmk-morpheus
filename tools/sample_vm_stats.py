#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Sample one VM across API update phases. Only GET; no cache timestamps changed.

Keep morpheus_api_audit.py in this directory. The token is prompted, not passed
as an argument or saved. The output contains selected private resource metadata.
"""
import argparse
import getpass
from pathlib import Path
import time
from urllib.parse import urlsplit
from morpheus_api_audit import Audit, server, server_detail, atomic_report, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--vm-id', type=int, required=True)
    parser.add_argument('--insecure', action='store_true')
    parser.add_argument('--samples', type=int, default=12)
    parser.add_argument('--interval', type=int, default=5)
    parser.add_argument('--output', type=Path, default=Path.home()/'tmp/morpheus_vm_samples.txt')
    args = parser.parse_args()
    url = urlsplit(args.url)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ('', '/')):
        parser.error('url must be an HTTPS base URL without path/query/credentials')
    if args.vm_id <= 0 or not 2 <= args.samples <= 30 or not 1 <= args.interval <= 15 or args.samples*args.interval > 150:
        parser.error('vm-id must be positive; samples 2..30; interval 1..15; samples*interval at most 150 seconds')
    token = getpass.getpass('Morpheus API token: ')
    if not token or '\n' in token or '\r' in token:
        parser.error('invalid/empty token')
    audit = Audit(args.url, token, args.insecure, timeout=10, budget=180)
    report = {'tool':'Morpheus VM statistics phase sampler', 'started_at':now(),
        'vm_id':args.vm_id, 'entries':audit.entries,
        'note':'API detail/list responses retain their original timestamps. No Checkmk cache is read or refreshed by this script.'}
    try:
        for index in range(args.samples):
            payload = audit.one('/api/servers/'+str(args.vm_id), server_detail, context={'sample':index+1})
            vm = (payload or {}).get('server') or {}
            if isinstance(vm, dict) and isinstance(vm.get('name'), str):
                audit.listing('/api/servers', 'servers', server, context={'sample':index+1},
                    scope=lambda v: str(v.get('id'))==str(args.vm_id), vm='true', name=vm['name'])
            if index+1 < args.samples and time.monotonic()+args.interval < audit.deadline:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        report['interrupted'] = True
    finally:
        report.update(finished_at=now(), requests=audit.calls)
        atomic_report(args.output.expanduser(), report, token)
        print('Report saved: '+str(args.output.expanduser()))


if __name__=='__main__': main()
