# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Infrastructure checks on the Morpheus API source host; VM piggyback unchanged."""
import json
import math
import re
from datetime import datetime, timezone
from cmk.agent_based.v2 import AgentSection, CheckPlugin, Service, Result, State, Metric


def parse(string_table):
    return json.loads(''.join(row[0] for row in string_table if row))

agent_section_morpheus_infrastructure = AgentSection(name='morpheus_infrastructure', parse_function=parse)


def num(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)


def item_name(o):
    return str(o.get('service_item') or o.get('name') or ('ID ' + str(o['id'])))


def object_identity(o):
    return Result(state=State.OK, notice='Morpheus object ID: ' + str(o['id']) + '; cloud ID: ' + str(o.get('zone', {}).get('id', 'not applicable')))


def find(section, key, item):
    return next((o for o in section.get(key, []) if item_name(o) == item), None)


def state(status):
    status = str(status or 'unknown').lower()
    if status in ('ok', 'healthy', 'online', 'provisioned', 'available', 'running', 'green'):
        return State.OK
    if status in ('warning', 'warn', 'degraded', 'yellow', 'nc', 'maintenance'):
        return State.WARN
    if status in ('error', 'failed', 'offline', 'critical', 'red', 'cr', 'nr', 'down'):
        return State.CRIT
    return State.UNKNOWN


