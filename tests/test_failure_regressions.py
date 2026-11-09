# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Power-loss and partial-statistics regressions observed during HVM tests."""
import copy
import json
import types
from datetime import datetime, timezone, timedelta
from test_infrastructure import infra, fixture, states, metric
from test_morpheus import agent, checks, State
import test_vm_stats_cache as vm_cache_tests
import unittest


class FailureTests(unittest.TestCase):
    def failed_host(self):
        data = fixture()
        h = data['hypervisors'][0]
        h.update(status='warning', powerState='unknown', serverGroupMemberStatus='unclean')
        h['stats'].update(cpuUsage=0, usedMemory=0)
        return data, h, infra.item_name(h)

    def test_unclean_is_critical_despite_unknown_power(self):
        data, h, item = self.failed_host()
        self.assertEqual(max(states(list(infra.check_hypervisor_state(item, data)))), State.CRIT)

    def test_outage_never_publishes_zero_usage_or_old_sensors(self):
        data, h, item = self.failed_host()
        for function in (infra.check_hypervisor_cpu, infra.check_hypervisor_memory, infra.check_hardware):
            rows = list(function(item, {}, data))
            self.assertEqual(max(states(rows)), State.CRIT)
            self.assertFalse(any(r.args for r in rows))

    def test_fenced_and_offline_members_are_critical(self):
        for status in ('unclean', 'fenced', 'offline', 'unreachable', 'lost'):
            data = fixture()
            c = data['clusters'][0]
            c['members'][0]['serverGroupMemberStatus'] = status
            rows = list(infra.check_cluster(infra.item_name(c), {}, data))
            self.assertEqual(max(states(rows)), State.CRIT, status)

    def test_unknown_membership_does_not_become_zero_usage(self):
        data, h, item = self.failed_host()
        h.update(powerState='on', status='provisioned', serverGroupMemberStatus='unrecognized')
        rows = list(infra.check_hypervisor_cpu(item, {}, data))
        self.assertEqual(max(states(rows)), State.UNKNOWN)
        self.assertFalse(any(r.args for r in rows))

    def test_power_off_blocks_readings_even_with_online_membership(self):
        data, h, item = self.failed_host()
        h.update(powerState='off', serverGroupMemberStatus='online')
        rows = list(infra.check_hypervisor_memory(item, {}, data))
        self.assertEqual(max(states(rows)), State.CRIT)
        self.assertFalse(any(r.args for r in rows))

    def test_recovery_restores_real_metrics(self):
        data, h, item = self.failed_host()
        h.update(status='provisioned', powerState='on', serverGroupMemberStatus='online')
        h['stats']['cpuUsage'] = 13.28
        rows = list(infra.check_hypervisor_cpu(item, {}, data))
        self.assertEqual(max(states(rows)), State.OK)
        self.assertEqual(metric(rows, 'morpheus_hypervisor_cpu'), 13.28)

    def test_cluster_member_graph_and_no_stale_counts(self):
        data = fixture()
        c = data['clusters'][0]
        c['members'][0]['serverGroupMemberStatus'] = 'unclean'
        item = infra.item_name(c)
        rows = list(infra.check_cluster(item, {}, data))
        self.assertEqual(metric(rows, 'morpheus_cluster_members_online'), len(c['members']) - 1)
        self.assertEqual(metric(rows, 'morpheus_cluster_members_total'), len(c['members']))
        c['lastSync'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.assertFalse(any(r.args and r.args[0].startswith('morpheus_cluster_members') for r in infra.check_cluster(item, {}, data)))

    def test_empty_membership_is_not_healthy(self):
        data = fixture(); c = data['clusters'][0]; c['members'] = []
        self.assertIn(State.UNKNOWN, states(list(infra.check_cluster(infra.item_name(c), {}, data))))


class IndependentMetricTests(unittest.TestCase):
    def setUp(self):
        # Reuse fixture construction without inheriting and rerunning its tests.
        self.context = vm_cache_tests.VMCacheTests()
        self.context.setUp()
        self.addCleanup(self.context.doCleanups)
        self.vm, self.api, self.cache = self.context.vm, self.context.api, self.context.cache

    def current(self):
        vm = copy.deepcopy(self.vm)
        vm.pop('metric_snapshots', None)
        vm['stats_source'] = 'list'
        vm['stats']['ts'] = datetime.now(timezone.utc).isoformat()
        return vm

    def test_missing_ram_keeps_fresh_cpu_and_storage(self):
        self.vm['stats']['ts'] = (datetime.now(timezone.utc) - timedelta(seconds=1000)).isoformat()
        agent.retain_vm_stats(self.api, [self.vm])
        vm = self.current(); vm['stats'].pop('usedMemory')
        agent.retain_vm_stats(self.api, [vm])
        self.assertEqual(vm['metric_snapshots']['Memory']['source'], 'cache')
        for item in ('CPU', 'Storage'):
            self.assertEqual(vm['metric_snapshots'][item]['source'], 'list')
            self.assertEqual(max(states(list(checks.check_vm_metrics(item, {}, vm)))), State.OK)
        self.assertIn(State.CRIT, states(list(checks.check_vm_metrics('Memory', {}, vm))))

    def test_partial_initial_sample_is_cached_without_complete_baseline(self):
        vm = self.current(); vm['stats'].pop('cpuUsage')
        agent.retain_vm_stats(self.api, [vm])
        later = self.current(); later['stats'] = {'ts': later['stats']['ts']}
        agent.retain_vm_stats(self.api, [later])
        self.assertIn('Memory', later['metric_snapshots'])
        self.assertNotIn('CPU', later['metric_snapshots'])

    def test_complementary_detail_samples_keep_individual_timestamps(self):
        vm = self.current(); vm['stats'].pop('usedMemory')
        list_ts = vm['stats']['ts']
        detail_stats = dict(self.vm['stats'])
        detail_stats.pop('cpuUsage')
        detail_ts = detail_stats['ts']
        api = types.SimpleNamespace(get=lambda path: {'server': {'id': vm['id'], 'stats': detail_stats}})
        agent.complete_vm_stats(api, [vm])
        agent.retain_vm_stats(api, [vm])
        output = json.loads(json.dumps(vm))
        self.assertEqual(output['metric_snapshots']['CPU']['stats']['ts'], list_ts)
        self.assertEqual(output['metric_snapshots']['Memory']['stats']['ts'], detail_ts)
        self.assertEqual(output['metric_snapshots']['Memory']['source'], 'detail')

    def test_legacy_cache_migrates_without_refreshing_time(self):
        legacy = {'stats': copy.deepcopy(self.vm['stats']), 'capacity': agent.pick(self.vm, agent.VM_CAPACITY_FIELDS)}
        self.cache.write(self.vm['id'], legacy)
        vm = self.current(); vm['stats'] = {'ts': vm['stats']['ts']}
        agent.retain_vm_stats(self.api, [vm])
        self.assertEqual(vm['metric_snapshots']['CPU']['stats']['ts'], legacy['stats']['ts'])
        self.assertEqual(self.cache.read(vm['id'])['schema'], 2)

    def test_invalid_ram_does_not_discard_valid_cpu(self):
        vm = self.current(); vm['stats']['usedMemory'] = vm['stats']['maxMemory'] + 1
        agent.retain_vm_stats(self.api, [vm])
        self.assertIn('CPU', vm['metric_snapshots'])
        self.assertNotIn('Memory', vm['metric_snapshots'])

    def test_disk_io_discovery_and_metrics_including_zero(self):
        vm = self.current(); vm['stats'].update(readIOPS=0, writeIOPS=7314)
        agent.retain_vm_stats(self.api, [vm])
        self.assertIn('Disk IO', [s.item for s in checks.discover_vm_metrics(vm)])
        rows = list(checks.check_vm_metrics('Disk IO', {}, vm))
        self.assertEqual(metric(rows, 'morpheus_vm_read_iops'), 0)
        self.assertEqual(metric(rows, 'morpheus_vm_write_iops'), 7314)
        self.assertEqual(max(states(rows)), State.OK)

    def test_disk_io_not_discovered_when_absent(self):
        vm = self.current()
        for key in ('readIOPS', 'writeIOPS'): vm['stats'].pop(key, None)
        agent.retain_vm_stats(self.api, [vm])
        self.assertNotIn('Disk IO', [s.item for s in checks.discover_vm_metrics(vm)])

    def test_stale_disk_io_is_not_published(self):
        vm = self.current()
        vm['stats'].update(readIOPS=1, writeIOPS=2, ts=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
        agent.retain_vm_stats(self.api, [vm])
        rows = list(checks.check_vm_metrics('Disk IO', {}, vm))
        self.assertIn(State.CRIT, states(rows))
        self.assertFalse(any(r.args and r.args[0].endswith('_iops') for r in rows))

    def test_future_timestamp_never_establishes_a_group(self):
        vm = self.current()
        vm['stats']['ts'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        agent.retain_vm_stats(self.api, [vm])
        self.assertFalse(vm['metric_snapshots'])

    def test_raw_untimestamped_aggregate_is_never_used(self):
        vm = self.current(); vm['stats'] = {'ts': vm['stats']['ts']}
        api = types.SimpleNamespace(get=lambda path: {
            'server': {'id': vm['id'], 'stats': vm['stats']},
            'stats': {'cpuUsage': 0, 'usedMemory': 0, 'maxMemory': 123}})
        agent.complete_vm_stats(api, [vm])
        self.assertFalse(vm['metric_snapshots'])


if __name__ == '__main__':
    unittest.main()
