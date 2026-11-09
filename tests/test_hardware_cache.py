# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from test_infrastructure import infra, fixture, states
from test_morpheus import agent, State


def stamp(seconds=0):
    return (datetime.now(timezone.utc)-timedelta(seconds=seconds)).isoformat()


def host():
    return {'id':1,'name':'ExampleHypervisor','stats':{'ts':stamp(),'cpuUsage':10,'sensors':[{'name':'PSU','status':'ok','reading':'Present','private_key':'SECRET'}]}}


class HardwareCacheTests(unittest.TestCase):
    def test_detail_endpoint_when_list_is_missing(self):
        h=host();h['stats'].pop('sensors')
        detail=host();detail['stats']['ts']=stamp(60)
        class API:
            def get(self,endpoint):
                self.endpoint=endpoint
                return {'server':detail}
        api=API();snapshot,source=agent.resolve_hardware(api,h)
        self.assertEqual(source,'detail');self.assertEqual(api.endpoint,'servers/1')
        normalized=agent.normalize_hypervisor(h,snapshot=snapshot,hardware_source=source)
        self.assertEqual(normalized['hardware_timestamp'],detail['stats']['ts'])
        self.assertEqual(normalized['stats']['cpuUsage'],10)
        self.assertNotIn('SECRET',json.dumps(normalized))

    def test_cache_keeps_original_time_and_private_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=agent.HardwareCache(Path(tmp)/'hardware')
            class API:
                hardware_cache=cache
                def get(self,endpoint):raise agent.CollectionError('unavailable')
            h=host();old=stamp(80);h['stats']['ts']=old
            agent.resolve_hardware(API(),h)
            self.assertEqual(cache.path(1).stat().st_mode & 0o777,0o600)
            h['stats']={'ts':stamp(),'cpuUsage':11}
            snapshot,source=agent.resolve_hardware(API(),h)
            self.assertEqual(source,'cache');self.assertEqual(snapshot['timestamp'],old)
            normalized=agent.normalize_hypervisor(h,snapshot=snapshot,hardware_source=source)
            rows=list(infra.check_hardware(infra.item_name(normalized),{'age_warn':120,'age_crit':900},{'hypervisors':[normalized]}))
            self.assertEqual(max(states(rows)),State.OK)
            self.assertTrue(any('last valid' in getattr(r,'summary','') for r in rows))

    def test_cached_data_ages_to_warning_and_critical(self):
        h=agent.normalize_hypervisor(host());h['hardware_source']='cache'
        for seconds,expected in [(150,State.WARN),(1000,State.CRIT)]:
            h['hardware_timestamp']=stamp(seconds)
            rows=list(infra.check_hardware(infra.item_name(h),{'age_warn':120,'age_crit':900},{'hypervisors':[h]}))
            self.assertIn(expected,states(rows))

    def test_hardware_failure_not_hidden_by_cache(self):
        h=host();h['stats']['sensors'][0]['status']='critical'
        h=agent.normalize_hypervisor(h);h['hardware_source']='cache'
        rows=list(infra.check_hardware(infra.item_name(h),{'age_warn':120,'age_crit':900},{'hypervisors':[h]}))
        self.assertIn(State.CRIT,states(rows))

    def test_no_history_stays_unknown(self):
        h=host();h['stats'].pop('sensors')
        class API:
            def get(self,endpoint):return {'server':h}
        snap,source=agent.resolve_hardware(API(),h)
        h=agent.normalize_hypervisor(h,snapshot=snap,hardware_source=source)
        rows=list(infra.check_hardware(infra.item_name(h),{}, {'hypervisors':[h]}))
        self.assertIn(State.UNKNOWN,states(rows))

    def test_corrupted_cache_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=agent.HardwareCache(tmp);cache.path(1).write_text('{invalid')
            self.assertIsNone(cache.read(1))
            cache.path(1).write_text(json.dumps({'timestamp':stamp(),'sensors':[]}))
            self.assertIsNone(cache.read(1))
            with self.assertRaises(ValueError):cache.path('../other')

    def test_fresh_snapshot_replaces_cached_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=agent.HardwareCache(tmp)
            old=host();old['stats']['ts']=stamp(400);old['stats']['sensors'][0]['status']='warning'
            cache.write(1,agent.sensor_snapshot(old))
            class API:hardware_cache=cache
            h=host();snap,source=agent.resolve_hardware(API(),h)
            self.assertEqual(source,'list');self.assertEqual(cache.read(1)['sensors'][0]['status'],'ok')

if __name__=='__main__':unittest.main()
