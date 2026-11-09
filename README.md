# HPE Morpheus Monitoring for Checkmk

Read-only monitoring of HPE Morpheus through its REST API, with infrastructure services on an API source host and VM services delivered through Checkmk piggyback.

**Maintainer:** Pawel Wladzinski — pawel.wladzinski@vayana.pl
**Version:** 1.1.0
**License:** GPL-2.0-only

This is an independent community integration. It is not an official HPE or Checkmk product and is not endorsed by either vendor.

**Source and issues:** https://github.com/pwladzinski/checkmk-morpheus

## Compatibility and validation

| Component | Scope |
| --- | --- |
| Checkmk | 2.4; package minimum 2.4.0, usable before 2.5.0 |
| Observed Checkmk environment | 2.4.0p26 CME |
| Morpheus API environment | 9.1.0.1 |
| Provider exercised in the deployment | Morpheus HVM |
| VMware inventory | Sample-data coverage; no claim of full live provider validation |
| Checkmk 2.5 / other Morpheus versions | Not validated |

Release 1.1.0 adds per-VM power services and power and snapshot overviews on the API source host, alongside opt-in checks for snapshots, volumes, alarms, licenses, and virtual switch configuration. The release was validated locally against the public Checkmk 2.4 plugin APIs. Verify installation and discovery on the target site.

## Features

- Appliance version, application health, CPU, JVM heap, database connections, threads, storage, Elasticsearch and RabbitMQ health.
- Cloud state and synchronization age.
- Datastore state, used/free/total capacity and multipath counters when available.
- Hypervisor state, CPU, RAM, maintenance and cluster membership.
- Cluster state, synchronization, member status/counts, HA information and worker CPU/RAM.
- Hardware health summaries and optional individual sensor services.
- VM state, power, Morpheus guest-agent status, CPU, RAM, API-reported storage and read/write disk IOPS through piggyback.
- Named metrics, units, primary usage/capacity graphs and Perf-O-Meters; source data age remains auxiliary.

Object names are used in infrastructure service names. Duplicate names are qualified by cloud and, when necessary, IDs. IDs remain available in service details. Names and name collisions can affect service identity; see [CHANGELOG.md](CHANGELOG.md) before upgrading older versions.

## Requirements

The Checkmk site must reach the Morpheus HTTPS endpoint. Create a dedicated API account/token with read access to the selected objects and endpoints. No write operations are performed. Exact permissions depend on Morpheus roles and tenant scope; verify access using the same API account that Checkmk will use.

Endpoints used include:

```text
GET /api/health
GET /api/zones
GET /api/servers?vm=true
GET /api/servers?vmHypervisor=true
GET /api/servers/{id}
GET /api/clusters
GET /api/zones/{id}/data-stores
GET /api/clusters/{id}/datastores
GET /api/servers/{id}/snapshots           # opt-in
GET /api/health/alarms                    # opt-in, appliance/account scope
GET /api/license                          # opt-in, appliance/account scope
GET /api/virtual-switches?clusterId={id}   # opt-in
GET /api/virtual-switches/{id}/uplinks     # opt-in
```

VM listing and infrastructure listings use pagination. The detail endpoint is used for incomplete VM metrics and missing hardware readings.

## Installation

Download `morpheus-1.1.0.mkp` from the release assets or Checkmk Exchange. As the site user:

```bash
mkp inspect ~/morpheus-1.1.0.mkp
mkp add ~/morpheus-1.1.0.mkp
mkp enable morpheus 1.1.0
cmk-validate-plugins
cmk -U
omd restart
```

Alternatively, use **Setup → Maintenance → Extension packages** to upload and enable the MKP. If GUI rule/graph definitions remain cached, restart the site's Apache with `omd restart apache`, then reload the page. This briefly interrupts web access.

## Configure the API source host

1. Save the Morpheus API token in Checkmk's Password store.
2. Create a logical API host, for example `morpheus-api`.
3. Set **Checkmk agent / API integrations** to **Configured API integrations, no Checkmk agent**, and disable SNMP. Configure the host address and host check according to your network.
4. Search Setup for **HPE Morpheus**, create a rule and restrict it to this source host.
5. Enter the appliance base URL, for example `https://morpheus.example.com` without `/api`, and select the token.
6. Leave TLS verification enabled. Install/trust the appropriate CA; disabling verification is an explicit alternative for an untrusted/self-signed certificate.
7. Optionally restrict collection to a cloud ID. Omit the filter to include all clouds visible to the API account.
8. Initially leave individual hardware sensors disabled; enabling them can create hundreds of additional services.
9. Run service discovery on the source host, accept the services and activate changes.

The package includes no customer URL, credential, site name or DCD configuration. Required connection details are entered in each installation's rule.

## Configure VM hosts

The default piggyback identity is `morpheus-vm-<server-id>`. The integration rule can use the VM name or guest hostname and an optional prefix instead. Ensure the resulting names are unique and match the intended Checkmk hosts exactly.

