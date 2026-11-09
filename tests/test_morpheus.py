# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import importlib.machinery
import importlib.util
import io
import json
import pathlib
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod

agent = load('collector', ROOT / 'src/morpheus/libexec/agent_morpheus')

# Function-level tests use a tiny result-object shim, NOT a Checkmk runtime.
# On-site cmk-validate-plugins remains required.
class Record:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.__dict__.update(kwargs)

class State:
    OK, WARN, CRIT, UNKNOWN = range(4)

api_stub = types.ModuleType('cmk.agent_based.v2')
api_stub.State = State
for attr in ('AgentSection', 'CheckPlugin', 'Service', 'Result', 'Metric'):
    setattr(api_stub, attr, type(attr, (Record,), {}))
sys.modules['cmk.agent_based.v2'] = api_stub
checks = load('checks', ROOT / 'src/morpheus/agent_based/morpheus.py')

FIXTURE = json.loads((ROOT / 'tests/sample_normalized.json').read_text())

class Tests(unittest.TestCase):
    def test_sample(self):
        self.assertEqual(FIXTURE['health']['buildVersion'], '9.1.0.1')
        self.assertEqual(FIXTURE['vms'][0]['status'], 'provisioned')
        self.assertEqual(FIXTURE['vms'][0]['powerState'], 'on')
        out = agent.render(FIXTURE, 1.2)
        self.assertIn('<<<<morpheus-vm-27>>>>', out)
        self.assertNotIn('PUBLIC KEY', out)
        self.assertEqual(checks.parse([[json.dumps(FIXTURE['health'])]])['buildVersion'], '9.1.0.1')

    def test_pagination(self):
        class Fake:
            def __init__(self): self.calls = []
            def get(self, endpoint, **kw):
                self.calls.append(kw['offset'])
                return {'servers': [{'id': i} for i in range(kw['offset'], min(kw['offset'] + 2, 5))], 'meta': {'total': 5}}
        fake = Fake()
        self.assertEqual(len(agent.API.listing(fake, 'servers', 'servers')), 5)
        self.assertEqual(fake.calls, [0, 2, 4])

    def test_pagination_incomplete(self):
        fake = types.SimpleNamespace(get=lambda *a, **k: {'servers': [], 'meta': {'total': 10}})
        with self.assertRaises(agent.CollectionError): agent.API.listing(fake, 'servers', 'servers')

    def test_pagination_duplicate(self):
        fake = types.SimpleNamespace(get=lambda *a, **k: {'servers': [{'id': 1}], 'meta': {'total': 3}})
        with self.assertRaises(agent.CollectionError): agent.API.listing(fake, 'servers', 'servers')

    def test_whitelist(self):
        vm = agent.normalize_vm({'id': 1, 'name': 'x', 'sshPassword': 'SECRET', 'config': {'password': 'SECRET'}, 'stats': {'cpuUsage': 0.25, 'secret': 'SECRET'}})
        h = agent.normalize_health({'health': {'database': {'stats': {'password': 'SECRET'}, 'usedConnections': 5}}})
        self.assertNotIn('SECRET', json.dumps([vm, h]))

    def test_name_modes(self):
        vm = {'id': 3, 'name': 'VM1', 'hostname': 'vm1.example'}
        self.assertEqual(agent.host_name(vm, 'id', 'morpheus-vm-'), 'morpheus-vm-3')
        self.assertEqual(agent.host_name(vm, 'hostname', ''), 'vm1.example')
        with self.assertRaises(agent.CollectionError): agent.host_name({'id': 1, 'name': 'x\n<<<<evil>>>>'}, 'name', '')

    def test_cloud_names_and_duplicate_resolution(self):
        clouds = [{'id': 1, 'name': 'Example-HVM'}, {'id': 2, 'name': 'Example-VMware'}]
        agent.assign_service_items(clouds)
        self.assertEqual([x.item for x in checks.discover_clouds(clouds)], ['Example-HVM', 'Example-VMware'])
        rows = list(checks.check_clouds('Example-HVM', {}, clouds))
        self.assertTrue(any(getattr(r, 'notice', '') == 'Morpheus cloud ID: 1' for r in rows))
        clouds[1]['name'] = 'Example-HVM'
        agent.assign_service_items(clouds)
        self.assertEqual([x.item for x in checks.discover_clouds(clouds)], ['Example-HVM (ID 1)', 'Example-HVM (ID 2)'])

    def test_name_collision(self):
        class Fake:
            def get(self, *a, **k): return {'health': {}}
            def listing(self, endpoint, *a, **k):
                return [] if endpoint == 'zones' else [{'id': 1, 'name': 'x'}, {'id': 2, 'name': 'x'}]
        with self.assertRaises(agent.CollectionError): agent.collect(Fake(), name_mode='name', prefix='')

    def test_no_partial_piggyback(self):
        class Fake:
            def get(self, *a, **k): return {'health': {}}
            def listing(self, *a, **k): raise agent.CollectionError('no inventory')
        output = io.StringIO()
        with patch.object(sys, 'argv', ['agent_morpheus', '--url', 'https://example', '--token', 'SECRET']), patch.object(agent, 'API', return_value=Fake()), patch('sys.stdout', output), patch('sys.stderr', io.StringIO()):
            self.assertEqual(agent.main(), 1)
        self.assertNotIn('<<<<', output.getvalue())
        self.assertNotIn('SECRET', output.getvalue())
        self.assertIn('"success":false', output.getvalue())

    def test_https_and_redirect(self):
        for url in ('http://example', 'https://user:secret@example', 'https://example/api', 'https://example?x=1'):
            with self.assertRaises(agent.CollectionError): agent.API(url, 'token')
        self.assertIsNone(agent.NoRedirect().redirect_request(None, None, 302, 'x', {}, 'https://other'))

    def test_power_defaults(self):
        vm = dict(FIXTURE['vms'][0], powerState='off')
        states = [r.state for r in checks.check_vm({}, vm) if hasattr(r, 'state')]
        self.assertNotIn(State.CRIT, states)
        states = [r.state for r in checks.check_vm({'expected_power': 'on'}, vm) if hasattr(r, 'state')]
        self.assertIn(State.CRIT, states)

    def fresh_vm(self):
        vm = dict(FIXTURE['vms'][0]); vm['stats'] = dict(vm['stats'])
        vm['stats']['ts'] = datetime.now(timezone.utc).isoformat()
        return vm

    def test_cpu_not_scaled(self):
        vm = self.fresh_vm(); vm['stats']['cpuUsage'] = 0.25
        rows = list(checks.check_vm_metrics('CPU', {}, vm))
        value = next(r.args[1] for r in rows if r.args and r.args[0] == 'morpheus_vm_cpu_percent')
        self.assertEqual(value, 0.25)

    def test_multicore_cpu_above_100_is_not_unknown_or_clamped(self):
        vm = self.fresh_vm(); vm['stats']['cpuUsage'] = 108.37176753233156
        rows = list(checks.check_vm_metrics('CPU', {}, vm))
        metric = next(r for r in rows if r.args and r.args[0] == 'morpheus_vm_cpu_percent')
        self.assertEqual(metric.args[1], 108.37176753233156)
        self.assertEqual(metric.boundaries, (0, None))
        self.assertFalse(any(getattr(r, 'state', None) == State.UNKNOWN for r in rows))
        self.assertTrue(any(getattr(r, 'state', None) == State.CRIT for r in rows))

    def test_cpu_levels_use_api_scale(self):
        vm = self.fresh_vm(); vm['stats']['cpuUsage'] = 108.37
        rows = list(checks.check_vm_metrics('CPU', {'warn': 180, 'crit': 190}, vm))
        self.assertTrue(all(r.state == State.OK for r in rows if hasattr(r, 'state')))

    def test_invalid_cpu_still_unknown(self):
        for value in (None, -1, True, float('nan'), float('inf')):
            vm = self.fresh_vm(); vm['stats']['cpuUsage'] = value
            rows = list(checks.check_vm_metrics('CPU', {}, vm))
            self.assertTrue(any(getattr(r, 'state', None) == State.UNKNOWN for r in rows))

    def test_other_percentages_keep_upper_bound(self):
        rows = list(checks.percent(108, 'memory', 'Memory'))
        self.assertTrue(any(getattr(r, 'state', None) == State.UNKNOWN for r in rows))

    def test_detail_snapshot_preserves_original_timestamp_and_whitelist(self):
        vm = self.fresh_vm()
        original_ts = vm['stats']['ts']
        vm['stats'] = {'ts': original_ts, 'maxMemory': 100}
        detail_stats = dict(FIXTURE['vms'][0]['stats'], ts='2026-10-29T10:00:00Z', secret='SECRET')
        api = types.SimpleNamespace(get=lambda path: {'server': {'id': vm['id'], 'stats': detail_stats}, 'stats': {'secret': 'SECRET'}})
        agent.complete_vm_stats(api, [vm])
        self.assertEqual(vm['stats_source'], 'detail')
        self.assertEqual(vm['stats']['ts'], '2026-10-29T10:00:00Z')
        self.assertNotIn('SECRET', json.dumps(vm))

    def test_detail_failure_keeps_inventory_and_list_readings(self):
        vm = self.fresh_vm(); vm['stats'].pop('usedMemory')
        previous = dict(vm['stats'])
        def fail(path): raise agent.CollectionError('SECRET')
        agent.complete_vm_stats(types.SimpleNamespace(get=fail), [vm])
        self.assertEqual(vm['stats'], previous)
        self.assertEqual(vm['stats_detail_status'], 'detail request failed')
        self.assertNotIn('SECRET', json.dumps(vm))

    def test_complete_vm_does_not_need_detail(self):
        vm = self.fresh_vm()
        with patch.object(agent.API, 'get', side_effect=AssertionError('unexpected lookup')):
            agent.complete_vm_stats(types.SimpleNamespace(), [vm])
        self.assertEqual(vm['stats_source'], 'list')

    def test_wrong_detail_id_is_rejected(self):
        vm = self.fresh_vm(); vm['stats'].pop('usedMemory')
        api = types.SimpleNamespace(get=lambda path: {'server': {'id': 999, 'stats': FIXTURE['vms'][0]['stats']}})
        agent.complete_vm_stats(api, [vm])
        self.assertNotIn('usedMemory', vm['stats'])
        self.assertEqual(vm['stats_detail_status'], 'invalid detail identity')

    def test_detail_does_not_mix_two_incomplete_samples(self):
        vm = self.fresh_vm(); vm['stats'].pop('usedMemory')
        stats = dict(vm['stats'], usedMemory=123)
        stats.pop('cpuUsage')
        api = types.SimpleNamespace(get=lambda path: {'server': {'id': vm['id'], 'stats': stats}})
        agent.complete_vm_stats(api, [vm])
        self.assertNotIn('usedMemory', vm['stats'])
        self.assertIn('cpuUsage', vm['stats'])

    def test_detail_limit_and_budget(self):
        calls = []
        def get(path):
            calls.append(path)
            return {'server': {'id': path.split('/')[-1], 'stats': {}}}
        vms = [{'id': i, 'powerState': 'on', 'stats': {}} for i in range(20)]
        agent.complete_vm_stats(types.SimpleNamespace(get=get), vms)
        self.assertEqual(len(calls), 10)
        self.assertIn('budget', vms[-1]['stats_detail_status'])
        calls.clear()
        agent.complete_vm_stats(types.SimpleNamespace(get=get, deadline=agent.time.monotonic() + 5), vms)
        self.assertEqual(calls, [])

    def test_detail_invalid_timestamp_is_not_refreshed(self):
        vm = self.fresh_vm(); vm['stats'].pop('usedMemory')
        for timestamp in (None, 'bad', '2026-10-29T10:00:00'):
            stats = dict(FIXTURE['vms'][0]['stats'], ts=timestamp)
            api = types.SimpleNamespace(get=lambda path: {'server': {'id': vm['id'], 'stats': stats}})
            agent.complete_vm_stats(api, [vm])
            self.assertNotIn('usedMemory', vm['stats'])
            self.assertEqual(vm['stats_detail_status'], 'invalid detail timestamp')

    def test_stale_data_no_cpu_metric(self):
        vm = self.fresh_vm(); vm['stats']['ts'] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        rows = list(checks.check_vm_metrics('CPU', {}, vm))
        self.assertTrue(any(getattr(r, 'state', None) == State.CRIT for r in rows))
        self.assertFalse(any(r.args and r.args[0] == 'morpheus_vm_cpu_percent' for r in rows))

    def test_missing_memory_unknown(self):
        vm = self.fresh_vm(); vm['stats'].pop('usedMemory')
        rows = list(checks.check_vm_metrics('Memory', {}, vm))
        self.assertTrue(any(getattr(r, 'state', None) == State.UNKNOWN for r in rows))

    def test_jvm_fraction(self):
        rows = list(checks.check_platform('memory', {}, FIXTURE['health']))
        value = next(r.args[1] for r in rows if r.args and r.args[0] == 'morpheus_jvm_percent')
        self.assertAlmostEqual(value, 76.41970982)

if __name__ == '__main__': unittest.main()
