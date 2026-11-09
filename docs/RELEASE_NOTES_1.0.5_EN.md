# HPE Morpheus Monitoring 1.0.5

Fix host-failure reporting and VM metric retention; add VM disk IO and cluster membership graphs.

- Explicit failed membership, including `unclean`, now reports CRIT rather than falling through to UNKNOWN. Unknown power does not hide a known host failure.
- Unavailable hypervisors no longer publish healthy zero CPU/RAM values or old hardware readings as current.
- CPU, RAM, storage and disk IO retain independent timestamped samples. Missing RAM cannot force fresh CPU/storage onto an old complete snapshot. Legacy VM caches migrate automatically.
- New **Morpheus VM Disk IO** service exposes API-reported read/write IOPS when available.
- Existing cluster State services gain online/total member graphs. These counts do not establish quorum or HA readiness.
- Datastore multipath scope is clarified; per-host paths and full quorum monitoring remain outside this release.

Existing host/service names, established metric names and age thresholds remain unchanged. Rescan existing VM hosts to discover Disk IO services, then activate changes. No new endpoint permissions are required.

Targets Checkmk 2.4 and the observed Morpheus 9.1.0.1 HVM API. Validation: 85 local unit tests plus public Checkmk 2.4 agent/rules/graph API checks. Live installation, graph rendering and failure/recovery checks of the exact MKP remain required.

Maintainer: Pawel Wladzinski <pawel.wladzinski@vayana.pl>. License: GPL-2.0-only.
