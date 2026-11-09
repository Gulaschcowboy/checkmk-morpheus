# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice, DefaultValue, Dictionary, DictElement, Integer,
    Password, String, SingleChoice, SingleChoiceElement, migrate_to_password, validators,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic


def form():
    return Dictionary(elements={
        'url': DictElement(required=True, parameter_form=String(
            title=Title('Morpheus URL'),
            custom_validate=(validators.LengthInRange(min_value=9),))),
        'token': DictElement(required=True, parameter_form=Password(
            title=Title('API bearer token'), migrate=migrate_to_password)),
        'insecure': DictElement(parameter_form=BooleanChoice(
            title=Title('Disable TLS certificate verification'), label=Label('Accept self-signed/untrusted certificate'))),
        'skip_infrastructure': DictElement(parameter_form=BooleanChoice(
            title=Title('Disable infrastructure collection (datastores, clusters and hypervisors)'))),
        'hardware_details': DictElement(parameter_form=BooleanChoice(
            title=Title('Discover individual hardware sensors'),
            help_text=Help('May create hundreds of services on the API source host. The hardware summary is always collected.'))),
        'timeout': DictElement(parameter_form=Integer(title=Title('Timeout per HTTP request'),
            prefill=DefaultValue(20), custom_validate=(validators.NumberInRange(min_value=1, max_value=45),))),
        'zone_id': DictElement(parameter_form=Integer(title=Title('Restrict infrastructure and VMs to cloud ID'),
            help_text=Help('Omit to include all clouds visible to the API account. Enter the cloud ID from the target appliance.'),
            custom_validate=(validators.NumberInRange(min_value=1),))),
        'name_mode': DictElement(required=True, parameter_form=SingleChoice(
            title=Title('Piggyback host identity'), prefill=DefaultValue('id'), elements=[
                SingleChoiceElement(name='id', title=Title('Stable Morpheus server ID')),
                SingleChoiceElement(name='name', title=Title('VM name (must be unique)')),
                SingleChoiceElement(name='hostname', title=Title('Guest hostname (must be unique)'))])),
        'prefix': DictElement(required=True, parameter_form=String(
            title=Title('Piggyback host prefix'), prefill=DefaultValue('morpheus-vm-'),
            help_text=Help('Use empty prefix only when intentionally matching existing host names.'))),
    })

rule_spec_morpheus = SpecialAgent(name='morpheus', title=Title('HPE Morpheus'),
    topic=Topic.CLOUD, parameter_form=form)