def age(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None: return None
        return (datetime.now(timezone.utc) - stamp).total_seconds()
    except (ValueError, TypeError, AttributeError): return None


def age_results(timestamp, params):
    elapsed = age(timestamp)
    if elapsed is None or elapsed < -300:
        yield Result(state=State.UNKNOWN, summary='Missing/invalid/future source timestamp')
        return
    warn, crit = params.get('age_warn', 900), params.get('age_crit', 1800)
    yield Result(state=State.CRIT if elapsed >= crit else State.WARN if elapsed >= warn else State.OK,
                 summary=f'Source data age: {max(0, elapsed):.0f} s')
    yield Metric('morpheus_data_age', max(0, elapsed), levels=(warn, crit))


def fresh(timestamp, params):
    elapsed = age(timestamp)
    return elapsed is not None and -300 <= elapsed < params.get('age_crit', 1800)


def usage(value, metric, label, params, default_warn=90, default_crit=95):
    if not num(value) or not 0 <= value <= 100:
        yield Result(state=State.UNKNOWN, summary=label + ': missing or invalid value')
        return
    warn, crit = params.get('warn', default_warn), params.get('crit', default_crit)
    yield Result(state=State.CRIT if value >= crit else State.WARN if value >= warn else State.OK,
                 summary=f'{label}: {value:.2f}%')
    yield Metric(metric, value, levels=(warn, crit), boundaries=(0, 100))


def discover_collection(section):
    yield Service()


def check_collection(section):
    errors = section.get('errors', [])
    yield Result(state=State.CRIT if errors else State.OK,
        summary=f"{len(section.get('datastores', []))} datastores, {len(section.get('hypervisors', []))} hypervisors, {len(section.get('clusters', []))} clusters" + ('; ' + '; '.join(errors) if errors else ''))

check_plugin_morpheus_infra_collection = CheckPlugin(name='morpheus_infra_collection',
    sections=['morpheus_infrastructure'], service_name='Morpheus Infrastructure collection',
    discovery_function=discover_collection, check_function=check_collection)


def discover_datastores(section):
    for ds in section.get('datastores', []): yield Service(item=item_name(ds))


def check_datastore_state(item, section):
    ds = find(section, 'datastores', item)
    if ds is None:
        yield Result(state=State.UNKNOWN, summary='Datastore absent from current inventory'); return
    yield object_identity(ds)
    yield Result(state=State.OK, summary='Cloud: ' + str(ds.get('zone', {}).get('name')))
    if 'online' in ds:
        yield Result(state=State.OK if ds['online'] is True else State.CRIT, summary='Online: ' + str(ds['online']))
    else:
        yield Result(state=State.UNKNOWN, summary='Online state not reported')
    if ds.get('active') is False: yield Result(state=State.WARN, summary='Datastore inactive')
    if ds.get('status') is not None:
        yield Result(state=state(ds['status']), summary='Status: ' + str(ds['status']))
    maintenance = ds.get('maintenanceStatus')
    if maintenance is not None:
        yield Result(state=State.OK if maintenance == 'available' else State.WARN, summary='Maintenance: ' + str(maintenance))
    if ds.get('statusMessage'):
        yield Result(state=State.OK, summary=str(ds['statusMessage']).replace('\n', ' ')[:300])
    for loc in ds.get('locations', []):
        yield Result(state=state(loc.get('status')), summary=f"Location {loc.get('refId')}: {loc.get('status')}")


def check_datastore_usage(item, params, section):
    ds = find(section, 'datastores', item)
    if ds is None:
        yield Result(state=State.UNKNOWN, summary='Datastore absent from current inventory'); return
    yield object_identity(ds)
    if ds.get('online') is False:
        yield Result(state=State.UNKNOWN, summary='Datastore offline; capacity not evaluated'); return
    yield from age_results(ds.get('sync_timestamp'), params)
    if not fresh(ds.get('sync_timestamp'), params): return
    total, free = ds.get('storageSize'), ds.get('freeSpace')
    if not num(total) or total <= 0 or not num(free) or free < 0 or free > total:
        yield Result(state=State.UNKNOWN, summary='Missing or inconsistent capacity/free space; no fabricated usage percentage')
        if num(free) and free >= 0: yield Metric('morpheus_datastore_free_bytes', free)
        return
    used = total - free
    yield from usage(100 * used / total, 'morpheus_datastore_used_percent', 'Used', params, 80, 90)
    yield Result(state=State.OK, summary=f'Used {used / 2**30:.2f} GiB, free {free / 2**30:.2f} GiB, total {total / 2**30:.2f} GiB; capacity source: {ds.get("capacity_source")}')
    for metric, value in [('used', used), ('free', free), ('size', total)]:
        yield Metric('morpheus_datastore_' + metric + '_bytes', value)


def discover_multipath(section):
    for ds in section.get('datastores', []):
        if ds.get('multipath'): yield Service(item=item_name(ds))


def check_multipath(item, params, section):
    ds = find(section, 'datastores', item)
    if ds is None:
        yield Result(state=State.UNKNOWN, summary='Datastore absent from inventory'); return
    yield object_identity(ds)
    yield from age_results(ds.get('sync_timestamp'), params)
    if not fresh(ds.get('sync_timestamp'), params): return
    p = ds.get('multipath', {})
    paths, active, failed = p.get('multipathPaths'), p.get('multipathActive'), p.get('multipathFailed')
    if not all(num(v) and v >= 0 for v in (paths, active, failed)) or active > paths or failed > paths:
        yield Result(state=State.UNKNOWN, summary='Missing/inconsistent multipath counters'); return
    minimum = params.get('min_paths', 2)
    s = State.CRIT if active == 0 else State.WARN if failed > 0 or active < paths or active < minimum else State.OK
    yield Result(state=s, summary=f'Active {active}/{paths}, failed {failed}; minimum active {minimum}; state: {p.get("multipathState", "unknown")}')
    if str(p.get('multipathState')).lower() in ('failed', 'offline', 'error'):
        yield Result(state=State.CRIT, summary='Multipath state indicates failure')
    for metric, value in [('active', active), ('failed', failed), ('paths', paths)]:
        yield Metric('morpheus_multipath_' + metric, value)


def discover_hypervisors(section):
    for h in section.get('hypervisors', []): yield Service(item=item_name(h))


def check_hypervisor_state(item, section):
    h = find(section, 'hypervisors', item)
    if h is None:
        yield Result(state=State.UNKNOWN, summary='Hypervisor absent from current inventory'); return
    yield object_identity(h)
    yield Result(state=state(h.get('status')), summary='Status: ' + str(h.get('status')))
    power = h.get('powerState')
    yield Result(state=State.OK if power == 'on' else State.CRIT if power == 'off' else State.UNKNOWN, summary='Power: ' + str(power))
    yield Result(state=State.WARN if h.get('maintenanceMode') else State.OK, summary='Maintenance: ' + str(h.get('maintenanceMode')))
    if h.get('serverGroupMemberStatus') is not None:
        yield Result(state=state(h['serverGroupMemberStatus']), summary='Membership: ' + str(h['serverGroupMemberStatus']))
    yield Result(state=State.OK, summary=f"Cloud: {h.get('zone', {}).get('name')}; {h.get('maxCores')} cores; {h.get('platform')} {h.get('platformVersion')}")


def check_hypervisor_cpu(item, params, section):
    yield from hypervisor_metric(item, params, section, 'CPU')


def check_hypervisor_memory(item, params, section):
    yield from hypervisor_metric(item, params, section, 'Memory')


def hypervisor_metric(item, params, section, kind):
    h = find(section, 'hypervisors', item)
    if h is None:
        yield Result(state=State.UNKNOWN, summary='Hypervisor absent from current inventory'); return
    yield object_identity(h)
    stats = h.get('stats', {})
    yield from age_results(stats.get('ts'), params)
    if not fresh(stats.get('ts'), params): return
    if kind == 'CPU':
        yield from usage(stats.get('cpuUsage'), 'morpheus_hypervisor_cpu', 'CPU', params)
    else:
        used, total = stats.get('usedMemory'), stats.get('maxMemory')
        if not num(used) or not num(total) or used < 0 or total <= 0:
            yield Result(state=State.UNKNOWN, summary='Missing/invalid memory data'); return
        yield from usage(100 * used / total, 'morpheus_hypervisor_memory', 'Memory', params)
        yield Metric('morpheus_hypervisor_memory_used_bytes', used)
        yield Metric('morpheus_hypervisor_memory_size_bytes', total)


def discover_hardware(section):
    for h in section.get('hypervisors', []):
        if h.get('hardware_summary', {}).get('count', 0): yield Service(item=item_name(h))


def check_hardware(item, params, section):
    h = find(section, 'hypervisors', item)
    if h is None:
        yield Result(state=State.UNKNOWN, summary='Hypervisor absent from current inventory'); return
    yield object_identity(h)
    timestamp = h.get('hardware_timestamp') or h.get('stats', {}).get('ts')
    source = h.get('hardware_source', 'list')
    yield Result(state=State.OK, summary='Hardware source: ' + ('last valid snapshot (current API omitted sensors)' if source == 'cache' else source))
    yield from age_results(timestamp, params)
    if not fresh(timestamp, params): return
    hw = h.get('hardware_summary', {})
    if not hw.get('count'):
        yield Result(state=State.UNKNOWN, summary='Hardware sensors no longer reported'); return
    problems = hw.get('problems', [])
    yield Result(state=State.OK, summary=f"{hw.get('count')} sensors, {hw.get('unavailable')} not available, {len(problems)} non-OK")
    for sensor in problems:
        yield Result(state=state(sensor.get('status')), summary=f"{sensor.get('name')}: {sensor.get('status')} {sensor.get('reading', '')}"[:300])
    yield Metric('morpheus_hardware_problems', len(problems))


def discover_sensors(section):
    for h in section.get('hypervisors', []):
        for sensor in h.get('sensors', []):
            yield Service(item=item_name(h) + ' / ' + str(sensor.get('name')))


def check_sensor(item, params, section):
    for h in section.get('hypervisors', []):
        for sensor in h.get('sensors', []):
            if item_name(h) + ' / ' + str(sensor.get('name')) != item: continue
            yield object_identity(h)
            timestamp = h.get('hardware_timestamp') or h.get('stats', {}).get('ts')
            if h.get('hardware_source') == 'cache':
                yield Result(state=State.OK, summary='Last valid snapshot; current API omitted sensors')
            yield from age_results(timestamp, params)
            if not fresh(timestamp, params): return
            reading = str(sensor.get('reading', ''))
            yield Result(state=state(sensor.get('status')), summary=str(sensor.get('status')) + ': ' + reading)
            match = re.fullmatch(r'(-?\d+(?:\.\d+)?)\s+(degrees C|RPM|Watts|Volts|percent)', reading)
            if match:
                metric = {'degrees C': 'temperature', 'RPM': 'rpm', 'Watts': 'watts', 'Volts': 'volts', 'percent': 'percent'}[match[2]]
                yield Metric('morpheus_sensor_' + metric, float(match[1]))
            return
    yield Result(state=State.UNKNOWN, summary='Sensor absent from current response')


def discover_clusters(section):
    for c in section.get('clusters', []): yield Service(item=item_name(c))


def check_cluster(item, params, section):
    c = find(section, 'clusters', item)
    if c is None:
        yield Result(state=State.UNKNOWN, summary='Cluster absent from current inventory'); return
    yield object_identity(c)
    cluster_status = str(c.get('status') or 'unknown').lower()
    # A normal inventory refresh must not flap the cluster service. The
    # existing lastSync age and member checks remain independent safeguards.
    yield Result(state=State.OK if cluster_status == 'syncing' else state(cluster_status),
                 summary='Status: ' + cluster_status)
    yield from age_results(c.get('lastSync'), params)
    yield Result(state=State.OK, summary=f"{len(c.get('members', []))} members; HA enabled: {c.get('ha_enabled', 'not reported')}")
    for member in c.get('members', []):
        yield Result(state=state(member.get('serverGroupMemberStatus')), summary=f"{member.get('name')}: {member.get('serverGroupMemberStatus')}")
    if params.get('expect_ha') and c.get('ha_enabled') is not True:
        yield Result(state=State.CRIT, summary='HA expected but not enabled/reported')


def check_cluster_cpu(item, params, section):
    yield from cluster_metric(item, params, section, 'CPU')


def check_cluster_memory(item, params, section):
    yield from cluster_metric(item, params, section, 'Memory')


def cluster_metric(item, params, section, kind):
    c = find(section, 'clusters', item)
    if c is None:
        yield Result(state=State.UNKNOWN, summary='Cluster absent from inventory'); return
    yield object_identity(c)
    yield from age_results(c.get('lastSync'), params)
    if not fresh(c.get('lastSync'), params): return
    stats = c.get('stats', {})
    if kind == 'CPU':
        yield from usage(stats.get('cpuUsageAvg'), 'morpheus_cluster_cpu_avg', 'Worker CPU average', params)
    else:
        used, total = stats.get('usedMemory'), stats.get('maxMemory')
        if not num(used) or not num(total) or used < 0 or total <= 0:
            yield Result(state=State.UNKNOWN, summary='Missing/invalid workerStats memory data'); return
        yield from usage(100 * used / total, 'morpheus_cluster_memory', 'workerStats memory', params)
        yield Metric('morpheus_cluster_memory_used_bytes', used)
        yield Metric('morpheus_cluster_memory_size_bytes', total)
        if num(stats.get('reservedMemory')):
            yield Metric('morpheus_cluster_memory_reserved_bytes', stats['reservedMemory'])


SECTIONS = ['morpheus_infrastructure']
DEFAULTS = {'warn': 90.0, 'crit': 95.0, 'age_warn': 900, 'age_crit': 1800}
check_plugin_morpheus_datastore_state = CheckPlugin(name='morpheus_datastore_state', sections=SECTIONS, service_name='Morpheus Datastore %s State', discovery_function=discover_datastores, check_function=check_datastore_state)
check_plugin_morpheus_datastore_usage = CheckPlugin(name='morpheus_datastore_usage', sections=SECTIONS, service_name='Morpheus Datastore %s Usage', discovery_function=discover_datastores, check_function=check_datastore_usage, check_ruleset_name='morpheus_datastore_usage', check_default_parameters={**DEFAULTS, 'warn': 80.0, 'crit': 90.0})
check_plugin_morpheus_multipath = CheckPlugin(name='morpheus_multipath', sections=SECTIONS, service_name='Morpheus Datastore %s Multipath', discovery_function=discover_multipath, check_function=check_multipath, check_ruleset_name='morpheus_multipath', check_default_parameters={'age_warn': 900, 'age_crit': 1800, 'min_paths': 2})
check_plugin_morpheus_hypervisor_state = CheckPlugin(name='morpheus_hypervisor_state', sections=SECTIONS, service_name='Morpheus Hypervisor %s State', discovery_function=discover_hypervisors, check_function=check_hypervisor_state)
check_plugin_morpheus_hypervisor_cpu = CheckPlugin(name='morpheus_hypervisor_cpu', sections=SECTIONS, service_name='Morpheus Hypervisor %s CPU', discovery_function=discover_hypervisors, check_function=check_hypervisor_cpu, check_ruleset_name='morpheus_infra_metrics', check_default_parameters=DEFAULTS)
check_plugin_morpheus_hypervisor_memory = CheckPlugin(name='morpheus_hypervisor_memory', sections=SECTIONS, service_name='Morpheus Hypervisor %s Memory', discovery_function=discover_hypervisors, check_function=check_hypervisor_memory, check_ruleset_name='morpheus_infra_metrics', check_default_parameters=DEFAULTS)
check_plugin_morpheus_hardware = CheckPlugin(name='morpheus_hardware', sections=SECTIONS, service_name='Morpheus Hardware %s', discovery_function=discover_hardware, check_function=check_hardware, check_ruleset_name='morpheus_hardware', check_default_parameters={'age_warn': 120, 'age_crit': 900})
check_plugin_morpheus_sensor = CheckPlugin(name='morpheus_sensor', sections=SECTIONS, service_name='Morpheus Sensor %s', discovery_function=discover_sensors, check_function=check_sensor, check_ruleset_name='morpheus_hardware', check_default_parameters={'age_warn': 120, 'age_crit': 900})
check_plugin_morpheus_cluster_state = CheckPlugin(name='morpheus_cluster_state', sections=SECTIONS, service_name='Morpheus Cluster %s State', discovery_function=discover_clusters, check_function=check_cluster, check_ruleset_name='morpheus_cluster_state', check_default_parameters={'age_warn': 900, 'age_crit': 1800, 'expect_ha': False})
check_plugin_morpheus_cluster_cpu = CheckPlugin(name='morpheus_cluster_cpu', sections=SECTIONS, service_name='Morpheus Cluster %s CPU', discovery_function=discover_clusters, check_function=check_cluster_cpu, check_ruleset_name='morpheus_infra_metrics', check_default_parameters=DEFAULTS)
check_plugin_morpheus_cluster_memory = CheckPlugin(name='morpheus_cluster_memory', sections=SECTIONS, service_name='Morpheus Cluster %s Memory', discovery_function=discover_clusters, check_function=check_cluster_memory, check_ruleset_name='morpheus_infra_metrics', check_default_parameters=DEFAULTS)
