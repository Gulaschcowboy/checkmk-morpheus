# Changelog

## 1.1.0 — 2026-11-09

- Public feature release consolidating the changes from 1.0.5 through 1.0.8.
- Add per-VM power checks with configurable expected states, power and snapshot overviews, and opt-in infrastructure and VM checks.

## 1.0.8 — 2026-11-09

- Add a power service for each VM on the API source host with configurable expected state.

## 1.0.7 — 2026-11-09

- Add a VM power overview and a snapshot overview to the API source host.
- Show snapshot counts only for the configured inventory scope and mark incomplete coverage explicitly.

## 1.0.6 — 2026-11-05

- Add opt-in snapshot count, oldest-known age and API size checks; API errors do not become healthy zero counts.
- Add opt-in volume inventory checks with optical-media filtering. API usedStorage is informational and does not assert guest filesystem fullness or measurement freshness.
- Add opt-in virtual-switch and per-host uplink configuration sync checks. Do not interpret interface active or config sync as physical NIC/LACP health.
- Add opt-in appliance/account-wide alarms and ID-matched VM alarm summaries, filtering acknowledged, closed and inactive records.
- Add opt-in license expiration and finite-capacity checks. Null limits are unlimited; zero limits remain enforced. Compute percentage from used/max, not the provider percentUsed scale.
- Keep mandatory VM inventory when optional endpoints fail, with an explicit Extended API collection service.
- Treat zero used RAM without a connected/reported guest-agent heartbeat as unverified.
- Add read-only API audit and one-minute VM statistics phase sampling tools. Existing metric timestamps/age limits are not changed to hide upstream missing data.
- Local validation: 124 unit tests, public Checkmk 2.4 API checks and archive/source/privacy verification. Live exact-archive acceptance remains required.

## 1.0.5 — 2026-11-02

- Treat explicit failed cluster membership, including unclean/fenced/unreachable/lost, as CRIT; an unknown host power state no longer hides a known host failure.
- Suppress CPU, RAM and hardware readings for unavailable hypervisors instead of displaying healthy zero values or old sensors.
- Retain CPU, RAM, storage and disk IO independently with their original timestamps; complementary list/detail groups never share fabricated timestamps.
- Read legacy VM caches and migrate to per-group schema 2; retain capacity-change and power-off protections.
- Add conditional VM Disk IO discovery with API-reported read/write IOPS and a primary graph.
- Add online/total member metrics to the existing cluster State service, without claiming quorum validation.
- Clarify datastore multipath scope and document remaining API coverage gaps.
- No existing host/service/metric identities or age thresholds are changed. New Disk IO items require service discovery.
- Local validation: 85 unit tests and public Checkmk 2.4 API checks; exact-archive validation on a live site is still required.

## 1.0.4 — 2026-10-30

- Prepare an English README, public installation/configuration instructions, contribution and security guidance, and publication materials.
- Publish this release under GPL-2.0-only; include the license text inside the installed MKP and license/maintainer headers in project sources.
- Keep monitoring behavior from 1.0.3. No new service names or metrics are introduced by 1.0.4.
- Add an optional HTTPS project URL argument to the builder and write build output to the project's `dist/` directory.
- Further anonymize sample datastore names. No live customer configuration is included.
- Local validation: 67 unit tests and public Checkmk 2.4 API/graph checks. Target-site validation of the exact release remains required.

## 1.0.3 — 2026-10-30

- Use readable infrastructure and cloud service names, without IDs for unique objects.
- Qualify duplicates by cloud and then by IDs when needed.
- Keep object IDs in service details.
- Upgrade note: infrastructure/cloud service items changed. Discover replacement services, review vanished services, and update rules that match old names/IDs. Existing history is not automatically moved to new names.

## 1.0.2 — 2026-10-29

- Retain timestamped last-complete VM snapshots across incomplete API samples; warn at 120 seconds and become critical at 900 seconds by default.
- Preserve original timestamps; reject reuse after capacity changes and clear snapshots after observed power-off.
- Add primary graphs, named metrics, accurate units and Perf-O-Meters across VM, infrastructure and appliance checks.
- Preserve existing metric names and RRD scales; convert MiB to bytes in graph expressions only.

## 1.0.1 — 2026-10-29

- Accept API CPU readings above 100% without normalization or clamping.
- Allow VM CPU thresholds above 100.
- Try bounded per-VM detail lookups when listing statistics are incomplete.

## 1.0.0 — 2026-10-29

- Set the public package title and maintainer metadata.
- Preserve monitoring logic from 0.2.2.

## 0.2.2 — 2026-10-29

- Add detail and timestamp-preserving hardware-cache fallbacks.

## 0.2.1 — 2026-10-29

- Treat cluster `syncing` as a transitional state while retaining freshness/member checks.

## 0.2.0 — 2026-10-29

- Add datastores, multipath, hypervisors, clusters, hardware summaries and optional sensors.

## 0.1.0 — 2026-10-29

- Initial appliance/cloud checks and VM piggyback integration.
