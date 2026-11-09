# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import time
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1]/'tools/morpheus_api_audit.py'
spec = importlib.util.spec_from_file_location('api_audit', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Response:
    status = 200
    def __init__(self, obj): self.obj = obj
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return json.dumps(self.obj).encode()


class AuditTests(unittest.TestCase):
    def test_server_filters_credentials_and_config_values(self):
        raw = {'id': 1, 'name': 'Example', 'sshPassword': 'SSHSECRET', 'apiKey': 'APISECRET',
            'guestConsolePassword': 'CONSOLESECRET', 'config': {'password': 'CONFIGSECRET', 'quorumToken': 'QUORUMSECRET'},
            'volumes': [{'name': 'root', 'maxStorage': 100, 'usedStorage': 50, 'password': 'VOLUMESECRET'}],
            'interfaces': [{'name': 'eth0', 'status': 'up', 'password': 'NICSECRET'}],
            'stats': {'ts': '2026-11-05T00:00:00Z', 'cpuReady': 1, 'secret': 'STATSSECRET'}}
        out = json.dumps(m.server(raw))
        for secret in ('SSHSECRET', 'APISECRET', 'CONSOLESECRET', 'CONFIGSECRET', 'QUORUMSECRET', 'VOLUMESECRET', 'NICSECRET', 'STATSSECRET'):
            self.assertNotIn(secret, out)
        self.assertIn('quorumToken', out)  # Only the candidate path/type.

    def test_snapshots_include_dates_sizes_and_no_file_paths(self):
        raw = {'id': 1, 'name': 'snapshot', 'snapshotCreated': '2026-11-05T00:00:00Z',
            'maxStorage': None, 'snapshotFiles': [{'path': '/PRIVATE/PATH', 'exportPath': 'SECRET'}]}
        out = m.snapshot(raw)
        self.assertIsNone(out['maxStorage'])
        self.assertIn('snapshotCreated', out)
        self.assertNotIn('/PRIVATE/PATH', json.dumps(out))

    def test_multipath_actual_values_and_no_config_dump(self):
        out = m.datastore({'id': 8, 'config': {'multipathPaths': 2, 'multipathActive': 1,
            'multipathFailed': 1, 'multipathState': 'degraded', 'password': 'SECRET'}})
        self.assertEqual(out['config_multipath']['multipathFailed'], 1)
        self.assertNotIn('SECRET', json.dumps(out))

    def test_license_expiry_and_limits_without_key_or_hash(self):
        out = m.license_info({'license': {'endDate': '2027-01-01', 'keyId': 'KEYSECRET', 'hash': 'HASHSECRET'},
            'licenseLimits': [{'code': 'mvmSockets', 'max': 2, 'used': 2, 'limitReached': True}],
            'currentUsage': {'mvmSockets': 2}})
        self.assertEqual(out['currentUsage']['mvmSockets'], 2)
        self.assertEqual(out['license']['endDate'], '2027-01-01')
        self.assertNotIn('SECRET', json.dumps(out))

    def test_compliance_does_not_export_configuration_differences(self):
        out = m.compliance({'overallStatus': 'non-compliant', 'hosts': [{'serverId': 1,
            'status': 'non-compliant', 'lastChecked': '2026-11-05',
            'complianceDetails': {'private': {'actual': 'SECRET'}}}]})
        self.assertEqual(out['hosts'][0]['status'], 'non-compliant')
        self.assertNotIn('SECRET', json.dumps(out))

    def test_nested_quorum_reachability_and_no_tokens(self):
        out = m.quorum({'quorum': {'quorumAchieved': False, 'waitFencing': True,
            'nodes': [{'name': 'node1', 'reachable': False, 'secret': 'SECRET'}], 'token': 'SECRET'}})
        self.assertFalse(out['quorum']['quorumAchieved'])
        self.assertFalse(out['quorum']['nodes'][0]['reachable'])
        self.assertNotIn('SECRET', json.dumps(out))

    def test_filesystem_candidates_keep_per_mount_values_without_invented_units(self):
        raw = {'id': 3, 'volumes': [{'deviceName': '/dev/vda', 'usedStorage': 0, 'maxStorage': 100}],
            'stats': {'filesystems': [{'mountPoint': '/', 'usedBytes': 95, 'freeBytes': 5,
                'totalBytes': 100, 'password': 'SECRET'}]}}
        out = m.server(raw)
        fs = out['filesystem_candidates'][0]['items'][0]
        self.assertEqual(fs['values']['mountPoint'], '/')
        self.assertEqual(fs['values']['freeBytes'], 5)
        self.assertNotIn('SECRET', json.dumps(out))
        self.assertNotIn('timestamp', fs['values'])
        self.assertIn('require validation', out['filesystem_candidates'][0]['semantics'])

    def test_interface_children_keep_link_and_error_fields(self):
        out = m.interface_info({'name': 'bond0', 'active': True, 'password': 'SECRET',
            'interfaces': [{'name': 'eth0', 'operState': 'down', 'rxErrors': 5, 'apiKey': 'SECRET'}]})
        self.assertEqual(out['interfaces'][0]['operState'], 'down')
        self.assertEqual(out['interfaces'][0]['rxErrors'], 5)
        self.assertNotIn('SECRET', json.dumps(out))

    def test_virtual_switch_sync_is_not_presented_as_physical_link_health(self):
        out = m.virtual_switch({'id': 1, 'status': 'available', 'bondMode': 'active-backup',
            'uplinks': [{'serverId': 1, 'nic1': 'eth0', 'nic2': 'eth1',
                'syncStatus': 'in-sync', 'password': 'SECRET'}]})
        self.assertEqual(out['uplinks'][0]['syncStatus'], 'in-sync')
        self.assertNotIn('SECRET', json.dumps(out))
        self.assertIn('not proof of physical carrier', out['uplinks'][0]['semantics'])

    def test_requests_are_get_and_bearer_is_only_in_headers(self):
        seen = []
        audit = m.Audit('https://example.invalid', 'TOKEN')
        def open_request(req, **kwargs):
            seen.append(req)
            return Response({'success': True})
        audit.opener = types.SimpleNamespace(open=open_request)
        obj, meta = audit.get('/api/health')
        self.assertEqual(seen[0].get_method(), 'GET')
        self.assertNotIn('TOKEN', seen[0].full_url)
        self.assertEqual(seen[0].get_header('Authorization'), 'Bearer TOKEN')
        self.assertNotIn('TOKEN', json.dumps(meta))

    def test_local_quorum_sends_no_authorization(self):
        audit = m.Audit('https://localhost:7443', '')
        def open_request(req, **kwargs):
            self.assertIsNone(req.get_header('Authorization'))
            self.assertEqual(req.get_method(), 'GET')
            return Response({'quorumAchieved': True})
        audit.opener = types.SimpleNamespace(open=open_request)
        audit.get('/quorum')

    def test_http_failure_does_not_export_body_or_claim_empty_success(self):
        audit = m.Audit('https://example.invalid', 'TOKEN')
        def fail(*args, **kwargs):
            raise HTTPError('https://example.invalid', 403, 'SECRET', {}, io.BytesIO(b'PRIVATEBODY'))
        audit.opener = types.SimpleNamespace(open=fail)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(audit.listing('/api/health/alarms', 'alarms', m.alarm), [])
        entry = audit.entries[0]
        self.assertEqual(entry['status'], 'http_error')
        self.assertFalse(entry['complete'])
        self.assertNotIn('SECRET', json.dumps(entry))
        self.assertNotIn('PRIVATEBODY', json.dumps(entry))

    def test_pagination_and_partial_failures(self):
        audit = m.Audit('https://example.invalid', 'TOKEN')
        def page(ep, **query):
            if query['offset'] == 0:
                return {'alarms': [{'id': 1, 'severity': 'critical'}], 'meta': {'total': 2}}, {'status': 'ok', 'http': 200}
            return None, {'status': 'http_error', 'http': 500}
        audit.get = page
        with contextlib.redirect_stderr(io.StringIO()): audit.listing('/api/health/alarms', 'alarms', m.alarm)
        entry = audit.entries[0]
        self.assertFalse(entry['complete'])
        self.assertEqual(entry['returned'], 1)
        self.assertEqual(entry['status'], 'http_error')

    def test_snapshot_unpaged_shape_and_missing_pagination(self):
        audit = m.Audit('https://example.invalid', 'TOKEN')
        audit.get = lambda *args, **kw: ({'snapshots': []}, {'status': 'ok'})
        with contextlib.redirect_stderr(io.StringIO()): audit.listing('/api/servers/1/snapshots', 'snapshots', m.snapshot, unpaged=True)
        self.assertTrue(audit.entries[0]['complete'])
        audit.get = lambda *args, **kw: ({'alarms': []}, {'status': 'ok'})
        with contextlib.redirect_stderr(io.StringIO()): audit.listing('/api/health/alarms', 'alarms', m.alarm)
        self.assertIsNone(audit.entries[1]['complete'])

    def test_unknown_nested_shapes_are_recorded(self):
        audit = m.Audit('https://example.invalid', 'TOKEN')
        audit.get = lambda *args, **kw: ({'server': 'invalid'}, {'status': 'ok'})
        with contextlib.redirect_stderr(io.StringIO()):
            audit.one('/api/servers/1', lambda obj: m.server(obj['server']))
        self.assertEqual(audit.entries[0]['status'], 'unexpected_shape')

    def test_request_budget_prevents_network_use(self):
        audit = m.Audit('https://example.invalid', 'TOKEN')
        audit.calls = 100
        audit.opener = types.SimpleNamespace(open=lambda *args, **kw: self.fail('unexpected network request'))
        self.assertEqual(audit.get('/api/health')[1]['status'], 'skipped')
        audit.calls = 0; audit.deadline = time.monotonic() - 1
        self.assertEqual(audit.get('/api/health')[1]['status'], 'skipped')

    def test_report_is_private_and_redacts_escaped_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'private/report.txt'
            token = 'token"with\\quotes'
            m.atomic_report(path, {'name': token, token: [token]}, token)
            result = json.loads(path.read_text())
            self.assertEqual(result['name'], '[REDACTED]')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_manager_end_to_end_uses_selected_cloud_and_filters_secrets(self):
        class FakeAudit(m.Audit):
            def get(self, ep, **query):
                meta = {'status': 'ok', 'http': 200}
                self.calls += 1
                if ep == '/api/zones': return {'zones': [{'id': 1}, {'id': 2}], 'meta': {'total': 2}}, meta
                if ep == '/api/clusters': return {'clusters': [{'id': 1, 'zone': {'id': 1}, 'servicePassword': 'SECRET'}], 'meta': {'total': 1}}, meta
                if ep == '/api/servers': return {'servers': [{'id': 3, 'name': 'ExampleVM', 'zone': {'id': 1}, 'apiKey': 'SECRET'}], 'meta': {'total': 1}}, meta
                if ep == '/api/virtual-switches': return {'virtualSwitches': [{'id': 9, 'name': 'vs0', 'clusterId': 1}]}, meta
                if ep == '/api/virtual-switches/9/uplinks': return {'uplinks': [{'id': 1, 'serverId': 3, 'nic1': 'eth0', 'syncStatus': 'in-sync'}]}, meta
                if ep.endswith('/snapshots'): return {'snapshots': [{'id': 7, 'name': 'snapshot', 'snapshotCreated': '2026-11-05', 'description': 'SECRET'}]}, meta
                if ep.endswith('/data-stores') or ep.endswith('/datastores'): return {'datastores': [], 'meta': {'total': 0}}, meta
                if ep in ('/api/health/alarms', '/api/monitoring/checks', '/api/monitoring/incidents'):
                    key = ep.rsplit('/',1)[1]
                    return {key: [], 'meta': {'total': 0}}, meta
                return {}, meta
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'audit.txt'
            argv = ['audit', '--url', 'https://example.invalid', '--cloud-id', '1', '--output', str(path)]
            with patch.object(m, 'Audit', FakeAudit), patch.object(m.getpass, 'getpass', return_value='TOKEN'), patch.object(m.sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                m.main()
            text = path.read_text(); report = json.loads(text)
            self.assertNotIn('SECRET', text)
            self.assertNotIn('TOKEN', text)
            self.assertIn('/api/servers/3/snapshots', [e['endpoint'] for e in report['entries']])
            self.assertIn('/api/servers/3', [e['endpoint'] for e in report['entries']])
            self.assertIn('/api/virtual-switches/9/uplinks', [e['endpoint'] for e in report['entries']])
            self.assertNotIn('/api/zones/2/data-stores', [e['endpoint'] for e in report['entries']])


if __name__ == '__main__': unittest.main()
