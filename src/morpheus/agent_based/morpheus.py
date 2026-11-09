# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import json
import math
from datetime import datetime, timezone
from cmk.agent_based.v2 import AgentSection, CheckPlugin, Service, Result, State, Metric


def parse(string_table):
    return json.loads(''.join(row[0] for row in string_table if row))

agent_section_morpheus_api = AgentSection(name='morpheus_api', parse_function=parse)
agent_section_morpheus_platform = AgentSection(name='morpheus_platform', parse_function=parse)
agent_section_morpheus_clouds = AgentSection(name='morpheus_clouds', parse_function=parse)
agent_section_morpheus_vm = AgentSection(name='morpheus_vm', parse_function=parse)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def age(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return None
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except ValueError:
        return None


def freshness(value, warn, crit):
    elapsed = age(value)
    if elapsed is None:
        yield Result(state=State.UNKNOWN, summary='Missing/invalid data timestamp')
    elif elapsed < -300:
        yield Result(state=State.UNKNOWN, summary='Data timestamp is in the future; check clocks')
    else:
        state = State.CRIT if elapsed >= crit else State.WARN if elapsed >= warn else State.OK
        yield Result(state=state, summary=f'Data age: {max(0, elapsed):.0f} s')
        yield Metric('morpheus_data_age', max(0, elapsed), levels=(warn, crit))


def status_result(obj, good):
    status = str(obj.get('status') or 'unknown').lower()
    if obj.get('success') is False:
        state = State.CRIT
    elif status in good:
        state = State.OK
    elif status in ('warning', 'warn', 'degraded', 'yellow'):
        state = State.WARN
    elif status in ('error', 'failed', 'critical', 'offline', 'red'):
        state = State.CRIT
    else:
        state = State.UNKNOWN
    msg = str(obj.get('statusMessage') or '').replace('\n', ' ')[:300]
    yield Result(state=state, summary=status + (': ' + msg if msg else ''))


def percent(value, name, label, warn=90.0, crit=95.0, upper=100):
    if not number(value) or value < 0 or (upper is not None and value > upper):
        yield Result(state=State.UNKNOWN, summary=label + ': missing/out-of-range value')
        return
    state = State.CRIT if value >= crit else State.WARN if value >= warn else State.OK
    yield Result(state=state, summary=f'{label}: {value:.2f}%')
    yield Metric(name, value, levels=(warn, crit), boundaries=(0, upper))


def discover_single(section):
    yield Service()


def check_api(section):
    if section.get('success') is not True:
        yield Result(state=State.CRIT, summary=section.get('message') or 'API collection failed')
        return
    yield Result(state=State.OK, summary=f"Collected {section['vm_count']} VMs, {section['cloud_count']} clouds")
    yield Metric('morpheus_api_duration', section['duration'])
    yield Metric('morpheus_vm_count', section['vm_count'])

check_plugin_morpheus_api = CheckPlugin(name='morpheus_api', service_name='Morpheus API',
    discovery_function=discover_single, check_function=check_api)


COMPONENTS = ('cpu', 'memory', 'threads', 'database', 'storage', 'elastic', 'rabbit')


def discover_platform(section):
    yield Service(item='Application')
    for key in COMPONENTS:
        if isinstance(section.get(key), dict):
            yield Service(item=key)


def check_platform(item, params, section):
    if item == 'Application':
        state = State.OK if section.get('success') is True and section.get('setupNeeded') is False else State.CRIT
        yield Result(state=state, summary=f"Version {section.get('buildVersion', 'unknown')}; success={section.get('success')}; setupNeeded={section.get('setupNeeded')}")
        yield from freshness(section.get('date'), params.get('age_warn', 900), params.get('age_crit', 1800))
        return
    component = section.get(item)
    if component is None:
        yield Result(state=State.UNKNOWN, summary='Component missing from API response')
        return
    yield from status_result(component, {'ok', 'healthy', 'green'})
    warn, crit = params.get('warn', 90.0), params.get('crit', 95.0)
    if item == 'cpu':
        yield from percent(component.get('cpuLoad'), 'morpheus_process_cpu', 'Morpheus CPU', warn, crit)
        yield from percent(component.get('cpuTotalLoad'), 'morpheus_system_cpu', 'System CPU', warn, crit)
    elif item == 'memory':
        value = component.get('memoryPercent')
        yield from percent(value * 100 if number(value) else None, 'morpheus_jvm_percent', 'JVM heap', warn, crit)
        for key, metric in [('usedMemory', 'morpheus_jvm_used_mib'), ('maxMemory', 'morpheus_jvm_max_mib'), ('systemAvailableMemory', 'morpheus_system_available_mib')]:
            if number(component.get(key)):
                yield Metric(metric, component[key] / 1048576)
    elif item == 'database':
        used, maximum = component.get('usedConnections'), component.get('maxConnections')
        if number(used) and number(maximum) and maximum > 0:
            yield from percent(100 * used / maximum, 'morpheus_db_connections_percent', 'DB connections', warn, crit)
            yield Metric('morpheus_db_connections', used)
    elif item == 'storage':
        yield from percent(component.get('percent'), 'morpheus_appliance_storage_percent', 'Appliance storage', warn, crit)
    elif item == 'threads' and number(component.get('totalThreads')):
        yield Metric('morpheus_threads', component['totalThreads'])
    elif item == 'rabbit':
        for key in ('busyQueuesCount', 'errorQueuesCount'):
            if number(component.get(key)):
                count = component[key]
                yield Result(state=State.WARN if count > 0 else State.OK, summary=f'{key}: {count}')
                yield Metric('morpheus_' + key.lower(), count)

check_plugin_morpheus_platform = CheckPlugin(name='morpheus_platform', service_name='Morpheus %s',
    discovery_function=discover_platform, check_function=check_platform,
    check_ruleset_name='morpheus_platform', check_default_parameters={'warn': 90.0, 'crit': 95.0, 'age_warn': 900, 'age_crit': 1800})


def discover_clouds(section):
    for cloud in section:
        yield Service(item=str(cloud.get('service_item') or cloud.get('name') or ('ID ' + str(cloud['id']))))


def check_clouds(item, params, section):
    cloud = next((c for c in section if str(c.get('service_item') or c.get('name') or ('ID ' + str(c['id']))) == item), None)
    if cloud is None:
        yield Result(state=State.UNKNOWN, summary='Cloud no longer in returned inventory')
        return
    yield Result(state=State.OK, summary=str(cloud.get('name', item)))
    yield Result(state=State.OK, notice='Morpheus cloud ID: ' + str(cloud['id']))
    if cloud.get('enabled') is False:
        yield Result(state=State.OK, summary='Cloud disabled; synchronization age not checked')
        return
    yield from status_result(cloud, {'ok', 'healthy'})
    yield from freshness(cloud.get('lastSync'), params.get('age_warn', 900), params.get('age_crit', 1800))

check_plugin_morpheus_clouds = CheckPlugin(name='morpheus_clouds', service_name='Morpheus Cloud %s',
    discovery_function=discover_clouds, check_function=check_clouds,
    check_ruleset_name='morpheus_clouds', check_default_parameters={'age_warn': 900, 'age_crit': 1800})


def check_vm(params, section):
    yield Result(state=State.OK, summary=f"{section.get('name')} (ID {section['id']}), cloud: {section.get('zone', {}).get('name')}, hypervisor: {section.get('parentServer', {}).get('name')}")
    yield from status_result(section, {'provisioned', 'running', 'stopped', 'off', 'on', 'suspended'})
    power = str(section.get('powerState') or 'unknown').lower()
    expected = params.get('expected_power', 'any')
    if power not in ('on', 'off', 'suspended', 'paused'):
        yield Result(state=State.UNKNOWN, summary='Power: ' + power)
    else:
        yield Result(state=State.CRIT if expected != 'any' and power != expected else State.OK, summary='Power: ' + power)
    guest = section.get('guestAgentStatus', 'unknown')
    yield Result(state=State.WARN if params.get('expect_guest_agent', False) and power == 'on' and guest != 'connected' else State.OK,
                 summary='Morpheus guest agent: ' + str(guest))
    if section.get('maintenanceMode'):
        yield Result(state=State.OK, summary='Morpheus maintenance mode enabled')

check_plugin_morpheus_vm = CheckPlugin(name='morpheus_vm', service_name='Morpheus VM',
    discovery_function=discover_single, check_function=check_vm,
    check_ruleset_name='morpheus_vm', check_default_parameters={'expected_power': 'any', 'expect_guest_agent': False})


def discover_vm_metrics(section):
    stats = section.get('stats', {})
    if stats:
        for item in ('CPU', 'Memory', 'Storage'):
            yield Service(item=item)


def check_vm_metrics(item, params, section):
    if section.get('powerState') != 'on':
        yield Result(state=State.OK, summary='VM not powered on; metrics not evaluated')
        return
    stats = section.get('stats', {})
    elapsed = age(stats.get('ts'))
    if section.get('stats_source') == 'detail':
        yield Result(state=State.OK, summary='Statistics source: VM detail endpoint')
    elif section.get('stats_source') == 'cache':
        yield Result(state=State.OK, summary='Statistics source: last complete snapshot (current API metrics incomplete)')
    age_warn, age_crit = params.get('age_warn', 900), params.get('age_crit', 1800)
    if section.get('stats_source') == 'cache':
        age_warn = min(age_warn, params.get('cache_age_warn', 120))
        age_crit = min(age_crit, params.get('cache_age_crit', 900))
    yield from freshness(stats.get('ts'), age_warn, age_crit)
    if elapsed is None or elapsed >= age_crit or elapsed < -300:
        return
    warn, crit = params.get('warn', 90.0), params.get('crit', 95.0)
    if item == 'CPU':
        # Preserve provider-reported CPU; some sources aggregate across cores.
        # Do not silently divide only values above 100 or clamp the reading.
        yield from percent(stats.get('cpuUsage'), 'morpheus_vm_cpu_percent', 'CPU reported by API', warn, crit, upper=None)
        if number(stats.get('cpuUsage')) and stats['cpuUsage'] > 100:
            yield Result(state=State.OK, summary='API CPU scale exceeds 100%; value is not normalized by vCPU count')
    else:
        suffix = 'Memory' if item == 'Memory' else 'Storage'
        used, total = stats.get('used' + suffix), stats.get('max' + suffix)
        if not number(used) or not number(total) or used < 0 or total <= 0:
            detail = section.get('stats_detail_status')
            yield Result(state=State.UNKNOWN, summary='No valid usage/capacity data' + ('; ' + detail if detail else ''))
            return
        # API storage semantics depend on provider: expose absolute values only.
        yield Metric('morpheus_vm_' + suffix.lower() + '_used_mib', used / 1048576)
        yield Metric('morpheus_vm_' + suffix.lower() + '_max_mib', total / 1048576)
        if item == 'Memory':
            yield from percent(100 * used / total, 'morpheus_vm_memory_percent', 'Memory reported by API', warn, crit)
        else:
            yield Result(state=State.OK, summary=f'API storage: {used / 1073741824:.2f} GiB used, {total / 1073741824:.2f} GiB capacity (not individual guest filesystems)')

check_plugin_morpheus_vm_metrics = CheckPlugin(name='morpheus_vm_metrics', service_name='Morpheus VM %s',
    sections=['morpheus_vm'], discovery_function=discover_vm_metrics, check_function=check_vm_metrics,
    check_ruleset_name='morpheus_vm_metrics', check_default_parameters={'warn': 90.0, 'crit': 95.0, 'age_warn': 900, 'age_crit': 1800, 'cache_age_warn': 120, 'cache_age_crit': 900})
