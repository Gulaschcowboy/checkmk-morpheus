# API coverage review — 1.0.6

Review date: 2026-11-05. This review compares the integration with supplied HVM API samples, its collector whitelist and public Morpheus documentation/OpenAPI. Documentation describes capabilities; it does not establish that a particular appliance, token or provider returns every field.

## Implemented in this release

| Area | Coverage |
| --- | --- |
| Appliance | Application health/version; CPU; JVM heap; database connections; threads; storage; Elasticsearch and RabbitMQ status. |
| Cloud | State and synchronization age. |
| Hypervisor | Power, provisioning status, maintenance, cluster membership, CPU, RAM and hardware sensor summary/optional individual sensors. Explicit member failures suppress misleading usage/sensor readings. |
| Cluster | State, member failures, online/total inventory member counts and graphs, synchronization age, reported HA flag and worker CPU/RAM. |
| Datastore | Online/provisioning/location/maintenance state; capacity; datastore-level multipath counters. |
| VM | Power/state, optional guest-agent expectation, CPU, RAM and API storage with independent last-valid metric groups. |
| VM disk IO | New optional **Morpheus VM Disk IO** item: timestamped `readIOPS` and `writeIOPS`, already present in supplied API samples. Graphs preserve API values, including zeros. |

No additional endpoint or token permission is required by the 1.0.6 monitoring changes. Disk IO is discovered conditionally. The package remains read-only.

## Additional opt-in coverage in 1.0.6

Observed manager API responses confirmed snapshot-list access, virtual-switch/uplink configuration, operational health alarms and finite-license usage. The integration adds these controls behind explicit rule options. Collection errors are not represented as healthy empty datasets. Snapshot lists were empty in the observed deployment; non-empty age/size cases have local schema-based regression coverage and require live acceptance.

Per-volume status/capacity/usedStorage values are exposed as API inventory. No guest filesystem fullness or per-volume measurement timestamp is inferred. Native alarms are summarized account-wide and matched to VM hosts by server IDs. Null license limits are unlimited; the finite usage ratio is calculated from used/max rather than trusting a provider field named percentUsed (which can use a 0..1 scale).

## Valuable remaining gaps

| Priority | Candidate | Evidence and prerequisites |
| --- | --- | --- |
| High | Actual guest filesystem fullness | No per-drive/mount-point filesystem records were present in the audit. Volume usedStorage can disagree with aggregate VM storage and may describe backing/allocation. Obtain guest OS filesystem checks for C:, D: or individual mount points. |
| High | Agent quorum, witness, fencing, DLM and GFS2 | HVM documentation exposes agent-local `/quorum` on port 7443. Obtain and validate responses from every participating host/layout before implementing. Cluster configuration/member flags alone do not establish quorum or successful failover. |
| High | Physical NIC/link/LACP and packet errors | The observed host interface inventory reports active/configuration/mapping, without physical carrier, speed or packet/error/drop counters. vSwitch uplinks report realization/sync, not physical link health. Use operational host/switch data with explicit timestamps/units. |
| High | Multipath/mount health per host | Datastore-level path counters are present and already monitored. They do not certify each host's paths, GFS2 mount or withdraw state. Obtain host-local operational evidence. |
| Medium | Native monitoring checks/incidents | Both endpoints returned HTTP 403 for the audit account. They are not queried automatically by this package. Confirm access/feature scope before considering implementation. |
| Medium | Host-profile compliance | The endpoint was available but no profile was attached. Automatic discovery would create an unhelpful UNKNOWN baseline; consider it when profiles and persisted compliance results exist. |
| Medium | VM CPU Ready and network throughput | Values are present but units, aggregation periods and counter/rate semantics need confirmation before alerting/graphing. |
| Medium | Host root filesystems and physical-memory overcommit | WorkerStats memory and datastore capacity are insufficient substitutes; verify OS measurements and allocation definitions. |

## Important interpretation limits

- Cluster membership counts are inventory counts, not a quorum computation. A member removed from current inventory cannot be detected without a separately configured expected-member baseline.
- `ha_enabled` is the API's existing configuration flag. It is not an end-to-end HA readiness test and may need layout/version-specific interpretation.
- A datastore can be available through a surviving host while another host is down. `Active 2/2` is not proof of four working paths across two hosts.
- Hypervisor unavailability alarms do not distinguish an intentional shutdown from an unplanned failure. No automatic downtime or suppression is introduced.
- A connected guest agent is not proof of fresh/complete resource statistics. Data age is checked independently.
- Independent caches reduce unnecessary cross-metric staleness but cannot recover values that the collector never receives. Missing values never become fabricated zeros.

## Sources reviewed

- [Official HPE Morpheus OpenAPI repository](https://github.com/HewlettPackard/morpheus-openapi), `dev-9.1` branch reviewed on the date above.
- [Health alarms endpoint definition](https://github.com/HewlettPackard/morpheus-openapi/blob/dev-9.1/paths/api%40health%40alarms.yaml).
- [Monitoring checks endpoint definition](https://github.com/HewlettPackard/morpheus-openapi/blob/dev-9.1/paths/api%40monitoring%40checks.yaml).
- [Host snapshots endpoint definition](https://github.com/HewlettPackard/morpheus-openapi/blob/dev-9.1/paths/api%40servers%40id%40snapshots.yaml).
- [Monitoring incidents API](https://apidocs.morpheusdata.com/reference/listincidents).
- [HVM troubleshooting and quorum diagnostics](https://docs.morpheusdata.com/en/9.1/infrastructure/clusters/hvm/troubleshooting.html).
- [HVM cluster alarms](https://docs.morpheusdata.com/en/9.1/infrastructure/clusters/hvm/alarms.html).

No live API responses, customer names, private addresses or credentials are included in this release bundle.
