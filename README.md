# HPE Morpheus Monitoring for Checkmk

Read-only monitoring of HPE Morpheus through its REST API, with infrastructure services on an API source host and VM services delivered through Checkmk piggyback.

**Maintainer:** Pawel Wladzinski — pawel.wladzinski@vayana.pl  
**Version:** 1.0.4  
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

The integration was developed and exercised against the versions above. Version 1.0.4 is a publication/documentation/licensing update to 1.0.3, not a new monitoring implementation. The exact 1.0.4 archive has local test and public Checkmk API validation; final installation, discovery and graph rendering must also be verified on the target site. Local tests do not constitute vendor certification or an uptime guarantee.

## Features

- Appliance version, application health, CPU, JVM heap, database connections, threads, storage, Elasticsearch and RabbitMQ health.
- Cloud state and synchronization age.
- Datastore state, used/free/total capacity and multipath counters when available.
- Hypervisor state, CPU, RAM, maintenance and cluster membership.
- Cluster state, synchronization, member status, HA information and worker CPU/RAM.
- Hardware health summaries and optional individual sensor services.
- VM state, power, Morpheus guest-agent status, CPU, RAM and API-reported storage through piggyback.
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
```

VM listing and infrastructure listings use pagination. The detail endpoint is used for incomplete VM metrics and missing hardware readings.

## Installation

Download `morpheus-1.0.4.mkp` from the release assets or Checkmk Exchange. As the site user:

```bash
mkp inspect ~/morpheus-1.0.4.mkp
mkp add ~/morpheus-1.0.4.mkp
mkp enable morpheus 1.0.4
cmk-validate-plugins
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

**Missing VM metrics:** the collector tries a bounded detail lookup and can use the last complete site-local snapshot. The original timestamp is preserved and the source is displayed. Missing fields are not replaced by zeros from the untimestamped top-level `stats` aggregate. Without an initial complete sample, missing metrics remain UNKNOWN. At critical age, usage metrics are not emitted as current values. Capacity changes prevent reuse of an older VM snapshot, and an observed powered-off VM clears its baseline.

**Hardware:** missing sensors trigger a detail lookup, followed by a last-valid snapshot when available. The original hardware timestamp is used; a fresh CPU timestamp does not refresh old hardware data. Unavailable sensors are counted separately from failed sensors.

## Security and operation

Only GET requests are used; redirects are blocked and response sizes/pagination are bounded. Output is normalized to selected fields, not full API configuration objects.

Runtime caches are scoped by site, appliance URL and token identity under `$OMD_ROOT/var/check_mk/morpheus_vm_stats/` and `morpheus_hardware/`. Snapshot files use mode 0600 and identity directories mode 0700. Without `OMD_ROOT`, persistent caches are disabled. Old cache files for removed objects are not automatically garbage-collected; absent VMs are not emitted from the cache as active inventory.

The token is stored in the installation's Password store. Checkmk 2.4 passes it through the special-agent argument mechanism; command-line diagnostics may expose arguments. Optional `setproctitle` reduces process-title exposure after startup but does not eliminate the startup window. Do not publish tokens, raw appliance exports or unreviewed debug output. Token refresh is not implemented.

## Limits

- No monitoring configuration writes, automatic downtime or acknowledgement actions.
- No backup-job, virtual-network or full quorum monitoring in this package.
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

Output: `dist/morpheus-1.0.4.mkp`. Optionally set the metadata project URL after creating your repository:

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

