# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
from cmk.graphing.v1 import Title
from cmk.graphing.v1.metrics import Metric, Unit, IECNotation, DecimalNotation, TimeNotation, Color, Product, Constant, Fraction, WarningOf, CriticalOf
from cmk.graphing.v1.graphs import Graph, MinimalRange
from cmk.graphing.v1.perfometers import Perfometer, FocusRange, Closed, Open

metric_morpheus_datastore_used_bytes = Metric(name='morpheus_datastore_used_bytes', title=Title('Datastore used space'), unit=Unit(IECNotation('B')), color=Color.ORANGE)
metric_morpheus_datastore_free_bytes = Metric(name='morpheus_datastore_free_bytes', title=Title('Datastore free space'), unit=Unit(IECNotation('B')), color=Color.GREEN)
metric_morpheus_datastore_size_bytes = Metric(name='morpheus_datastore_size_bytes', title=Title('Datastore capacity'), unit=Unit(IECNotation('B')), color=Color.BLUE)
metric_morpheus_datastore_used_percent = Metric(name='morpheus_datastore_used_percent', title=Title('Datastore utilization'), unit=Unit(DecimalNotation('%')), color=Color.ORANGE)
metric_morpheus_hypervisor_cpu = Metric(name='morpheus_hypervisor_cpu', title=Title('Hypervisor CPU usage'), unit=Unit(DecimalNotation('%')), color=Color.BLUE)
metric_morpheus_hypervisor_memory = Metric(name='morpheus_hypervisor_memory', title=Title('Hypervisor memory usage'), unit=Unit(DecimalNotation('%')), color=Color.GREEN)
metric_morpheus_hypervisor_memory_used_bytes = Metric(name='morpheus_hypervisor_memory_used_bytes', title=Title('Hypervisor used memory'), unit=Unit(IECNotation('B')), color=Color.GREEN)
metric_morpheus_hypervisor_memory_size_bytes = Metric(name='morpheus_hypervisor_memory_size_bytes', title=Title('Hypervisor memory capacity'), unit=Unit(IECNotation('B')), color=Color.BLUE)
metric_morpheus_cluster_cpu_avg = Metric(name='morpheus_cluster_cpu_avg', title=Title('Cluster worker CPU average'), unit=Unit(DecimalNotation('%')), color=Color.BLUE)
metric_morpheus_cluster_memory = Metric(name='morpheus_cluster_memory', title=Title('Cluster worker memory usage'), unit=Unit(DecimalNotation('%')), color=Color.GREEN)
metric_morpheus_cluster_memory_used_bytes = Metric(name='morpheus_cluster_memory_used_bytes', title=Title('Cluster worker used memory'), unit=Unit(IECNotation('B')), color=Color.GREEN)
metric_morpheus_cluster_memory_size_bytes = Metric(name='morpheus_cluster_memory_size_bytes', title=Title('Cluster worker memory capacity'), unit=Unit(IECNotation('B')), color=Color.BLUE)
metric_morpheus_cluster_memory_reserved_bytes = Metric(name='morpheus_cluster_memory_reserved_bytes', title=Title('Cluster reserved memory'), unit=Unit(IECNotation('B')), color=Color.PURPLE)
metric_morpheus_multipath_active = Metric(name='morpheus_multipath_active', title=Title('Active multipath paths'), unit=Unit(DecimalNotation('')), color=Color.GREEN)
metric_morpheus_multipath_failed = Metric(name='morpheus_multipath_failed', title=Title('Failed multipath paths'), unit=Unit(DecimalNotation('')), color=Color.RED)
metric_morpheus_multipath_paths = Metric(name='morpheus_multipath_paths', title=Title('Total multipath paths'), unit=Unit(DecimalNotation('')), color=Color.BLUE)
metric_morpheus_hardware_problems = Metric(name='morpheus_hardware_problems', title=Title('Hardware sensors with problems'), unit=Unit(DecimalNotation('')), color=Color.RED)
metric_morpheus_sensor_temperature = Metric(name='morpheus_sensor_temperature', title=Title('Temperature'), unit=Unit(DecimalNotation('°C')), color=Color.ORANGE)
metric_morpheus_sensor_rpm = Metric(name='morpheus_sensor_rpm', title=Title('Fan speed'), unit=Unit(DecimalNotation('RPM')), color=Color.BLUE)
metric_morpheus_sensor_watts = Metric(name='morpheus_sensor_watts', title=Title('Power'), unit=Unit(DecimalNotation('W')), color=Color.ORANGE)
metric_morpheus_sensor_volts = Metric(name='morpheus_sensor_volts', title=Title('Voltage'), unit=Unit(DecimalNotation('V')), color=Color.GREEN)
metric_morpheus_sensor_percent = Metric(name='morpheus_sensor_percent', title=Title('Sensor utilization'), unit=Unit(DecimalNotation('%')), color=Color.BLUE)

