#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Read-only Morpheus API capability audit. Python 3 standard library only.

Manager mode: --url https://morpheus.example.com --cloud-id 1 --output audit.txt
Local HVM mode: --local-quorum --insecure --output quorum.txt
The token is prompted without echo. Only selected fields are written; raw API
configuration, credentials, error bodies and snapshot file paths are omitted.
Reports can contain private resource names and should be reviewed before sharing.
This script does not install checks or change the appliance configuration.
"""
import argparse
import getpass
import json
import math
import os
from pathlib import Path
import re
import ssl
import sys
import tempfile
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

VERSION = '0.2.0'
SPEC_COMMIT = 'cec1593e56d04d0515ffa904b1da9f7c56e9f007'
STATS = ('ts', 'cpuUsage', 'cpuUsageAvg', 'cpuReady', 'cpuIdleTime',
         'usedMemory', 'freeMemory', 'maxMemory', 'reservedMemory',
         'hostReservedMemory', 'usedStorage', 'freeStorage', 'maxStorage',
         'reservedStorage', 'readIOPS', 'writeIOPS', 'totalIOPS', 'iops',
         'netRxUsage', 'netTxUsage', 'bandwidth', 'running')
IDENTITY = ('id', 'name')
MULTIPATH = ('multipathPaths', 'multipathActive', 'multipathFailed', 'multipathState')
INTERESTING = re.compile(r'quorum|witness|fenc|heartbeat|multipath|corosync|dlm|lockspace|iscsi|storageinterface|filesystem|mount|diskstats|diskusage|interface|uplink|bond|carrier', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def scalar(value):
    return value is None or isinstance(value, (str, bool, int)) or isinstance(value, float) and math.isfinite(value)


def pick(obj, fields):
    if not isinstance(obj, dict):
        return {}
    return {k: obj[k][:500] if isinstance(obj[k], str) else obj[k]
            for k in fields if k in obj and scalar(obj[k])}


def rows(obj):
    return obj if isinstance(obj, list) else []


def field_types(obj):
    return {str(k)[:100]: type(v).__name__ for k, v in list(obj.items())[:200]} if isinstance(obj, dict) else {'value_type': type(obj).__name__}


def candidates(obj, path='', depth=0):
    """Discover candidate field locations without exposing their values."""
    found = []
    if depth > 6:
        return found
    entries = list(obj.items())[:200] if isinstance(obj, dict) else list(enumerate(obj[:3])) if isinstance(obj, list) else []
    for key, value in entries:
        location = path + '.' + str(key)[:100] if path else str(key)[:100]
        if INTERESTING.search(str(key)):
            found.append({'path': location, 'type': type(value).__name__})
        found.extend(candidates(value, location, depth + 1))
    return found[:200]


def stats_summary(value):
    result = {'fields': field_types(value), 'values': pick(value, STATS)}
    if isinstance(value, dict) and isinstance(value.get('sensors'), list):
        result['sensors_count'] = len(value['sensors'])
    return result


def filesystem_candidates(obj):
    """Export selected candidate readings without assuming units or semantics."""
    fields = ('name', 'device', 'deviceName', 'mountPoint', 'mountpoint', 'mount',
        'drive', 'driveLetter', 'filesystem', 'fsType', 'type', 'total', 'free',
        'used', 'available', 'size', 'capacity', 'totalBytes', 'freeBytes',
        'usedBytes', 'maxStorage', 'usedStorage', 'freeSpace', 'diskSize',
        'diskFree', 'diskUsed', 'ts', 'timestamp', 'lastUpdated', 'readOnly', 'mounted')
    result = []
    for label, container in (('server', obj), ('server.stats', obj.get('stats'))):
        if not isinstance(container, dict):
            continue
        for key in ('filesystems', 'fileSystems', 'diskStats', 'diskUsage', 'disks', 'mounts', 'mountPoints'):
            value = container.get(key)
            if not isinstance(value, (dict, list)):
                continue
            entries = list(value.items())[:100] if isinstance(value, dict) else list(enumerate(value[:100]))
            result.append({'source_path': label+'.'+key,
                'semantics': 'candidate data; guest-filesystem meaning and units require validation',
                'items': [{'record_key': str(k)[:100], 'values': pick(v, fields),
                    'fields': field_types(v)} for k, v in entries]})
    return result


def interface_info(obj, depth=0):
    result = pick(obj, (*IDENTITY, 'interfaceName', 'active', 'primaryInterface',
        'status', 'linkState', 'operState', 'adminState', 'linkUp', 'carrier',
        'enabled', 'speed', 'mtu', 'duplex', 'rxBytes', 'txBytes', 'rxErrors',
        'txErrors', 'rxDropped', 'txDropped', 'ts', 'timestamp', 'lastUpdated'))
    result['fields'] = field_types(obj)
    result['network'] = pick(obj.get('network'), IDENTITY)
    if depth < 3:
        for key in ('interfaces', 'slaves', 'members'):
            if isinstance(obj.get(key), list):
                result[key] = [interface_info(v, depth+1) for v in obj[key][:50] if isinstance(v, dict)]
    return result


def server(obj):
    result = pick(obj, (*IDENTITY, 'status', 'powerState', 'maintenanceMode',
        'serverGroupMemberStatus', 'agentInstalled', 'agentVersion',
        'guestAgentStatus', 'lastAgentUpdate', 'maxCores', 'maxMemory', 'maxStorage'))
    for relation in ('zone', 'parentServer'):
        result[relation] = pick(obj.get(relation), IDENTITY)
    result['stats'] = stats_summary(obj.get('stats'))
    result['volumes'] = [pick(v, (*IDENTITY, 'deviceName', 'rootVolume', 'status',
        'maxStorage', 'usedStorage', 'freeSpace', 'datastoreId', 'active', 'online',
        'readOnly', 'volumeType', 'controllerMountPoint', 'lastUpdated', 'dateCreated')) |
        {'datastore': pick(v.get('datastore'), IDENTITY), 'fields': field_types(v)} for v in rows(obj.get('volumes'))[:100] if isinstance(v, dict)]
    result['interfaces'] = [interface_info(v) for v in rows(obj.get('interfaces'))[:100] if isinstance(v, dict)]
    result['filesystem_candidates'] = filesystem_candidates(obj)
    result['candidate_fields'] = candidates(obj)
    return result


def server_detail(obj):
    result = server(obj.get('server') or {})
    result['root_stats'] = stats_summary(obj.get('stats'))
    return result


def uplink(obj):
    return pick(obj, (*IDENTITY, 'serverId', 'serverName', 'nic1', 'nic2',
        'syncStatus', 'lastSyncDate', 'linkState', 'operState', 'linkUp', 'speed')) | {
        'fields': field_types(obj),
        'semantics': 'NIC mapping and configuration sync status; not proof of physical carrier'}


def virtual_switch(obj):
    return pick(obj, (*IDENTITY, 'clusterId', 'baseType', 'bondMode', 'mtu',
        'status', 'active', 'nicCount', 'networkCount')) | {
        'uplinks': [uplink(v) for v in rows(obj.get('uplinks'))[:100]],
        'segments': [pick(v, (*IDENTITY, 'vlanId', 'vlan', 'mtu', 'status', 'trafficType')) for v in rows(obj.get('segments'))[:100]],
        'fields': field_types(obj)}


def datastore(obj):
    result = pick(obj, (*IDENTITY, 'status', 'online', 'active', 'maintenanceStatus',
        'storageSize', 'freeSpace', 'allowRead', 'allowWrite', 'allowProvision'))
    result['config_multipath'] = pick(obj.get('config'), MULTIPATH)
    result['locations'] = [pick(v, ('refType', 'refId', 'status')) for v in rows(obj.get('locations'))[:100]]
    result['candidate_fields'] = candidates(obj)
    return result


def cluster(obj):
    result = pick(obj, (*IDENTITY, 'status', 'enabled', 'lastSync', 'lastSyncDuration', 'autoRecoverPowerState'))
    result['zone'] = pick(obj.get('zone'), IDENTITY)
    result['layout'] = pick(obj.get('layout'), (*IDENTITY, 'code'))
    result['members'] = [pick(v, (*IDENTITY, 'status', 'powerState', 'serverGroupMemberStatus')) for v in rows(obj.get('servers'))[:100]]
    result['workerStats'] = stats_summary(obj.get('workerStats'))
    result['config_flags'] = pick(obj.get('config'), ('notHighAvailability', 'enabled', 'autoRecoverPowerState'))
    result['candidate_fields'] = candidates(obj)
    return result


def snapshot(obj):
    return pick(obj, (*IDENTITY, 'status', 'state', 'snapshotType', 'snapshotCreated',
        'dateCreated', 'lastUpdated', 'maxStorage', 'currentlyActive',
        'memorySnapshot', 'forExport', 'forBackup')) | {'fields': field_types(obj)}


def alarm(obj):
    return pick(obj, (*IDENTITY, 'status', 'severity', 'severityId', 'category',
        'alarmStatus', 'acknowledged', 'dateCreated', 'lastUpdated', 'startDate',
        'endDate', 'acknowledgedDate', 'acknoDate', 'refType', 'refId', 'resourceId',
        'resourceType', 'resourceName')) | {'fields': field_types(obj)}


def monitoring(obj):
    return pick(obj, (*IDENTITY, 'status', 'health', 'severity', 'active', 'muted',
        'deleted', 'availability', 'lastCheckStatus', 'lastRunDate', 'lastUpdated',
        'lastCheckTime', 'lastSuccessDate', 'lastErrorDate', 'lastWarningDate',
        'checkInterval', 'startDate', 'endDate', 'duration')) | {'fields': field_types(obj)}


def health(obj):
    h = obj.get('health')
    if not isinstance(h, dict):
        return {'fields': field_types(obj), 'health_object_present': False}
    result = pick(h, ('success', 'buildVersion', 'date', 'setupNeeded'))
    for key in ('cpu', 'memory', 'storage', 'threads', 'database', 'elastic', 'rabbit'):
        part = h.get(key)
        result[key] = pick(part, ('status', 'success', 'usedMemory', 'maxMemory',
            'swapPercent', 'systemMemory', 'systemAvailableMemory', 'totalThreads',
            'runningWebThreads', 'usedConnections', 'maxConnections', 'abortedConnections'))
        result[key]['fields'] = field_types(part)
    return result


def compliance(obj):
    return pick(obj, ('success', 'clusterId', 'profileId', 'profileName', 'overallStatus')) | {
        'hosts': [pick(h, ('serverId', 'serverName', 'status', 'compliant', 'lastChecked',
            'remediatedDate', 'remediableViolations', 'manualViolations')) for h in rows(obj.get('hosts'))[:100]],
        'fields': field_types(obj)}


def license_info(obj):
    fields = ('startDate', 'endDate', 'productTier', 'licenseVersion', 'limitType',
        'maxInstances', 'maxMemory', 'maxStorage', 'maxManagedServers',
        'maxDiscoveredServers', 'maxHosts', 'maxMvm', 'maxMvmSockets', 'maxSockets',
        'maxDistributedWorkers', 'hardLimit', 'freeTrial', 'lastUpdated')
    return {'license': pick(obj.get('license'), fields),
        'installedLicenses': [pick(v, fields) for v in rows(obj.get('installedLicenses'))[:100]],
        'currentUsage': pick(obj.get('currentUsage'), ('memory', 'storage', 'workloads',
            'managedServers', 'discoveredServers', 'hosts', 'mvm', 'mvmSockets',
            'sockets', 'hypervisorSocketCount', 'distributedWorkers')),
        'licenseLimits': [pick(v, ('code', 'max', 'used', 'percentUsed', 'warning',
            'limitReached', 'unit')) for v in rows(obj.get('licenseLimits'))[:100]],
        'limitReached': pick(obj, ('limitReached',)).get('limitReached'),
        'fields': field_types(obj)}


def quorum(obj, depth=0):
    fields = ('quorumAchieved', 'fenced', 'waitFencing', 'reachableNodes', 'totalNodes',
        'onlineNodes', 'offlineNodes', 'fencedNodes', 'corosyncActive', 'dlmActive',
        'corosyncQuorate', 'witnessConnected', 'witnessReachable', 'status', 'ts', 'timestamp', 'quorum')
    result = pick(obj, fields)
    for key in ('quorum', 'data', 'witness'):
        if depth < 3 and isinstance(obj.get(key), dict):
            result[key] = quorum(obj[key], depth + 1)
    result['nodes'] = [pick(v, ('id', 'name', 'serverId', 'reachable', 'online',
        'status', 'fenced', 'waitFencing', 'lastHeartbeat', 'lastUpdated'))
        for v in rows(obj.get('nodes'))[:100]]
    result['fields'] = field_types(obj)
    result['candidate_fields'] = candidates(obj)
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Audit:
    def __init__(self, base, token, insecure=False, timeout=15, budget=180):
        self.base, self.token = base.rstrip('/'), token
        self.deadline, self.timeout = time.monotonic() + budget, timeout
        self.calls, self.entries = 0, []
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=
            ssl._create_unverified_context() if insecure else ssl.create_default_context()))

    def get(self, endpoint, **query):
        if self.calls >= 100 or time.monotonic() >= self.deadline:
            return None, {'status': 'skipped', 'reason': 'request or time budget exhausted'}
        self.calls += 1
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = Request(self.base + endpoint + ('?' + urlencode(query) if query else ''), headers=headers, method='GET')
        try:
            with self.opener.open(request, timeout=min(self.timeout, max(.1, self.deadline-time.monotonic()))) as response:
                data = response.read(16 * 1024 * 1024 + 1)
                if len(data) > 16 * 1024 * 1024:
                    return None, {'status': 'error', 'reason': 'response exceeds 16 MiB'}
                obj = json.loads(data)
                if not isinstance(obj, dict):
                    return None, {'status': 'error', 'reason': 'expected JSON object'}
                if obj.get('success') is False:
                    return None, {'status': 'api_failure', 'http': response.status, 'fields': field_types(obj)}
                return obj, {'status': 'ok', 'http': response.status, 'fields': field_types(obj)}
        except HTTPError as exc:
            return None, {'status': 'http_error', 'http': exc.code}
        except (URLError, TimeoutError, OSError):
            return None, {'status': 'connection_error', 'reason': 'connection, TLS or timeout failure'}
        except (ValueError, UnicodeError):
            return None, {'status': 'error', 'reason': 'invalid JSON'}

    def one(self, endpoint, sanitizer, context=None):
        print('GET ' + endpoint, file=sys.stderr)
        obj, meta = self.get(endpoint)
        entry = {'endpoint': endpoint, 'context': context, 'checked_at': now(), **meta}
        if obj is not None:
            try:
                entry['data'] = sanitizer(obj)
            except (ValueError, TypeError, AttributeError, KeyError):
                entry.update(status='unexpected_shape', reason='selected nested fields have an unexpected structure')
        self.entries.append(entry)
        return obj

    def listing(self, endpoint, key, sanitizer, context=None, unpaged=False, scope=None, **filters):
        print('GET ' + endpoint, file=sys.stderr)
        entry = {'endpoint': endpoint, 'context': context, 'checked_at': now(), 'complete': False}
        self.entries.append(entry)
        collected, seen = [], set()
        total = None
        for _ in range(10):
            obj, meta = self.get(endpoint, **({} if unpaged else {'max': 100, 'offset': len(collected)}), **filters)
            entry.update(meta)
            if obj is None:
                break
            batch = obj.get(key)
            if not isinstance(batch, list) or any(not isinstance(v, dict) for v in batch):
                entry.update(status='unexpected_shape', reason='expected object array: ' + key)
                break
            duplicate = any(str(v['id']) in seen for v in batch if v.get('id') is not None)
            if duplicate:
                entry.update(status='partial', reason='duplicate objects across pages; inventory may have changed')
                break
            seen.update(str(v['id']) for v in batch if v.get('id') is not None)
            collected.extend(batch)
            paging = obj.get('meta')
            if isinstance(paging, dict) and isinstance(paging.get('total'), int) and not isinstance(paging['total'], bool) and paging['total'] >= 0:
                total = paging['total']
                if len(collected) >= total:
                    entry['complete'] = True
                    break
                if not batch or unpaged:
                    entry.update(status='partial', reason='pagination incomplete or unsupported for this endpoint')
                    break
            else:
                entry['complete'] = True if unpaged else None
                if not unpaged:
                    entry['reason'] = 'no pagination total; completeness unverified'
                break
        else:
            entry.update(status='partial', reason='pagination limit reached')
        entry['returned'] = len(collected)
        entry['reported_total'] = total
        selected = [value for value in collected if scope(value)] if scope else collected
        entry['selected_in_scope'] = len(selected)
        entry['data'] = []
        for value in selected:
            try:
                entry['data'].append(sanitizer(value))
            except (ValueError, TypeError, AttributeError, KeyError):
                entry['data'].append({'fields': field_types(value), 'status': 'unexpected_shape'})
                entry.update(status='partial', reason='one or more objects have unexpected nested structures')
        return selected


def object_id(obj):
    value = obj.get('id') if isinstance(obj, dict) else None
    return str(value) if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def atomic_report(path, report, token):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    def redact(value):
        if isinstance(value, str):
            return value.replace(token, '[REDACTED]') if token else value
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value
    text = json.dumps(redact(report), ensure_ascii=False, indent=2, allow_nan=False)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
            temporary = f.name
            f.write(text + '\n')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', help='Manager HTTPS base URL without /api')
    parser.add_argument('--cloud-id', type=int, help='Restrict VM, host and cluster inventory to this cloud')
    parser.add_argument('--insecure', action='store_true', help='Disable TLS certificate validation explicitly')
    parser.add_argument('--local-quorum', action='store_true', help='Read only local HVM https://localhost:7443/quorum; no token sent')
    parser.add_argument('--max-vms', type=int, default=30, help='Maximum VMs for detail and snapshot probes (default 30)')
    parser.add_argument('--output', type=Path, default=Path.home()/'tmp'/('morpheus_api_audit_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'.txt'))
    args = parser.parse_args()
    if not 1 <= args.max_vms <= 100 or args.cloud_id is not None and args.cloud_id <= 0:
        parser.error('max-vms must be 1..100 and cloud-id must be positive')
    token = ''
    if args.local_quorum:
        if args.url or args.cloud_id:
            parser.error('local-quorum cannot be combined with url/cloud-id')
        base = 'https://localhost:7443'
    else:
        parsed = urlsplit(args.url or '')
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            parser.error('url must be https://hostname[:port], without path/query/credentials')
        base = args.url
        token = getpass.getpass('Morpheus API token: ')
        if not token or '\r' in token or '\n' in token:
            parser.error('invalid or empty token')
    audit = Audit(base, token, args.insecure)
    report = {'tool': 'Morpheus read-only API audit', 'version': VERSION,
        'started_at': now(), 'mode': 'local_quorum' if args.local_quorum else 'manager',
        'reference_openapi_commit': SPEC_COMMIT, 'cloud_id': args.cloud_id,
        'tls_verified': not args.insecure, 'entries': audit.entries, 'limits': [],
        'notes': ['Only GET requests; no monitoring or infrastructure configuration changes.',
            'Failed/unsupported endpoints are not empty healthy results.',
            'Alarm/check/incident endpoints use appliance/account scope, not the cloud inventory filter.',
            'Volume usedStorage and interface active are inventory values; guest filesystem fullness and physical link state require separate evidence.',
            'Raw configuration, error bodies, tokens and snapshot file paths are omitted.',
            'Resource names are private environment information; review before sharing.']}
    try:
        if args.local_quorum:
            audit.one('/quorum', quorum)
        else:
            audit.one('/api/health', health)
            audit.one('/api/license', license_info)
            filters = {'zoneId': args.cloud_id} if args.cloud_id else {}
            in_scope = lambda v: args.cloud_id is None or v.get('zoneId') == args.cloud_id or pick(v.get('zone'), ('id',)).get('id') == args.cloud_id
            clouds = audit.listing('/api/zones', 'zones', lambda z: pick(z, (*IDENTITY, 'status', 'lastSync')),
                scope=lambda z: args.cloud_id is None or z.get('id') == args.cloud_id)
            if args.cloud_id and not clouds:
                report['limits'].append('Requested cloud not found in the returned cloud inventory.')
            clusters = audit.listing('/api/clusters', 'clusters', cluster, scope=in_scope, **filters)
            vms = audit.listing('/api/servers', 'servers', server, context='virtual_machines', scope=in_scope, vm='true', **filters)
            hosts = audit.listing('/api/servers', 'servers', server, context='hypervisors', scope=in_scope, vmHypervisor='true', **filters)
            for z in clouds[:10]:
                if (sid := object_id(z)):
                    audit.listing('/api/zones/'+sid+'/data-stores', 'datastores', datastore, context={'cloud_id': z['id']})
            switch_probes = 0
            for c in clusters[:10]:
                if (sid := object_id(c)):
                    audit.one('/api/clusters/'+sid, lambda obj: cluster(obj.get('cluster') or {}), context={'cluster_id': c['id']})
                    audit.listing('/api/clusters/'+sid+'/datastores', 'datastores', datastore, context={'cluster_id': c['id']})
                    audit.one('/api/clusters/'+sid+'/host-profile/compliance', compliance, context={'cluster_id': c['id']})
                    switches = audit.listing('/api/virtual-switches', 'virtualSwitches', virtual_switch,
                        context={'cluster_id': c['id']}, unpaged=True, clusterId=c['id'])
                    for switch in switches:
                        if switch_probes >= 10:
                            report['limits'].append('Virtual switch detail probes limited to 10 switches.')
                            break
                        if (switch_id := object_id(switch)):
                            switch_probes += 1
                            audit.one('/api/virtual-switches/'+switch_id,
                                lambda obj: virtual_switch(obj.get('virtualSwitch') or {}))
                            audit.listing('/api/virtual-switches/'+switch_id+'/uplinks', 'uplinks', uplink, unpaged=True)
            for h in hosts[:10]:
                if (sid := object_id(h)):
                    audit.one('/api/servers/'+sid, server_detail, context={'hypervisor_id': h['id']})
            for vm in vms[:args.max_vms]:
                if (sid := object_id(vm)):
                    audit.one('/api/servers/'+sid, server_detail, context={'vm_id': vm['id']})
                    audit.listing('/api/servers/'+sid+'/snapshots', 'snapshots', snapshot, context={'vm_id': vm['id'], 'vm_name': pick(vm, ('name',)).get('name')}, unpaged=True)
            if len(vms) > args.max_vms:
                report['limits'].append(str(len(vms)-args.max_vms)+' VM snapshot endpoints skipped by max-vms limit.')
            if any(len(group) > 10 for group in (clouds, clusters, hosts)):
                report['limits'].append('Per-object cloud/cluster/hypervisor probes limited to first 10 objects of each type.')
            audit.listing('/api/health/alarms', 'alarms', alarm, context='appliance/account scope; API default alarm filter')
            audit.listing('/api/monitoring/checks', 'checks', monitoring, context='appliance/account scope')
            audit.listing('/api/monitoring/incidents', 'incidents', monitoring, context='appliance/account scope')
    except KeyboardInterrupt:
        report['limits'].append('Interrupted by operator; report is partial.')
    finally:
        report.update(finished_at=now(), requests=audit.calls)
        atomic_report(args.output.expanduser(), report, token)
        print('Report saved: ' + str(args.output.expanduser()))
        print('Share the report after reviewing resource names. Do not share the token.')


if __name__ == '__main__':
    main()
