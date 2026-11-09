# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
"""Opt-in snapshot, volume, license, alarm and virtual-switch checks."""
import json
import math
from datetime import datetime, timezone
from cmk.agent_based.v2 import AgentSection, CheckPlugin, Service, Result, State, Metric


def parse(string_table):
    return json.loads(''.join(row[0] for row in string_table if row))


agent_section_morpheus_extended = AgentSection(name='morpheus_extended', parse_function=parse)
agent_section_morpheus_vm_inventory = AgentSection(name='morpheus_vm_inventory', parse_function=parse)

POWER_LABELS = {'on': 'Powered ON', 'off': 'Powered OFF', 'suspended': 'Suspended', 'paused': 'Paused'}


def vm_power_item(vm):
    return f"{vm.get('name') or 'Unnamed VM'} [ID {vm['id']}]"


def discover_vm_power(section):
    for vm in section['vms']:
        yield Service(item=vm_power_item(vm))


def check_vm_power(item, params, section):
    for vm in section['vms']:
        if vm_power_item(vm) != item:
            continue
        raw = str(vm.get('powerState') or 'unknown')
        power = raw.lower()
        if power not in POWER_LABELS:
            yield Result(state=State.UNKNOWN, summary=f'Unrecognized power state: {raw}', details=inventory_vm_label(vm))
            return
        expected = params.get('expected_power', 'any')
        mismatch = expected != 'any' and expected != power
        summary = POWER_LABELS[power]
        if mismatch:
            summary += f' (expected {POWER_LABELS[expected]})'
        yield Result(state=State.CRIT if mismatch else State.OK, summary=summary, details=inventory_vm_label(vm))
        return
    yield Result(state=State.WARN, summary='VM missing from current Morpheus inventory')


def inventory_scope(section):
    zone_id = section.get('zone_id')
    return f'Cloud ID {zone_id}' if zone_id is not None else 'All API-visible clouds'


def inventory_vm_label(vm):
    name = vm.get('name') or 'Unnamed VM'
    cloud = (vm.get('zone') or {}).get('name') or 'Unknown cloud'
    host = (vm.get('parentServer') or {}).get('name') or 'Unknown host'
    return f"{name} (ID {vm['id']}, {cloud}, {host})"


def check_vm_inventory(section):
    groups = {'Powered ON': [], 'Powered OFF': [], 'Suspended': [], 'Other / unknown': []}
    labels = {'on': 'Powered ON', 'off': 'Powered OFF', 'suspended': 'Suspended'}
    for vm in section['vms']:
        power = str(vm.get('powerState') or 'unknown')
        group = labels.get(power.lower(), 'Other / unknown')
        entry = inventory_vm_label(vm)
        groups[group].append(f'{entry}: {power}' if group == 'Other / unknown' else entry)
    summary = ', '.join(f'{label}: {len(vms)}' for label, vms in groups.items())
    details = '\n'.join(
        f'{label} ({len(vms)})\n' + '\n'.join(sorted(vms, key=str.casefold))
        for label, vms in groups.items() if vms
    )
    yield Result(state=State.OK, summary=f'{inventory_scope(section)}: {summary}', details=details or summary)


def discover_inventory_snapshots(section):
    if section.get('snapshots_enabled'):
        yield Service()


def check_inventory_snapshots(section):
    vms = section['vms']
    total = sum(vm.get('snapshot_count', 0) for vm in vms)
    missing = [vm for vm in vms if 'snapshot_count' not in vm]
    details = '\n'.join(sorted(
        (f"{inventory_vm_label(vm)}: {vm['snapshot_count']} snapshots" for vm in vms if vm.get('snapshot_count')),
        key=str.casefold,
    ))
    if missing:
        summary = f'{inventory_scope(section)}: {total} known snapshots; incomplete coverage ({len(vms) - len(missing)}/{len(vms)} VMs)'
        unavailable = '\n'.join(inventory_vm_label(vm) for vm in missing)
        yield Result(state=State.UNKNOWN, summary=summary, details='\n'.join(filter(None, (details, 'Snapshot data unavailable for:', unavailable))))
        return
    yield Metric('morpheus_snapshot_count', total)
    summary = f'{inventory_scope(section)}: {total} snapshots across {len(vms)} VMs'
    yield Result(state=State.OK, summary=summary, details=details or summary)


