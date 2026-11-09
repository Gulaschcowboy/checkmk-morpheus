# Upgrade to 1.1.0

Install `package/morpheus-1.1.0.mkp`. Source, tests and diagnostic tools are included in the ZIP for review; only files under `src/` are installed by the MKP. Existing established service/metric/host identities remain unchanged.

As the Checkmk site user:

```bash
mkp inspect ~/morpheus-1.1.0.mkp
mkp add ~/morpheus-1.1.0.mkp
mkp enable morpheus 1.1.0
mkp list
cmk-validate-plugins
cmk -U
omd restart
```

The restart briefly interrupts monitoring and the site web interface. Regeneration/restart loads new code into persistent core, GUI and helper processes. Installing files alone can leave an older check implementation running in memory.

In a distributed installation, install matching code on the sites that execute collection/checks and provide central configuration/graphs, using your usual extension-distribution method.

## Enable new collections

Open the existing **HPE Morpheus** special-agent rule. Enable the options needed:

- **Collect VM snapshots**
- **Discover individual API volumes**
- **Collect virtual switches and per-host uplinks**
- **Collect appliance/account-wide health alarms**
- **Collect appliance license expiration and capacity**

Keep infrastructure collection enabled for virtual-switch collection. The snapshot and license options may require additional read permissions. Alarm and license summaries are appliance/account-wide, irrespective of the cloud inventory filter. Existing rules default all new collections to disabled.

Save and activate the rule. Rescan the API source host and existing VM hosts, accept the new services, then activate changes. Existing-host service discovery is required; discovery during DCD host creation is insufficient for hosts that already exist.

## New source services
- Morpheus VM Power Overview and individual Morpheus VM Power services. Use the Morpheus VM expected power state rule to enforce ON or OFF for selected VMs.
- Morpheus Snapshot Overview when snapshot collection is enabled. Incomplete coverage is UNKNOWN and suppresses the total metric.

- Morpheus Extended API collection
- Morpheus Virtual Switch [cluster / switch]
- Morpheus Uplink [cluster / switch / host] Configuration
- Morpheus Appliance alarms
- Morpheus License expiration
- Morpheus License capacity [finite limit code]

## New VM services

- Morpheus VM Snapshots
- Morpheus VM Volume [device or qualified name]
- Morpheus VM Alarms

Snapshot services are discovered even for a successful zero-snapshot response, so future snapshots are monitored without creating a new service. Permission/timeout/incomplete response errors remain unavailable. Volume discovery omits zero-capacity and recognized optical/removable media. An API volume is not a guest filesystem check.

## Acceptance checks

1. Confirm an empty successful snapshot list gives count 0; a failed request must give UNKNOWN, not OK count 0.
2. Verify snapshot age levels match your retention policy (defaults 7/30 days). Snapshot size may be absent.
3. Confirm vSwitch and uplink names/mappings match the UI. Configuration sync dates can be old while still in-sync; no physical carrier inference is made.
4. Confirm current host failure still raises CRIT despite an in-sync uplink record.
5. Compare open API alarms with the UI. VM association uses IDs, so an alarm's old display name can differ after a VM rename.
6. Confirm finite license usage and expiry. Full allocation (e.g. 2/2 sockets) is WARN; it is not proof of an outage. Above-limit use is CRIT. Unlimited/null metrics are not discovered as finite limits.
7. Existing VM telemetry age thresholds remain in force. A successful API/agent connection does not fabricate missing resource measurements.

No guest filesystem, physical NIC/LACP or full agent-quorum implementation is added by this release. See [TROUBLESHOOTING_API_STATS.md](TROUBLESHOOTING_API_STATS.md).

## Rollback

Enable a previously retained MKP (for example `mkp enable morpheus 1.0.5`), regenerate the configuration and restart the site. Review newly added services as vanished after rollback. Established VM/cache behavior remains compatible with 1.0.5.