graph_morpheus_datastore_capacity = Graph(name='morpheus_datastore_capacity', title=Title('Datastore capacity'), compound_lines=['morpheus_datastore_used_bytes', 'morpheus_datastore_free_bytes'], simple_lines=['morpheus_datastore_size_bytes'])
graph_morpheus_multipath = Graph(name='morpheus_multipath', title=Title('Multipath paths'), simple_lines=['morpheus_multipath_active', 'morpheus_multipath_failed', 'morpheus_multipath_paths'])
graph_morpheus_hypervisor_memory = Graph(name='morpheus_hypervisor_memory', title=Title('Hypervisor memory'), compound_lines=['morpheus_hypervisor_memory_used_bytes'], simple_lines=['morpheus_hypervisor_memory_size_bytes'])

# Give every emitted metric a readable label and an accurate unit. Existing
# *_mib RRDs stay in MiB; the capacity graph expressions convert them to bytes.
for _name, _title, _notation, _color in (
    ('morpheus_data_age', 'Source data age', TimeNotation(), Color.PURPLE),
    ('morpheus_api_duration', 'API collection duration', TimeNotation(), Color.BLUE),
    ('morpheus_vm_count', 'Virtual machines collected', DecimalNotation(''), Color.GREEN),
    ('morpheus_vm_cpu_percent', 'VM CPU reported by API', DecimalNotation('%'), Color.BLUE),
    ('morpheus_vm_memory_percent', 'VM memory utilization', DecimalNotation('%'), Color.GREEN),
    ('morpheus_vm_memory_used_mib', 'VM used memory', DecimalNotation('MiB'), Color.GREEN),
    ('morpheus_vm_memory_max_mib', 'VM memory capacity', DecimalNotation('MiB'), Color.BLUE),
    ('morpheus_vm_storage_used_mib', 'VM used storage reported by API', DecimalNotation('MiB'), Color.ORANGE),
    ('morpheus_vm_storage_max_mib', 'VM storage capacity reported by API', DecimalNotation('MiB'), Color.BLUE),
    ('morpheus_process_cpu', 'Morpheus process CPU', DecimalNotation('%'), Color.BLUE),
    ('morpheus_system_cpu', 'Appliance system CPU', DecimalNotation('%'), Color.ORANGE),
    ('morpheus_jvm_percent', 'JVM heap utilization', DecimalNotation('%'), Color.GREEN),
    ('morpheus_jvm_used_mib', 'JVM used heap', DecimalNotation('MiB'), Color.GREEN),
    ('morpheus_jvm_max_mib', 'JVM heap capacity', DecimalNotation('MiB'), Color.BLUE),
    ('morpheus_system_available_mib', 'Appliance available memory', DecimalNotation('MiB'), Color.BLUE),
    ('morpheus_db_connections_percent', 'Database connection utilization', DecimalNotation('%'), Color.ORANGE),
    ('morpheus_db_connections', 'Database connections', DecimalNotation(''), Color.BLUE),
    ('morpheus_threads', 'Application threads', DecimalNotation(''), Color.BLUE),
    ('morpheus_busyqueuescount', 'Busy RabbitMQ queues', DecimalNotation(''), Color.ORANGE),
    ('morpheus_errorqueuescount', 'RabbitMQ queues with errors', DecimalNotation(''), Color.RED),
    ('morpheus_appliance_storage_percent', 'Appliance storage utilization', DecimalNotation('%'), Color.ORANGE),
):
    globals()['metric_' + _name] = Metric(name=_name, title=Title(_title), unit=Unit(_notation), color=_color)

def _bytes_from_mib(name, title, color):
    return Product(Title(title), Unit(IECNotation('B')), color,
                   [name, Constant(Title('MiB to bytes'), Unit(DecimalNotation('')), color, 1048576)])

# Explicit business graphs are evaluated before the automatic fallback graph
# for morpheus_data_age. Do not define a standalone age graph ahead of these.
for _name, _title, _metric, _bounded in (
    ('morpheus_vm_cpu', 'VM CPU reported by API', 'morpheus_vm_cpu_percent', False),
    ('morpheus_vm_memory_01_utilization', 'VM memory utilization', 'morpheus_vm_memory_percent', True),
    ('morpheus_datastore_utilization', 'Datastore utilization', 'morpheus_datastore_used_percent', True),
    ('morpheus_hypervisor_cpu', 'Hypervisor CPU usage', 'morpheus_hypervisor_cpu', True),
    ('morpheus_hypervisor_memory_utilization', 'Hypervisor memory utilization', 'morpheus_hypervisor_memory', True),
    ('morpheus_cluster_cpu', 'Cluster worker CPU average', 'morpheus_cluster_cpu_avg', True),
    ('morpheus_cluster_memory_01_utilization', 'Cluster worker memory utilization', 'morpheus_cluster_memory', True),
    ('morpheus_jvm_01_utilization', 'JVM heap utilization', 'morpheus_jvm_percent', True),
    ('morpheus_database_01_utilization', 'Database connection utilization', 'morpheus_db_connections_percent', True),
    ('morpheus_appliance_storage', 'Appliance storage utilization', 'morpheus_appliance_storage_percent', True),
    ('morpheus_hardware', 'Hardware sensors with problems', 'morpheus_hardware_problems', False),
    ('morpheus_sensor_temperature', 'Temperature', 'morpheus_sensor_temperature', False),
    ('morpheus_sensor_rpm', 'Fan speed', 'morpheus_sensor_rpm', False),
    ('morpheus_sensor_watts', 'Power', 'morpheus_sensor_watts', False),
    ('morpheus_sensor_volts', 'Voltage', 'morpheus_sensor_volts', False),
    ('morpheus_sensor_percent', 'Sensor utilization', 'morpheus_sensor_percent', True),
):
    globals()['graph_' + _name] = Graph(name=_name, title=Title(_title), compound_lines=[_metric],
        simple_lines=[WarningOf(_metric), CriticalOf(_metric)],
        minimal_range=MinimalRange(0, 100) if _bounded else None)