def num(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def item_name(obj):
    return str(obj.get('service_item') or obj.get('name') or obj.get('id'))


def elapsed(timestamp):
    try:
        stamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if stamp.tzinfo is None: return None
        return (datetime.now(timezone.utc) - stamp).total_seconds()
    except (AttributeError, ValueError, TypeError):
        return None


def failure(dataset):
    if not isinstance(dataset, dict) or dataset.get('success') is not True:
        return Result(state=State.UNKNOWN, summary='API collection unavailable: ' + str((dataset or {}).get('error', 'dataset missing')))
    return None


def discover_collection(section):
    yield Service()


def check_collection(section):
    errors = section.get('errors', [])
    enabled = ', '.join(k for k,v in section.get('features', {}).items() if v)
    yield Result(state=State.CRIT if errors else State.OK, summary='Enabled: ' + enabled + ('; ' + '; '.join(errors) if errors else '; collection succeeded'))


def discover_snapshots(section):
    if 'snapshots' in section: yield Service()


def check_snapshots(params, section):
    dataset = section.get('snapshots')
    if problem := failure(dataset):
        yield problem; return
    items = dataset['data']
    yield Metric('morpheus_snapshot_count', len(items))
    yield Result(state=State.OK, summary=f'{len(items)} snapshots')
    if not items: return
    ages, invalid_dates = [], []
    has_failure = False
    for snapshot in items:
        status = str(snapshot.get('status') or snapshot.get('state') or 'unknown').lower()
        name = str(snapshot.get('name') or snapshot['id'])
        if status in ('error', 'failed', 'failure'):
            has_failure = True
            yield Result(state=State.CRIT, summary=name + ': ' + status)
        age = elapsed(snapshot.get('snapshotCreated') or snapshot.get('dateCreated'))
        if age is None or age < -300:
            invalid_dates.append(name)
        else:
            ages.append(max(0, age))
    if ages:
        oldest = max(ages)
        warn, crit = params.get('age_warn', 7*86400), params.get('age_crit', 30*86400)
        yield Result(state=State.CRIT if oldest >= crit else State.WARN if oldest >= warn else State.OK,
            summary=f'Oldest known snapshot: {oldest/86400:.2f} days')
        yield Metric('morpheus_snapshot_oldest_age', oldest, levels=(warn, crit))
        has_failure = has_failure or oldest >= crit
    for name in invalid_dates:
        yield Result(state=State.OK if has_failure else State.UNKNOWN, summary='Missing/invalid/future creation time: ' + name)
    sizes = [s.get('maxStorage') for s in items]
    if all(num(v) and v >= 0 for v in sizes):
        yield Metric('morpheus_snapshot_size_bytes', sum(sizes))
    else:
        yield Result(state=State.OK, notice='Snapshot size not reported for every snapshot; no total size fabricated')


def discover_volumes(section):
    for volume in section.get('volumes', []): yield Service(item=item_name(volume))


def check_volume(item, section):
    volume = next((v for v in section.get('volumes', []) if item_name(v) == item), None)
    if volume is None:
        yield Result(state=State.UNKNOWN, summary='Volume absent from current API inventory'); return
    status = str(volume.get('status') or 'unknown').lower()
    state = State.CRIT if volume.get('online') is False or status in ('failed', 'error', 'offline') else State.WARN if status in ('warning', 'degraded') else State.OK if status in ('provisioned', 'available', 'online', 'ok') else State.UNKNOWN
    yield Result(state=state, summary=f'API volume status: {status}; online: {volume.get("online", "not reported")}')
    yield Result(state=State.OK, notice='Morpheus volume ID: ' + str(volume['id']))
    total, used = volume.get('maxStorage'), volume.get('usedStorage')
    if num(total) and total > 0:
        yield Metric('morpheus_volume_capacity_bytes', total)
        summary = f'Capacity: {total/2**30:.2f} GiB'
        if num(used) and used >= 0:
            yield Metric('morpheus_volume_used_bytes', used)
            summary += f', API usedStorage: {used/2**30:.2f} GiB'
        yield Result(state=State.OK, summary=summary + '; guest filesystem usage not verified')
    else:
        yield Result(state=State.UNKNOWN, summary='Volume capacity missing/invalid')
    yield Result(state=State.OK, notice='Volume inventory has no independent measurement timestamp. No guest-fullness thresholds are applied; use guest filesystem checks for C:, D: or mount points.')


def discover_license(section):
    if 'license' in section: yield Service()


def check_license(params, section):
    dataset = section.get('license')
    if problem := failure(dataset):
        yield problem; return
    data = dataset['data']
    licenses = data.get('installed') or [data.get('license', {})]
    remaining, invalid = [], 0
    for license in licenses:
        # A missing end date cannot be interpreted as a perpetual license.
        age = elapsed(license.get('endDate'))
        if age is None:
            invalid += 1; continue
        remaining.append(-age/86400)
    if remaining:
        days = min(remaining)
        warn, crit = params.get('warn_days', 30), params.get('crit_days', 7)
        yield Result(state=State.CRIT if days <= crit else State.WARN if days <= warn else State.OK,
            summary=f'Earliest installed license expiration: {days:.1f} days remaining')
        yield Metric('morpheus_license_days_remaining', days)
    if invalid:
        yield Result(state=State.OK if remaining and min(remaining) <= params.get('crit_days',7) else State.UNKNOWN,
            summary=f'License expiration date not reported/invalid for {invalid} installed licenses')
    yield Result(state=State.OK, notice='License information is appliance/account-wide, regardless of the cloud inventory filter.')


def discover_license_limits(section):
    dataset = section.get('license', {})
    for limit in dataset.get('data', {}).get('limits', []):
        if num(limit.get('max')) and limit['max'] >= 0:
            yield Service(item=str(limit['code']))


def check_license_limit(item, section):
    dataset = section.get('license')
    if problem := failure(dataset):
        yield problem; return
    limit = next((v for v in dataset['data'].get('limits', []) if v.get('code') == item), None)
    if limit is None:
        yield Result(state=State.UNKNOWN, summary='License limit absent or now unlimited; review discovery'); return
    used, maximum = limit.get('used'), limit.get('max')
    if not num(used) or used < 0 or not num(maximum) or maximum < 0:
        yield Result(state=State.UNKNOWN, summary='License limit/usage missing or invalid'); return
    state = State.CRIT if used > maximum else State.WARN if used == maximum or limit.get('warning') or limit.get('limitReached') else State.OK
    yield Result(state=state, summary=f'License usage: {used:g}/{maximum:g}' + ('; capacity fully allocated' if used == maximum else ''))
    yield Metric('morpheus_license_used', used)
    yield Metric('morpheus_license_limit', maximum)
    if maximum > 0: yield Metric('morpheus_license_usage_percent', 100*used/maximum)


def discover_appliance_alarms(section):
    if 'alarms' in section: yield Service()


def check_alarm_dataset(dataset):
    if problem := failure(dataset):
        yield problem; return
    items = [a for a in dataset['data'] if a.get('active') is not False and a.get('acknowledged') is not True and not a.get('endDate')]
    critical, warning, unknown = [], [], []
    for alarm in items:
        status = str(alarm.get('status') or '').lower()
        if status in ('critical', 'error', 'failed', 'fatal'): critical.append(alarm)
        elif status in ('warning', 'warn'): warning.append(alarm)
        elif status not in ('ok', 'healthy', 'info', 'informational', 'normal', 'resolved', 'closed'): unknown.append(alarm)
    state = State.CRIT if critical else State.UNKNOWN if unknown else State.WARN if warning else State.OK
    yield Result(state=state, summary=f'Open unacknowledged alarms: {len(items)}; critical: {len(critical)}, warning: {len(warning)}, unknown severity: {len(unknown)}')
    for alarm in (critical + warning + unknown)[:5]:
        yield Result(state=State.OK, summary=str(alarm.get('name') or alarm['id'])[:200])
    for name, values in (('critical', critical), ('warning', warning), ('unknown', unknown)):
        yield Metric('morpheus_alarms_' + name, len(values))


def check_appliance_alarms(section):
    yield Result(state=State.OK, notice='Appliance/account-wide API alarms; the cloud inventory filter does not limit this summary.')
    yield from check_alarm_dataset(section.get('alarms'))


def check_vm_alarms(section):
    yield from check_alarm_dataset(section.get('alarms'))


def discover_switches(section):
    for switch in section.get('virtual_switches', []): yield Service(item=item_name(switch))


def check_switch(item, section):
    switch = next((v for v in section.get('virtual_switches', []) if item_name(v) == item), None)
    if switch is None:
        yield Result(state=State.UNKNOWN, summary='Virtual switch absent from current API inventory'); return
    status = str(switch.get('status') or 'unknown').lower()
    state = State.OK if status == 'available' else State.WARN if status in ('syncing', 'pending') else State.CRIT if status in ('error', 'failed') else State.UNKNOWN
    yield Result(state=state, summary=f'Status: {status}; bond: {switch.get("bondMode")}; MTU: {switch.get("mtu")}')
    if switch.get('active') is False: yield Result(state=State.WARN, summary='Virtual switch inactive')
    if problem := failure(switch.get('uplinks')): yield problem


def discover_uplinks(section):
    for switch in section.get('virtual_switches', []):
        for uplink in switch.get('uplinks', {}).get('data', []): yield Service(item=item_name(uplink))


def check_uplink(item, section):
    for switch in section.get('virtual_switches', []):
        for uplink in switch.get('uplinks', {}).get('data', []):
            if item_name(uplink) != item: continue
            host = uplink.get('host', {})
            member = str(host.get('serverGroupMemberStatus') or '').lower()
            if host.get('powerState') == 'off' or member in ('unclean', 'offline', 'fenced', 'lost', 'unreachable', 'down'):
                yield Result(state=State.CRIT, summary='Host unavailable; uplink realization cannot establish current network health'); return
            status = str(uplink.get('syncStatus') or 'unknown').lower()
            state = State.OK if status == 'in-sync' else State.WARN if status in ('pending', 'drifted') else State.CRIT if status in ('error', 'failed') else State.UNKNOWN
            yield Result(state=state, summary=f'Configuration: {status}; NICs: {uplink.get("nic1")}, {uplink.get("nic2")}')
            yield Result(state=State.OK, notice='Last configuration sync: ' + str(uplink.get('lastSyncDate')) + '; not a periodic link measurement. Physical carrier, LACP member health and NIC error counters are not verified by this endpoint.')
            return
    yield Result(state=State.UNKNOWN, summary='Uplink absent from current API inventory')


EXT = ['morpheus_extended']
VM = ['morpheus_vm']
INVENTORY = ['morpheus_vm_inventory']
check_plugin_morpheus_vm_inventory = CheckPlugin(name='morpheus_vm_inventory', sections=INVENTORY, service_name='Morpheus VM Power Overview', discovery_function=discover_collection, check_function=check_vm_inventory)
check_plugin_morpheus_vm_power = CheckPlugin(
    name='morpheus_vm_power', sections=INVENTORY, service_name='Morpheus VM Power %s',
    discovery_function=discover_vm_power, check_function=check_vm_power,
    check_ruleset_name='morpheus_vm_power', check_default_parameters={'expected_power': 'any'},
)
check_plugin_morpheus_inventory_snapshots = CheckPlugin(name='morpheus_inventory_snapshots', sections=INVENTORY, service_name='Morpheus Snapshot Overview', discovery_function=discover_inventory_snapshots, check_function=check_inventory_snapshots)
check_plugin_morpheus_extended_collection = CheckPlugin(name='morpheus_extended_collection', sections=EXT, service_name='Morpheus Extended API collection', discovery_function=discover_collection, check_function=check_collection)
check_plugin_morpheus_vm_snapshots = CheckPlugin(name='morpheus_vm_snapshots', sections=VM, service_name='Morpheus VM Snapshots', discovery_function=discover_snapshots, check_function=check_snapshots, check_ruleset_name='morpheus_snapshots', check_default_parameters={'age_warn': 604800, 'age_crit': 2592000})
check_plugin_morpheus_vm_volume = CheckPlugin(name='morpheus_vm_volume', sections=VM, service_name='Morpheus VM Volume %s', discovery_function=discover_volumes, check_function=check_volume)
check_plugin_morpheus_license = CheckPlugin(name='morpheus_license', sections=EXT, service_name='Morpheus License expiration', discovery_function=discover_license, check_function=check_license, check_ruleset_name='morpheus_license', check_default_parameters={'warn_days': 30, 'crit_days': 7})
check_plugin_morpheus_license_limit = CheckPlugin(name='morpheus_license_limit', sections=EXT, service_name='Morpheus License capacity %s', discovery_function=discover_license_limits, check_function=check_license_limit)
check_plugin_morpheus_appliance_alarms = CheckPlugin(name='morpheus_appliance_alarms', sections=EXT, service_name='Morpheus Appliance alarms', discovery_function=discover_appliance_alarms, check_function=check_appliance_alarms)
check_plugin_morpheus_vm_alarms = CheckPlugin(name='morpheus_vm_alarms', sections=VM, service_name='Morpheus VM Alarms', discovery_function=discover_appliance_alarms, check_function=check_vm_alarms)
check_plugin_morpheus_virtual_switch = CheckPlugin(name='morpheus_virtual_switch', sections=EXT, service_name='Morpheus Virtual Switch %s', discovery_function=discover_switches, check_function=check_switch)
check_plugin_morpheus_uplink = CheckPlugin(name='morpheus_uplink', sections=EXT, service_name='Morpheus Uplink %s Configuration', discovery_function=discover_uplinks, check_function=check_uplink)
