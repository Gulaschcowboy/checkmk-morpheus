# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import copy
import json
import os
import pathlib
import stat
import tempfile
import types
import unittest
from datetime import datetime, timezone, timedelta
from test_morpheus import agent, checks, FIXTURE, State


class VMCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = agent.VMStatsCache(pathlib.Path(self.temp.name) / 'private')
        self.api = types.SimpleNamespace(vm_stats_cache=self.cache)
        self.vm = copy.deepcopy(FIXTURE['vms'][0])
        self.vm['stats']['ts'] = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
        self.vm['stats_source'] = 'list'

    def prime(self):
        agent.retain_vm_stats(self.api, [self.vm])

    def incomplete(self):
        vm = copy.deepcopy(self.vm)
        vm['stats'] = {'ts': datetime.now(timezone.utc).isoformat(), 'maxMemory': vm['maxMemory']}
        return vm

    def test_three_sample_regression_complete_incomplete_complete(self):
        self.prime()
        partial = self.incomplete()
        agent.retain_vm_stats(self.api, [partial])
        self.assertEqual(partial['stats_source'], 'cache')
        self.assertEqual(partial['stats'], self.vm['stats'])
        self.assertEqual(self.cache.read(self.vm['id'])['stats']['ts'], self.vm['stats']['ts'])
        for item in ('CPU', 'Memory', 'Storage'):
            rows = list(checks.check_vm_metrics(item, {}, partial))
            self.assertFalse(any(getattr(r, 'state', None) == State.UNKNOWN for r in rows))
            self.assertTrue(any('last complete snapshot' in getattr(r, 'summary', '') for r in rows))
        latest = copy.deepcopy(self.vm)
        latest['stats']['ts'] = datetime.now(timezone.utc).isoformat()
        latest['stats']['cpuUsage'] = 0.03336072
        agent.retain_vm_stats(self.api, [latest])
        self.assertEqual(latest['stats_source'], 'list')
        self.assertEqual(self.cache.read(latest['id'])['stats'], latest['stats'])

    def test_cached_snapshot_warning_and_critical_use_original_time(self):
        for seconds, state in ((180, State.WARN), (1000, State.CRIT)):
            self.cache.path(self.vm['id']).unlink(missing_ok=True)
            self.vm['stats']['ts'] = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
            self.prime()
            partial = self.incomplete()
            agent.retain_vm_stats(self.api, [partial])
            rows = list(checks.check_vm_metrics('CPU', {}, partial))
            self.assertTrue(any(getattr(r, 'state', None) == state for r in rows))
            if state == State.CRIT:
                self.assertFalse(any(r.args and r.args[0] == 'morpheus_vm_cpu_percent' for r in rows))

    def test_no_baseline_remains_unknown(self):
        partial = self.incomplete()
        agent.retain_vm_stats(self.api, [partial])
        self.assertNotEqual(partial['stats_source'], 'cache')
        self.assertTrue(any(getattr(r, 'state', None) == State.UNKNOWN for r in checks.check_vm_metrics('CPU', {}, partial)))

    def test_capacity_change_rejects_old_snapshot(self):
        self.prime()
        for key in agent.VM_CAPACITY_FIELDS:
            partial = self.incomplete()
            partial[key] = (partial.get(key) or 1) * 2
            agent.retain_vm_stats(self.api, [partial])
            self.assertNotEqual(partial['stats_source'], 'cache')

    def test_power_off_clears_baseline(self):
        self.prime()
        stopped = copy.deepcopy(self.vm)
        stopped['powerState'] = 'off'
        agent.retain_vm_stats(self.api, [stopped])
        self.assertIsNone(self.cache.read(self.vm['id']))

    def test_cache_is_private_and_whitelisted(self):
        self.vm['sshPassword'] = 'SECRET'
        self.vm['stats']['secret'] = 'SECRET'
        self.prime()
        path = self.cache.path(self.vm['id'])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertNotIn('SECRET', path.read_text())

    def test_corrupt_or_invalid_cache_is_ignored(self):
        self.prime()
        path = self.cache.path(self.vm['id'])
        path.write_text('{broken')
        self.assertIsNone(self.cache.read(self.vm['id']))
        self.prime()
        data = self.cache.read(self.vm['id'])
        data['stats']['cpuUsage'] = None
        path.write_text(json.dumps(data))
        self.assertIsNone(self.cache.read(self.vm['id']))

    def test_invalid_timestamp_does_not_overwrite_baseline(self):
        self.prime()
        for timestamp in (None, 'invalid', '2026-10-29T10:00:00', (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()):
            bad = copy.deepcopy(self.vm)
            bad['stats']['ts'] = timestamp
            agent.retain_vm_stats(self.api, [bad])
            self.assertEqual(bad['stats_source'], 'cache')
            self.assertEqual(bad['stats']['ts'], self.vm['stats']['ts'])

    def test_delayed_complete_response_does_not_replace_newer_cache(self):
        self.prime()
        old = copy.deepcopy(self.vm)
        old['stats']['ts'] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        agent.retain_vm_stats(self.api, [old])
        self.assertEqual(self.cache.read(self.vm['id'])['stats']['ts'], self.vm['stats']['ts'])

    def test_no_site_disables_cache(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            api = agent.API('https://example.invalid', 'token')
        self.assertIsNone(api.vm_stats_cache)
        agent.retain_vm_stats(api, [self.incomplete()])

    def test_api_and_credential_identity_separate_caches(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'OMD_ROOT': self.temp.name}):
            a = agent.API('https://example.invalid', 'token-a')
            b = agent.API('https://example.invalid', 'token-b')
            c = agent.API('https://other.invalid', 'token-a')
        self.assertEqual(len({a.vm_stats_cache.directory, b.vm_stats_cache.directory, c.vm_stats_cache.directory}), 3)

    def test_independent_vm_ids_do_not_share_readings(self):
        self.prime()
        partial = self.incomplete()
        partial['id'] = 9999
        agent.retain_vm_stats(self.api, [partial])
        self.assertNotEqual(partial['stats_source'], 'cache')