For hosts monitored **only through this piggyback integration**, configure:

- **Checkmk agent / API integrations:** No API integrations, no Checkmk agent.
- **SNMP:** No SNMP.
- **IP address family:** No IP.
- **Piggyback:** Always use and expect piggyback data.

Create those hosts manually or use Dynamic host management in an edition that provides it. Restrict a DCD piggyback connector to the API source host and intended VM name pattern, and enable **Discover services during creation**. DCD is configured separately; installing the MKP does not create a connection.

For an existing host that also uses an OS agent, retain the required OS-agent configuration and arrange intentional piggyback name matching. The settings above describe piggyback-only hosts.

## Thresholds and data semantics

| Check/rule | Default WARN / CRIT |
| --- | --- |
| General CPU/RAM/platform utilization | 90% / 95% |
| Datastore utilization | 80% / 90% |
| Normal VM/source metric age | 900 s / 1800 s |
| Cached VM snapshot age | 120 s / 900 s |
| Hardware snapshot age | 120 s / 900 s |

Configure these through the corresponding Morpheus check-parameter rules. For cached VM data, the stricter of normal and cached age limits applies. Multipath normally expects at least two active paths. HA is informational unless the rule explicitly requires it.

**CPU:** `stats.cpuUsage` is preserved in the API's scale, including values above 100%. There is no automatic multiplication, division by vCPU count or clamping. CPU thresholds use that same scale; rules limited to item `CPU` may use thresholds above 100. Confirm the provider's semantics before interpreting a raw value as normalized VM capacity.

**RAM:** usage is calculated from the API's used/max memory fields. A zero reported by a disconnected guest agent is not proof that the guest uses no RAM.

**Storage:** VM storage is informational API used/capacity data, not guest filesystem utilization. Directory datastores can share one backing filesystem and report identical capacity; do not sum them as independent storage pools.

**Missing VM metrics:** CPU, RAM, storage and disk IO are retained independently, each with its own original timestamp and source. A missing RAM value cannot force fresh CPU/storage to use an older snapshot. A bounded detail lookup can complement the listing with independent valid metric groups; a usage/capacity pair always comes from the same response. Untimestamped top-level `stats` aggregates are not used. Missing fields are not replaced by zeros. Without a valid initial sample for a group, that group remains UNKNOWN. At critical age, its usage metrics are not emitted. Capacity changes prevent reuse of cached groups, and observed power-off clears the baseline. Legacy 1.0.4 caches migrate automatically without refreshing timestamps. This cannot recover measurements that the API never returns during collection.

**Disk IO:** the `Disk IO` item is discovered only when both `readIOPS` and `writeIOPS` are available, including valid zeros. Values are presented as API-reported read/write IOPS, without counter-to-rate conversion or usage thresholds. The VM metric age rules also apply to disk IO.

**Hypervisor failures:** membership states `unclean`, `fenced`, `offline`, `unreachable`, `lost` and other explicit failure states raise CRIT. A known failure is not hidden by an unknown power state. CPU, RAM and hardware readings are suppressed while the hypervisor is unavailable; the corresponding services explain the unavailability rather than showing healthy zero usage. Unconfirmed power/membership produces UNKNOWN. On recovery, fresh readings resume. Planned shutdowns still raise an availability alarm; use Checkmk downtime for planned work.

**Cluster members:** the existing State service graphs the online/total members in the current API inventory. This is not quorum verification and does not establish that HA or failover worked. Removed inventory members cannot be detected from current membership alone.

**Multipath scope:** the existing datastore service evaluates datastore-level API counters. It does not verify every host's FC/iSCSI paths independently. A datastore can remain accessible through a surviving host.

**Hardware:** missing sensors trigger a detail lookup, followed by a last-valid snapshot when available. The original hardware timestamp is used; a fresh CPU timestamp does not refresh old hardware data. Unavailable sensors are counted separately from failed sensors.

## Security and operation

Only GET requests are used; redirects are blocked and response sizes/pagination are bounded. Output is normalized to selected fields, not full API configuration objects.

Runtime caches are scoped by site, appliance URL and token identity under `$OMD_ROOT/var/check_mk/morpheus_vm_stats/` and `morpheus_hardware/`. Snapshot files use mode 0600 and identity directories mode 0700. Without `OMD_ROOT`, persistent caches are disabled. Old cache files for removed objects are not automatically garbage-collected; absent VMs are not emitted from the cache as active inventory.

The token is stored in the installation's Password store. Checkmk 2.4 passes it through the special-agent argument mechanism; command-line diagnostics may expose arguments. Optional `setproctitle` reduces process-title exposure after startup but does not eliminate the startup window. Do not publish tokens, raw appliance exports or unreviewed debug output. Token refresh is not implemented.

## Limits