graph_morpheus_vm_memory_02_capacity = Graph(name='morpheus_vm_memory_02_capacity', title=Title('VM memory used and capacity'),
    compound_lines=[_bytes_from_mib('morpheus_vm_memory_used_mib', 'Used memory', Color.GREEN)],
    simple_lines=[_bytes_from_mib('morpheus_vm_memory_max_mib', 'Memory capacity', Color.BLUE)])
graph_morpheus_vm_storage = Graph(name='morpheus_vm_storage', title=Title('VM storage reported by API (not guest filesystems)'),
    compound_lines=[_bytes_from_mib('morpheus_vm_storage_used_mib', 'Used storage', Color.ORANGE)],
    simple_lines=[_bytes_from_mib('morpheus_vm_storage_max_mib', 'Storage capacity', Color.BLUE)])
graph_morpheus_jvm_02_capacity = Graph(name='morpheus_jvm_02_capacity', title=Title('JVM heap used and capacity'),
    compound_lines=[_bytes_from_mib('morpheus_jvm_used_mib', 'Used heap', Color.GREEN)],
    simple_lines=[_bytes_from_mib('morpheus_jvm_max_mib', 'Heap capacity', Color.BLUE)])
graph_morpheus_system_memory_available = Graph(name='morpheus_system_memory_available', title=Title('Appliance available memory'),
    compound_lines=[_bytes_from_mib('morpheus_system_available_mib', 'Available memory', Color.BLUE)])
graph_morpheus_cluster_memory_02_capacity = Graph(name='morpheus_cluster_memory_02_capacity', title=Title('Cluster worker memory'),
    compound_lines=['morpheus_cluster_memory_used_bytes'],
    simple_lines=['morpheus_cluster_memory_size_bytes', 'morpheus_cluster_memory_reserved_bytes'], optional=['morpheus_cluster_memory_reserved_bytes'])
graph_morpheus_platform_cpu = Graph(name='morpheus_platform_cpu', title=Title('Morpheus process and system CPU'), simple_lines=['morpheus_process_cpu', 'morpheus_system_cpu'], minimal_range=MinimalRange(0, 100))
graph_morpheus_database_02_connections = Graph(name='morpheus_database_02_connections', title=Title('Database connections'), compound_lines=['morpheus_db_connections'])
graph_morpheus_threads = Graph(name='morpheus_threads', title=Title('Application threads'), compound_lines=['morpheus_threads'])
graph_morpheus_rabbit = Graph(name='morpheus_rabbit', title=Title('RabbitMQ queue problems'), simple_lines=['morpheus_busyqueuescount', 'morpheus_errorqueuescount'])
graph_morpheus_api_duration = Graph(name='morpheus_api_duration', title=Title('API collection duration'), compound_lines=['morpheus_api_duration'])
graph_morpheus_vm_count = Graph(name='morpheus_vm_count', title=Title('Virtual machines collected'), compound_lines=['morpheus_vm_count'])

# Open CPU upper border: the API can legitimately report more than 100%.
for _metric in ('morpheus_vm_cpu_percent', 'morpheus_vm_memory_percent',
                'morpheus_datastore_used_percent', 'morpheus_hypervisor_cpu',
                'morpheus_hypervisor_memory', 'morpheus_cluster_cpu_avg',
                'morpheus_cluster_memory', 'morpheus_jvm_percent',
                'morpheus_appliance_storage_percent', 'morpheus_db_connections_percent',
                'morpheus_system_cpu'):
    globals()['perfometer_' + _metric] = Perfometer(name=_metric,
        focus_range=FocusRange(Closed(0), Open(100) if _metric == 'morpheus_vm_cpu_percent' else Closed(100)),
        segments=[_metric])

perfometer_morpheus_vm_storage = Perfometer(name='morpheus_vm_storage', focus_range=FocusRange(Closed(0), Open(100)), segments=[
    Product(Title('API storage utilization'), Unit(DecimalNotation('%')), Color.ORANGE, [
        Fraction(Title('API storage ratio'), Unit(DecimalNotation('')), Color.ORANGE,
            dividend='morpheus_vm_storage_used_mib', divisor='morpheus_vm_storage_max_mib'),
        Constant(Title('Percent'), Unit(DecimalNotation('')), Color.ORANGE, 100)])])
