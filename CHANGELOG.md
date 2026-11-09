# Changelog

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