- No monitoring configuration writes, automatic downtime or acknowledgement actions.
- No backup-job, full agent-quorum or physical-NIC monitoring. Virtual-switch configuration checks are opt-in.
- No guest filesystem checks; use an OS agent for guest-level detail.
- Provider API availability determines which metrics are present.
- VM detail fallback is limited to ten VMs per collection and the remaining request budget.
- A source collection failure is not hidden by emitting an old VM inventory.
- Existing installations need rediscovery after infrastructure naming changes introduced in 1.0.3. History is not automatically migrated between renamed services.

## Build and tests

Python 3.12 is the local test baseline. Build uses only the standard library:

```bash
python3 -m unittest discover -s tests -v
python3 build.py
```

Output: `dist/morpheus-1.1.0.mkp`. Optionally set the metadata project URL after creating your repository:

```bash
python3 build.py --download-url https://github.com/pwladzinski/checkmk-morpheus
```

On a Checkmk 2.4 site with its public APIs installed:

```bash
python3 tests/validate_public_api.py
```

Function-level tests use small API result shims; the second script uses the actual public API classes. Neither replaces live collection, `cmk-validate-plugins`, discovery or GUI validation.

## Support and contributions

Use the repository's Issues once published, or contact the maintainer by email. Include package/Checkmk/Morpheus versions, provider type, affected service and sanitized output. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

English publication materials are in [docs/](docs/), including the [publishing guide](docs/PUBLISHING.md).

## License

This release is distributed under **GNU GPL version 2 only**, see [LICENSE](LICENSE). The installed MKP includes `morpheus/COPYING`. Earlier 1.0.3 and previous archives were distributed with MIT notices; this publication release does not revoke permissions already granted for those archives.



See [UPGRADE_1.1.0.md](docs/UPGRADE_1.1.0.md) for installation and acceptance checks, and [API_COVERAGE.md](docs/API_COVERAGE.md) for coverage gaps.


## Source host overviews
**Morpheus VM Power <name> [ID <id>]** provides one service per VM on the source host. By default any known power state is OK. Use the **Morpheus VM expected power state** rule to enforce ON or OFF for selected items. IDs distinguish VMs with the same name.

**Morpheus VM Power Overview** lists VM names and placement in Details, grouped by power state. **Morpheus Snapshot Overview** appears when snapshot collection is enabled. It shows the total and lists VMs with snapshots in Details. Both services follow the special agent's cloud filter and API account visibility. Failed or skipped snapshot requests produce an UNKNOWN overview and no total metric for that run.

## Additional checks in 1.0.6

Enable the corresponding options in the **HPE Morpheus** special-agent rule, then rescan the source and existing VM hosts and activate changes. New endpoint collection is disabled by default so an upgrade does not silently require new permissions or change appliance/account scope.

| Rule option | Services and interpretation |
| --- | --- |
| Collect VM snapshots | One VM snapshot service, including zero-snapshot baselines; count, oldest known age and size when every snapshot has a size. Default age WARN 7 days, CRIT 30 days. Collection failures are UNKNOWN, not zero snapshots. |
| Discover individual API volumes | One service per selected non-optical volume with state and informational capacity/usedStorage. No guest-filesystem fullness thresholds. |
| Collect virtual switches and per-host uplinks | Source-host services for vSwitch status and per-host configuration sync (`in-sync`, `pending`, `drifted`, `error`), with NIC mappings. Requires infrastructure collection. |
| Collect appliance/account-wide health alarms | Source summary of all API-visible unacknowledged/open alarms, irrespective of cloud filter; VM summaries matched by stable compute-server ID, even after a rename. |
| Collect appliance license expiration and capacity | Earliest installed-license expiry (WARN 30 days, CRIT 7 days) and finite capacity limits. Full allocation is WARN; usage above a finite limit is CRIT. Null limits are unlimited; zero limits are enforced without division by zero. |

Snapshots require one extra GET per VM (maximum 100 VMs per run). All endpoint calls share the existing collector time budget. Larger installations should verify runtime and may need a separate collection design. Requested but incomplete data remains unavailable; inventory is never populated from an error response.

**Disk versus filesystem:** `volumes[].usedStorage` can represent storage backing/allocation. It has no independent measurement timestamp in the observed API. It cannot establish C:, D: or mount-point free space, particularly with multiple partitions/LVM. Use guest OS filesystem checks to alarm on a full guest filesystem. Capacity/service labels intentionally say API volume.

**Network scope:** interface `active` and virtual-switch `in-sync` do not prove physical carrier, LACP member health, link speed, packet errors or drops. No fabricated per-NIC traffic/health service is created from these flags. Last configuration sync dates are displayed, not treated as periodic health samples.

**Guest RAM zero:** a powered-on VM reporting zero used RAM without a connected/reported guest-agent heartbeat is UNKNOWN; no healthy 0% RAM metric is emitted from that combination.

See [UPGRADE_1.1.0.md](docs/UPGRADE_1.1.0.md) and [TROUBLESHOOTING_API_STATS.md](docs/TROUBLESHOOTING_API_STATS.md). Standalone audit/sampling tools are in `tools/`; they are not installed as part of the MKP.
