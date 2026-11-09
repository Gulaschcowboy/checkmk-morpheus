# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import copy
import json
import types
import unittest
from datetime import datetime, timezone, timedelta
from test_morpheus import ROOT, load, agent, State
from test_infrastructure import states, metric
from test_morpheus import checks

extended = load('extended_checks', ROOT/'src/morpheus/agent_based/extended.py')


def date(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def fixture():
    return json.loads((ROOT/'tests/sample_extended.json').read_text())


class ExtendedTests(unittest.TestCase):
    def test_zero_ram_without_guest_agent_heartbeat_is_unverified(self):
        vm = {'powerState':'on', 'guestAgentStatus':'disconnected', 'stats':{'ts':date(0), 'usedMemory':0, 'maxMemory':100}}
        rows = list(checks.check_vm_metrics('Memory', {}, vm))
        self.assertIn(State.UNKNOWN, states(rows))
        self.assertFalse(any(r.args and r.args[0]=='morpheus_vm_memory_percent' for r in rows))

    def test_zero_snapshots_is_ok_but_failed_request_is_unknown(self):
        rows = list(extended.check_snapshots({}, {'snapshots': {'success': True, 'data': []}}))
        self.assertEqual(max(states(rows)), State.OK)
        self.assertEqual(metric(rows, 'morpheus_snapshot_count'), 0)
        rows = list(extended.check_snapshots({}, {'snapshots': {'success': False, 'error': 'HTTP 403'}}))
        self.assertEqual(max(states(rows)), State.UNKNOWN)
        self.assertFalse(any(r.args for r in rows))

    def test_snapshot_age_levels_and_missing_size(self):
        vm = {'snapshots': {'success': True, 'data': [{'id': 1, 'snapshotCreated': date(-8), 'maxStorage': None}]}}
        rows = list(extended.check_snapshots({}, vm))
        self.assertIn(State.WARN, states(rows))
        self.assertFalse(any(r.args and r.args[0]=='morpheus_snapshot_size_bytes' for r in rows))
        vm['snapshots']['data'][0]['snapshotCreated'] = date(-31)
        self.assertIn(State.CRIT, states(list(extended.check_snapshots({}, vm))))

    def test_snapshot_failure_and_invalid_date_are_not_healthy(self):
        vm = {'snapshots': {'success': True, 'data': [{'id': 1, 'status': 'failed', 'dateCreated': date(-1)}]}}
        self.assertIn(State.CRIT, states(list(extended.check_snapshots({}, vm))))
        vm['snapshots']['data'][0].update(status='available', dateCreated='bad')
        self.assertIn(State.UNKNOWN, states(list(extended.check_snapshots({}, vm))))

    def test_license_full_allocation_warns_and_null_is_unlimited(self):
        source = fixture()['extensions']
        self.assertEqual([s.item for s in extended.discover_license_limits(source)], ['maxMvmSockets'])
        rows = list(extended.check_license_limit('maxMvmSockets', source))
        self.assertEqual(max(states(rows)), State.WARN)
        self.assertEqual(metric(rows, 'morpheus_license_usage_percent'), 100)
        source['license']['data']['limits'][0]['used'] = 3
        self.assertIn(State.CRIT, states(list(extended.check_license_limit('maxMvmSockets', source))))

    def test_zero_license_limit_is_enforced_without_dividing_by_zero(self):
        section = {'license': {'success': True, 'data': {'limits': [{'code': 'zero', 'max': 0, 'used': 0}]}}}
        rows = list(extended.check_license_limit('zero', section))
        self.assertEqual(max(states(rows)), State.WARN)
        self.assertFalse(any(r.args and r.args[0]=='morpheus_license_usage_percent' for r in rows))

    def test_license_expiry_and_missing_date(self):
        for days, state in ((40, State.OK), (20, State.WARN), (3, State.CRIT), (-1, State.CRIT)):
            data = {'license': {'success': True, 'data': {'installed': [{'endDate': date(days)}]}}}
            self.assertEqual(max(states(list(extended.check_license({}, data)))), state)
        self.assertIn(State.UNKNOWN, states(list(extended.check_license({}, {'license': {'success': True, 'data': {}}}))))

    def test_alarm_severity_and_acknowledged_closed_filter(self):
        section = {'success': True, 'data': [
            {'id': 1, 'name': 'Active warning', 'status': 'warning'},
            {'id': 2, 'name': 'Acknowledged', 'status': 'critical', 'acknowledged': True},
            {'id': 3, 'name': 'Closed', 'status': 'critical', 'endDate': date(-1)},
        ]}
        rows = list(extended.check_alarm_dataset(section))
        self.assertEqual(max(states(rows)), State.WARN)
        self.assertEqual(metric(rows, 'morpheus_alarms_critical'), 0)
        section['data'].append({'id': 4, 'status': 'critical'})
        self.assertEqual(max(states(list(extended.check_alarm_dataset(section)))), State.CRIT)

    def test_unknown_alarm_severity_is_not_ok(self):
        rows = list(extended.check_alarm_dataset({'success': True, 'data': [{'id': 1, 'status': 'new-severity'}]}))
        self.assertIn(State.UNKNOWN, states(rows))

    def test_uplink_old_sync_time_is_not_treated_as_measurement_age(self):
        section = fixture()['extensions']; name = list(extended.discover_uplinks(section))[0].item
        rows = list(extended.check_uplink(name, section))
        self.assertEqual(max(states(rows)), State.OK)
        self.assertTrue(any('not a periodic link measurement' in getattr(r,'notice','') for r in rows))

    def test_uplink_drift_error_and_host_down(self):
        section = fixture()['extensions']; uplink = section['virtual_switches'][0]['uplinks']['data'][0]
        name = list(extended.discover_uplinks(section))[0].item
        for status, state in (('drifted', State.WARN), ('pending', State.WARN), ('error', State.CRIT), ('unknown-new', State.UNKNOWN)):
            uplink['syncStatus'] = status
            self.assertEqual(max(states(list(extended.check_uplink(name, section)))), state)
        uplink.update(syncStatus='in-sync', host={'powerState':'unknown','serverGroupMemberStatus':'unclean'})
        self.assertEqual(max(states(list(extended.check_uplink(name, section)))), State.CRIT)

    def test_volume_no_guest_fullness_thresholds_or_fake_timestamp(self):
        vm = fixture()['vm']; volume = vm['volumes'][0]
        volume['usedStorage'] = volume['maxStorage']
        rows = list(extended.check_volume(volume['name'], vm))
        self.assertEqual(max(states(rows)), State.OK)
        self.assertFalse(any(r.args and r.args[0]=='morpheus_data_age' for r in rows))
        self.assertTrue(any('guest filesystem usage not verified' in getattr(r,'summary','') for r in rows))
        volume['online'] = False
        self.assertIn(State.CRIT, states(list(extended.check_volume(volume['name'], vm))))

    def test_volume_normalizer_filters_optical_and_secrets(self):
        raw = {'volumes': [
            {'id': 1, 'deviceName': '/dev/sda', 'maxStorage': 0},
            {'id': 2, 'deviceName': '/dev/sdb', 'maxStorage': 100, 'diskType': 'cdrom'},
            {'id': 3, 'deviceName': '/dev/vda', 'maxStorage': 100, 'usedStorage': 50, 'apiKey': 'SECRET'},
        ]}
        result = agent.normalize_volumes(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], '/dev/vda')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_unpaged_rejects_partial_duplicate_and_bad_arrays(self):
        for response in ({'snapshots': 'bad'}, {'snapshots': [{'id':1},{'id':1}]}, {'snapshots':[], 'meta':{'total':2}}):
            api = types.SimpleNamespace(get=lambda *a, **k: response)
            with self.assertRaises(agent.CollectionError): agent.unpaged(api, 'servers/1/snapshots', 'snapshots')

    def test_optional_permission_failure_keeps_vm_inventory(self):
        class API:
            def get(self, path, **kwargs):
                if path=='health': return {'health':{'success':True}}
                raise agent.CollectionError(path + ': HTTP 403')
            def listing(self, path, key, **kwargs):
                return [{'id':1,'name':'Example-HVM'}] if path=='zones' else [{'id':3,'name':'ExampleVM','stats':{},'powerState':'off'}]
        result = agent.collect(API(), skip_infrastructure=True, features={'snapshots':True})
        self.assertEqual(len(result['vms']),1)
        self.assertFalse(result['vms'][0]['snapshots']['success'])
        self.assertIn('<<<<morpheus-vm-3>>>>', agent.render(result,1))
        self.assertIn(State.UNKNOWN,states(list(extended.check_snapshots({},result['vms'][0]))))

    def test_optional_bad_schema_is_reported_without_erasing_vms(self):
        api=types.SimpleNamespace(get=lambda *a,**k: {'licenseLimits': 5})
        # A selected field action that encounters unexpected structure must fail locally.
        vms=[{'id':3}]
        result=agent.collect_extensions(api,vms,{}, {'license':True})
        self.assertEqual(len(vms),1)
        self.assertFalse(result['license']['success'])
        self.assertTrue(result['errors'])
        self.assertIn(State.UNKNOWN,states(list(extended.check_license({},result))))

    def test_known_snapshot_and_license_faults_are_not_hidden_by_unknown_dates(self):
        vm={'snapshots':{'success':True,'data':[{'id':1,'status':'failed'}]}}
        self.assertEqual(max(states(list(extended.check_snapshots({},vm)))),State.CRIT)
        source={'license':{'success':True,'data':{'installed':[{'endDate':date(-1)},{}]}}}
        self.assertEqual(max(states(list(extended.check_license({},source)))),State.CRIT)

    def test_optional_collector_normalizes_and_matches_alarm_by_id(self):
        class API:
            def get(self, path, **kwargs):
                if path.endswith('/snapshots'): return {'snapshots':[]}
                if path=='license': return {'license': {'endDate': date(60), 'keyId':'SECRET'},'licenseLimits':[]}
                if path=='virtual-switches': return {'virtualSwitches':[{'id':1,'name':'vs0','status':'available','password':'SECRET'}]}
                if path.endswith('/uplinks'): return {'uplinks':[{'id':1,'serverId':1,'serverName':'Host1','nic1':'eth0','syncStatus':'in-sync'}]}
                raise AssertionError(path)
            def listing(self, path, key, **kwargs):
                self.last_endpoint=path
                return [{'id':1,'refType':'computeServer','refId':3,'name':'Old VM name','status':'warning','config':{'password':'SECRET'}}]
        vms=[{'id':3,'name':'New VM name'}]
        result=agent.collect_extensions(API(),vms,{'clusters':[{'id':1,'name':'ExampleCluster'}], 'hypervisors':[{'id':1,'powerState':'on'}]},dict(snapshots=True,license=True,alarms=True,virtual_switches=True))
        self.assertFalse(result['errors'])
        self.assertEqual(len(vms[0]['alarms']['data']),1)
        self.assertEqual(len(result['virtual_switches']),1)
        self.assertNotIn('SECRET',json.dumps([vms,result]))

    def test_snapshot_overview_does_not_report_partial_total_as_metric(self):
        section = fixture()['inventory']
        self.assertEqual(metric(list(extended.check_inventory_snapshots(section)), 'morpheus_snapshot_count'), 2)
        del section['vms'][1]['snapshot_count']
        rows = list(extended.check_inventory_snapshots(section))
        self.assertEqual(states(rows), [State.UNKNOWN])
        self.assertFalse(any(row.args and row.args[0] == 'morpheus_snapshot_count' for row in rows))

    def test_vm_power_distinguishes_equal_names_and_expected_state(self):
        section = {'vms': [
            {'id': 1, 'name': 'ExampleVM', 'powerState': 'on'},
            {'id': 2, 'name': 'ExampleVM', 'powerState': 'off'},
        ]}
        on, off = [service.item for service in extended.discover_vm_power(section)]
        self.assertNotEqual(on, off)
        self.assertEqual(states(list(extended.check_vm_power(on, {'expected_power': 'on'}, section))), [State.OK])
        self.assertEqual(states(list(extended.check_vm_power(off, {}, section))), [State.OK])
        self.assertEqual(states(list(extended.check_vm_power(off, {'expected_power': 'on'}, section))), [State.CRIT])
        self.assertEqual(states(list(extended.check_vm_power(off, {}, {'vms': section['vms'][:1]}))), [State.WARN])

    def test_all_new_checks_discover_and_return_results(self):
        sample=fixture()
        for name, plugin in vars(extended).items():
            if not name.startswith('check_plugin_'): continue
            data = sample[{'morpheus_vm': 'vm', 'morpheus_extended': 'extensions', 'morpheus_vm_inventory': 'inventory'}[plugin.sections[0]]]
            for service in plugin.discovery_function(data):
                args = {'section':data}
                if getattr(service,'item',None) is not None: args['item']=service.item
                if getattr(plugin,'check_default_parameters',None) is not None: args['params']=plugin.check_default_parameters
                self.assertTrue(list(plugin.check_function(**args)),name)


if __name__=='__main__': unittest.main()
