# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Run using Checkmk 2.4's Python and installed public APIs (no service changes)."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from cmk.agent_based.v2 import Metric, Result, Service

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

m = load('checks', ROOT / 'src/morpheus/agent_based/morpheus.py')
f = json.loads((ROOT / 'tests/sample_normalized.json').read_text())
f['health']['date'] = datetime.now(timezone.utc).isoformat()
f['vms'][0]['stats']['ts'] = datetime.now(timezone.utc).isoformat()
count = 0
for service in m.discover_platform(f['health']):
    assert isinstance(service, Service)
    rows = list(m.check_platform(service.item, {}, f['health']))
    assert rows and all(isinstance(r, (Metric, Result)) for r in rows)
    count += 1
for service in m.discover_clouds(f['clouds']):
    assert list(m.check_clouds(service.item, {}, f['clouds']))
    count += 1
assert list(m.check_vm({}, f['vms'][0]))
count += 1
for service in m.discover_vm_metrics(f['vms'][0]):
    assert list(m.check_vm_metrics(service.item, {}, f['vms'][0]))
    count += 1
assert list(m.check_api({'success': True, 'vm_count': 1, 'cloud_count': 1, 'duration': 1.0}))
count += 1
print(f'Public agent API: {count} sample services evaluated successfully')
f['vms'][0]['stats']['cpuUsage'] = 108.37176753233156
rows = list(m.check_vm_metrics('CPU', {}, f['vms'][0]))
assert any(isinstance(r, Metric) and r.name == 'morpheus_vm_cpu_percent' and r.value == 108.37176753233156 for r in rows)
print('Public agent API: CPU above 100% accepted without clipping or normalization')
for path in sorted((ROOT / 'src/morpheus/rulesets').glob('*.py')):
    module = load('rules_' + path.stem, path)
    for name, rule in vars(module).items():
        if name.startswith('rule_spec_'):
            rule.parameter_form()
            print('Public rules API:', name, 'form constructed')
module = load('server_calls', ROOT / 'src/morpheus/server_side_calls/special_agent.py')
print('Public server-side calls API: configuration loaded')

# Infrastructure checks use the same runtime classes and current timestamps.
infra = load('infrastructure', ROOT / 'src/morpheus/agent_based/infrastructure.py')
data = json.loads((ROOT / 'tests/sample_infrastructure.json').read_text())
now = datetime.now(timezone.utc).isoformat()
for ds in data['datastores']: ds['sync_timestamp'] = now
for hv in data['hypervisors']: hv['stats']['ts'] = now
for c in data['clusters']: c['lastSync'] = now
count_infra = 0
count_summary = 0
for name, plugin in vars(infra).items():
    if not name.startswith('check_plugin_'): continue
    for service in plugin.discovery_function(data):
        kwargs = {'section': data}
        if service.item is not None: kwargs['item'] = service.item
        if plugin.check_default_parameters is not None: kwargs['params'] = plugin.check_default_parameters
        rows = list(plugin.check_function(**kwargs))
        assert rows and all(isinstance(r, (Metric, Result)) for r in rows), (name, service.item)
        count_infra += 1
        if name != 'check_plugin_morpheus_sensor': count_summary += 1
print(f'Infrastructure API: {count_infra} sample services evaluated, including {count_summary} without detailed sensors')
graphing = load('graphing', ROOT / 'src/morpheus/graphing/infrastructure.py')
print('Public graphing API: metrics and graphs constructed')

# Every primary metric gets a template; age remains an automatic auxiliary graph.
from cmk.graphing.v1.metrics import Constant, Product, Fraction, WarningOf, CriticalOf
def references(value):
    if isinstance(value, str): return {value}
    if isinstance(value, Constant): return set()
    if isinstance(value, Product): return set().union(*(references(x) for x in value.factors))
    if isinstance(value, Fraction): return references(value.dividend) | references(value.divisor)
    if isinstance(value, (WarningOf, CriticalOf)): return references(value.metric_name)
    raise AssertionError(type(value))

defined_metrics = {v.name: v for k,v in vars(graphing).items() if k.startswith('metric_')}
defined_graphs = {v.name: v for k,v in vars(graphing).items() if k.startswith('graph_')}
defined_perfometers = {v.name: v for k,v in vars(graphing).items() if k.startswith('perfometer_')}
graphed = set()
for graph in defined_graphs.values():
    used = set().union(*(references(x) for x in (*graph.compound_lines, *graph.simple_lines)))
    assert used <= defined_metrics.keys(), (graph.name, used - defined_metrics.keys())
    assert 'morpheus_data_age' not in used, graph.name
    graphed |= used
assert set(defined_metrics) - {'morpheus_data_age'} <= graphed
for meter in defined_perfometers.values():
    assert set().union(*(references(x) for x in meter.segments)) <= defined_metrics.keys()
assert 'morpheus_vm_cpu_percent' in defined_perfometers
assert 'morpheus_vm_memory_percent' in defined_perfometers
assert 'morpheus_vm_storage' in defined_perfometers
assert defined_metrics['morpheus_vm_cpu_percent'].unit.notation.symbol == '%'
assert defined_metrics['morpheus_data_age'].unit.notation.symbol == 's'
storage = defined_graphs['morpheus_vm_storage']
assert storage.compound_lines[0].factors[1].value == 1048576
assert storage.compound_lines[0].unit.notation.symbol == 'B'
print(f'Graphing coverage: {len(defined_metrics)} named metrics, {len(defined_graphs)} primary graphs, {len(defined_perfometers)} perfometers; age auxiliary; MiB-to-byte conversion checked')
# Cross-check plugin check defaults against the matching form fields.
forms = load('all_forms', ROOT / 'src/morpheus/rulesets/check_parameters.py')
by_name = {v.name: v for n,v in vars(forms).items() if n.startswith('rule_spec_')}
for module in (m, infra):
    for name, plugin in vars(module).items():
        if name.startswith('check_plugin_') and plugin.check_ruleset_name:
            keys = set(by_name[plugin.check_ruleset_name].parameter_form().elements)
            assert set(plugin.check_default_parameters).issubset(keys), name
print('Check default parameter keys match all rule forms')
