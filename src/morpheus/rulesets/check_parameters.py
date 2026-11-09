# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice, DefaultValue, Dictionary, DictElement, Float, Integer,
    SingleChoice, SingleChoiceElement, String, validators,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, HostCondition, Topic


def metric_form():
    return Dictionary(elements={
        'warn': DictElement(parameter_form=Float(title=Title('Warning usage percentage'),
            prefill=DefaultValue(90.0), custom_validate=(validators.NumberInRange(min_value=0, max_value=100),))),
        'crit': DictElement(parameter_form=Float(title=Title('Critical usage percentage'),
            prefill=DefaultValue(95.0), custom_validate=(validators.NumberInRange(min_value=0, max_value=100),))),
        'age_warn': DictElement(parameter_form=Integer(title=Title('Warning data age in seconds'),
            prefill=DefaultValue(900), custom_validate=(validators.NumberInRange(min_value=1),))),
        'age_crit': DictElement(parameter_form=Integer(title=Title('Critical data age in seconds'),
            prefill=DefaultValue(1800), custom_validate=(validators.NumberInRange(min_value=1),))),
    }, help_text=Help('Configure warning below critical. Usage levels apply to CPU, memory and appliance storage. VM storage is informational.'))


def cloud_form():
    return Dictionary(elements={
        'age_warn': DictElement(parameter_form=Integer(title=Title('Warning sync age in seconds'), prefill=DefaultValue(900))),
        'age_crit': DictElement(parameter_form=Integer(title=Title('Critical sync age in seconds'), prefill=DefaultValue(1800))),
    })


def vm_form():
    return Dictionary(elements={
        'expected_power': DictElement(parameter_form=SingleChoice(title=Title('Expected power state'),
            prefill=DefaultValue('any'), elements=[
                SingleChoiceElement(name='any', title=Title('Any known power state')),
                SingleChoiceElement(name='on', title=Title('Powered on')),
                SingleChoiceElement(name='off', title=Title('Powered off'))])),
        'expect_guest_agent': DictElement(parameter_form=BooleanChoice(title=Title('Expect connected Morpheus guest agent while powered on'))),
    })

def vm_metric_form():
    elements = dict(metric_form().elements)
    elements['cache_age_warn'] = DictElement(parameter_form=Integer(title=Title('Warning cached VM snapshot age in seconds'),
        prefill=DefaultValue(120), custom_validate=(validators.NumberInRange(min_value=1),)))
    elements['cache_age_crit'] = DictElement(parameter_form=Integer(title=Title('Critical cached VM snapshot age in seconds'),
        prefill=DefaultValue(900), custom_validate=(validators.NumberInRange(min_value=1),)))
    for key, label, default in (('warn', 'Warning usage percentage', 90.0), ('crit', 'Critical usage percentage', 95.0)):
        elements[key] = DictElement(parameter_form=Float(title=Title(label),
            prefill=DefaultValue(default), custom_validate=(validators.NumberInRange(min_value=0),)))
    return Dictionary(elements=elements, help_text=Help(
        'CPU is the unmodified API cpuUsage and may exceed 100% depending on the provider. '
        'CPU thresholds use this same scale; restrict a rule to item CPU when setting levels above 100. '
        'No automatic vCPU normalization is applied. Memory uses a usage/capacity percentage. VM storage is informational. '
        'Cached snapshots keep their original timestamp. The stricter of the normal and cached age limits applies.'))

rule_spec_morpheus_platform = CheckParameters(name='morpheus_platform', title=Title('Morpheus platform levels'),
    topic=Topic.CLOUD, parameter_form=metric_form, condition=HostAndItemCondition(item_title=Title('Component')))
rule_spec_morpheus_clouds = CheckParameters(name='morpheus_clouds', title=Title('Morpheus cloud synchronization'),
    topic=Topic.CLOUD, parameter_form=cloud_form, condition=HostAndItemCondition(item_title=Title('Cloud name')))
rule_spec_morpheus_vm = CheckParameters(name='morpheus_vm', title=Title('Morpheus VM state'),
    topic=Topic.CLOUD, parameter_form=vm_form, condition=HostCondition())
rule_spec_morpheus_vm_metrics = CheckParameters(name='morpheus_vm_metrics', title=Title('Morpheus VM metric levels'),
    topic=Topic.CLOUD, parameter_form=vm_metric_form, condition=HostAndItemCondition(item_title=Title('Metric')))


def datastore_form():
    elements = dict(metric_form().elements)
    elements['warn'] = DictElement(parameter_form=Float(title=Title('Warning datastore usage percentage'), prefill=DefaultValue(80.0), custom_validate=(validators.NumberInRange(min_value=0, max_value=100),)))
    elements['crit'] = DictElement(parameter_form=Float(title=Title('Critical datastore usage percentage'), prefill=DefaultValue(90.0), custom_validate=(validators.NumberInRange(min_value=0, max_value=100),)))
    return Dictionary(elements=elements)


def multipath_form():
    elements = dict(cloud_form().elements)
    elements['min_paths'] = DictElement(parameter_form=Integer(title=Title('Minimum active multipath paths'), prefill=DefaultValue(2), custom_validate=(validators.NumberInRange(min_value=1),)))
    return Dictionary(elements=elements)


def cluster_state_form():
    elements = dict(cloud_form().elements)
    elements['expect_ha'] = DictElement(parameter_form=BooleanChoice(title=Title('Require cluster HA to be enabled')))
    return Dictionary(elements=elements)

rule_spec_morpheus_datastore_usage = CheckParameters(name='morpheus_datastore_usage', title=Title('Morpheus datastore capacity levels'), topic=Topic.CLOUD, parameter_form=datastore_form, condition=HostAndItemCondition(item_title=Title('Datastore')))
rule_spec_morpheus_multipath = CheckParameters(name='morpheus_multipath', title=Title('Morpheus datastore multipath'), topic=Topic.CLOUD, parameter_form=multipath_form, condition=HostAndItemCondition(item_title=Title('Datastore')))
rule_spec_morpheus_infra_metrics = CheckParameters(name='morpheus_infra_metrics', title=Title('Morpheus infrastructure metric levels'), topic=Topic.CLOUD, parameter_form=metric_form, condition=HostAndItemCondition(item_title=Title('Infrastructure item')))
rule_spec_morpheus_cluster_state = CheckParameters(name='morpheus_cluster_state', title=Title('Morpheus cluster state and HA'), topic=Topic.CLOUD, parameter_form=cluster_state_form, condition=HostAndItemCondition(item_title=Title('Cluster')))



def hardware_form():
    return Dictionary(elements={
        'age_warn': DictElement(parameter_form=Integer(title=Title('Warning hardware snapshot age in seconds'), prefill=DefaultValue(120), custom_validate=(validators.NumberInRange(min_value=1),))),
        'age_crit': DictElement(parameter_form=Integer(title=Title('Critical hardware snapshot age in seconds'), prefill=DefaultValue(900), custom_validate=(validators.NumberInRange(min_value=1),))),
    }, help_text=Help('Applies to the original timestamp of hardware readings, including cached last-valid readings. Set warning below critical.'))

rule_spec_morpheus_hardware = CheckParameters(name='morpheus_hardware', title=Title('Morpheus hardware data freshness'), topic=Topic.CLOUD, parameter_form=hardware_form, condition=HostAndItemCondition(item_title=Title('Hypervisor / sensor')))
