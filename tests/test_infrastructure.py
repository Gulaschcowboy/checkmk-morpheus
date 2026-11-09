# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import copy
import json
from datetime import datetime, timezone, timedelta
import unittest
from test_morpheus import ROOT, load, agent, State

infra = load('infrastructure_checks', ROOT / 'src/morpheus/agent_based/infrastructure.py')
SAMPLE = json.loads((ROOT / 'tests/sample_infrastructure.json').read_text())


def fixture():
    data = copy.deepcopy(SAMPLE)
    now = datetime.now(timezone.utc).isoformat()
    for ds in data['datastores']: ds['sync_timestamp'] = now
    for hv in data['hypervisors']: hv['stats']['ts'] = now
    for c in data['clusters']: c['lastSync'] = now
    return data


def states(rows): return [r.state for r in rows if hasattr(r, 'state')]

def metric(rows, name): return next(r.args[1] for r in rows if r.args and r.args[0] == name)


class InfrastructureTests(unittest.TestCase):
    def test_readable_unique_names_and_identity_in_details(self):
        data = fixture()
        for key in ('datastores', 'hypervisors', 'clusters'):
            agent.assign_service_items(data[key])
            for obj in data[key]:
                self.assertEqual(infra.item_name(obj), obj['name'])
                self.assertIs(infra.find(data, key, obj['name']), obj)
                self.assertIn(str(obj['id']), infra.object_identity(obj).notice)

    def test_same_names_in_different_clouds(self):
        objects = [
            {'id': 1, 'name': 'local', 'zone': {'id': 1, 'name': 'Cloud A'}},
            {'id': 2, 'name': 'local', 'zone': {'id': 2, 'name': 'Cloud B'}},
        ]
        agent.assign_service_items(objects)
        self.assertEqual([infra.item_name(x) for x in objects], ['local (Cloud A)', 'local (Cloud B)'])
        section = {'datastores': objects}
        self.assertIs(infra.find(section, 'datastores', 'local (Cloud B)'), objects[1])

    def test_same_names_in_same_cloud_use_ids(self):
        objects = [{'id': i, 'name': 'local', 'zone': {'id': 1, 'name': 'A'}} for i in (1, 2)]
        agent.assign_service_items(objects)
        self.assertEqual([infra.item_name(x) for x in objects], ['local (A) (ID 1)', 'local (A) (ID 2)'])

    def test_name_disambiguation_is_independent_of_api_order(self):
        objects = [{'id': i, 'name': 'local', 'zone': {'id': i, 'name': 'A'}} for i in (1, 2)]
        agent.assign_service_items(objects)
        expected = {x['id']: x['service_item'] for x in objects}
        agent.assign_service_items(list(reversed(objects)))
        self.assertEqual(expected, {x['id']: x['service_item'] for x in objects})

    def test_indistinguishable_duplicate_inventory_is_rejected(self):
        objects = [{'id': 1, 'name': 'same'}, {'id': 1, 'name': 'same'}]
        with self.assertRaises(agent.CollectionError):
            agent.assign_service_items(objects)

    def test_hvm_capacity(self):
        data = fixture();ds = next(x for x in data['datastores'] if x['id'] == 8)
        rows = list(infra.check_datastore_usage(infra.item_name(ds), {}, data))
        self.assertAlmostEqual(metric(rows, 'morpheus_datastore_used_percent'), 2.0577790157)
        self.assertEqual(metric(rows, 'morpheus_datastore_size_bytes'), 12274182881280)
        self.assertEqual(max(states(rows)), State.OK)

    def test_capacity_thresholds(self):
        data=fixture();ds=data['datastores'][0];ds['storageSize']=100;ds['freeSpace']=15
        self.assertIn(State.WARN,states(list(infra.check_datastore_usage(infra.item_name(ds),{},data))))
        ds['freeSpace']=5
        self.assertIn(State.CRIT,states(list(infra.check_datastore_usage(infra.item_name(ds),{},data))))

    def test_missing_capacity_unknown(self):
        data=fixture();ds=next(x for x in data['datastores'] if x['storageSize'] is None)
        rows=list(infra.check_datastore_usage(infra.item_name(ds),{},data))
        self.assertIn(State.UNKNOWN,states(rows))
        self.assertFalse(any(r.args and r.args[0]=='morpheus_datastore_used_percent' for r in rows))

    def test_capacity_inconsistent(self):
        data=fixture();ds=data['datastores'][0];ds['storageSize']=10;ds['freeSpace']=11
        self.assertIn(State.UNKNOWN,states(list(infra.check_datastore_usage(infra.item_name(ds),{},data))))

    def test_capacity_stale(self):
        data=fixture();ds=data['datastores'][0];ds['sync_timestamp']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        rows=list(infra.check_datastore_usage(infra.item_name(ds),{},data))
        self.assertIn(State.CRIT,states(rows))
        self.assertFalse(any(r.args and r.args[0]=='morpheus_datastore_used_bytes' for r in rows))

    def test_offline_datastore(self):
        data=fixture();ds=data['datastores'][0];ds['online']=False
        self.assertIn(State.CRIT,states(list(infra.check_datastore_state(infra.item_name(ds),data))))

    def test_multipath_degraded_and_failed(self):
        data=fixture();ds=next(x for x in data['datastores'] if x.get('multipath'));name=infra.item_name(ds)
        self.assertEqual(max(states(list(infra.check_multipath(name,{},data)))),State.OK)
        ds['multipath']['multipathActive']=1;ds['multipath']['multipathFailed']=1
        self.assertIn(State.WARN,states(list(infra.check_multipath(name,{},data))))
        ds['multipath']['multipathActive']=0
        self.assertIn(State.CRIT,states(list(infra.check_multipath(name,{},data))))

    def test_hardware_no_reading_not_failure(self):
        data=fixture();hv=next(h for h in data['hypervisors'] if h['hardware_summary']['count'])
        rows=list(infra.check_hardware(infra.item_name(hv),{},data))
        self.assertEqual(max(states(rows)),State.OK)
        self.assertEqual(hv['hardware_summary']['unavailable'],20)

    def test_hardware_problem_propagates(self):
        data=fixture();hv=next(h for h in data['hypervisors'] if h['hardware_summary']['count'])
        hv['hardware_summary']['problems']=[{'name':'PSU','status':'critical'}]
        self.assertIn(State.CRIT,states(list(infra.check_hardware(infra.item_name(hv),{},data))))

    def test_member_failure_and_ha_policy(self):
        data=fixture();c=data['clusters'][0];name=infra.item_name(c)
        self.assertEqual(max(states(list(infra.check_cluster(name,{},data)))),State.OK)
        self.assertIn(State.CRIT,states(list(infra.check_cluster(name,{'expect_ha':True},data))))
        c['members'][0]['serverGroupMemberStatus']='offline'
        self.assertIn(State.CRIT,states(list(infra.check_cluster(name,{},data))))

    def test_syncing_is_transient_and_preserves_safeguards(self):
        data=fixture();c=data['clusters'][0];c['status']='syncing';name=infra.item_name(c)
        self.assertEqual(max(states(list(infra.check_cluster(name,{},data)))),State.OK)
        c['lastSync']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        self.assertIn(State.CRIT,states(list(infra.check_cluster(name,{},data))))
        c['lastSync']=datetime.now(timezone.utc).isoformat()
        c['members'][0]['serverGroupMemberStatus']='offline'
        self.assertIn(State.CRIT,states(list(infra.check_cluster(name,{},data))))

    def test_cluster_unknown_status_is_not_masked(self):
        data=fixture();c=data['clusters'][0];name=infra.item_name(c)
        c['status']='unexpected-status'
        self.assertIn(State.UNKNOWN,states(list(infra.check_cluster(name,{},data))))
        c['status']='error'
        self.assertIn(State.CRIT,states(list(infra.check_cluster(name,{},data))))

    def test_sensor_numeric_reading(self):
        data=fixture();hv=next(h for h in data['hypervisors'] if h['sensors']);sensor=next(s for s in hv['sensors'] if 'degrees C' in s.get('reading',''))
        rows=list(infra.check_sensor(infra.item_name(hv)+' / '+sensor['name'],{},data))
        self.assertGreater(metric(rows,'morpheus_sensor_temperature'),0)

    def test_datastore_normalizer_whitelist_and_conflict(self):
        ds={'id':8,'name':'x','freeSpace':10,'apiKey':'SECRET','config':{'password':'SECRET','multipathPaths':2}}
        out=agent.normalize_datastore(ds,{'id':1},None,{('1','8'):{100,200}})
        self.assertIsNone(out['storageSize']);self.assertNotIn('SECRET',json.dumps(out))

    def test_infra_failure_keeps_existing_datasets(self):
        class Fake:
            def listing(self,*a,**k):raise agent.CollectionError('HTTP 403')
        data=agent.collect_infrastructure(Fake(),[{'id':1}])
        self.assertEqual(len(data['errors']),3)
        self.assertIn(State.CRIT,states(list(infra.check_collection(data))))

    def test_cluster_datastore_is_used_and_deduplicated(self):
        class Fake:
            def listing(self,ep,key,**filters):
                if ep=='servers':return []
                if ep=='clusters':return [{'id':1,'name':'c','zone':{'id':1}}]
                ds={'id':1,'name':'ds','freeSpace':1}
                return [dict(ds,storageSize=10)] if ep.startswith('clusters/') else [ds]
        data=agent.collect_infrastructure(Fake(),[{'id':1}])
        self.assertEqual(len(data['datastores']),1)
        self.assertEqual(data['datastores'][0]['storageSize'],10)

    def test_all_items_unique(self):
        data=fixture()
        for key in ['datastores','hypervisors','clusters']:
            items=[infra.item_name(x) for x in data[key]];self.assertEqual(len(items),len(set(items)))

if __name__=='__main__':unittest.main()
