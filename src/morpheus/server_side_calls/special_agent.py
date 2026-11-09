# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
from cmk.server_side_calls.v1 import SpecialAgentConfig, SpecialAgentCommand, noop_parser


def commands(params, host_config):
    args = ['--url', params['url'], '--token', params['token'].unsafe(),
            '--source-host', host_config.name,
            '--name-mode', params.get('name_mode', 'id'),
            '--prefix', params.get('prefix', 'morpheus-vm-'),
            '--timeout', str(params.get('timeout', 20))]
    if params.get('skip_infrastructure'):
        args.append('--skip-infrastructure')
    if params.get('hardware_details'):
        args.append('--hardware-details')
    if params.get('insecure'):
        args.append('--insecure')
    if params.get('zone_id'):
        args.extend(['--zone-id', str(params['zone_id'])])
    yield SpecialAgentCommand(command_arguments=args)

special_agent_morpheus = SpecialAgentConfig(name='morpheus',
    parameter_parser=noop_parser, commands_function=commands)
