# HPE Morpheus Monitoring 1.0.6

Add opt-in snapshot, API volume, health alarm, license and virtual-switch configuration monitoring, grounded in observed Morpheus 9.1.0.1 HVM API responses.

- Snapshot count, oldest-known creation age and reported size; failed API requests never become healthy zero-snapshot results.
- Per-volume API inventory/state/capacity with optical-media filtering. This does not verify guest filesystem free space.
- vSwitch and per-host NIC mapping/configuration sync checks. This does not verify physical carrier, LACP member health or NIC counters.
- Appliance/account-wide open alarm summary and VM alarm services matched by stable server IDs.
- Earliest installed-license expiry and finite capacity checks, handling null/unlimited and enforced-zero limits correctly.
- Unknown/unverified zero guest RAM is no longer presented as a healthy 0% usage reading when no connected/reported guest-agent heartbeat is present.
- Optional endpoint errors retain the mandatory VM inventory and are surfaced explicitly.
- Read-only API audit and one-minute VM telemetry phase sampler included in source tools.

Enable the new options in the special-agent rule, activate, rescan existing source/VM hosts and activate again. Existing metric identities and freshness thresholds remain unchanged. Restart site processes after installation so updated code is loaded.

Local validation: 124 unit tests; public Checkmk 2.4 agent/rules/graph API checks; source/archive/privacy validation. Live exact-archive acceptance on the target site remains required.

Maintainer: Pawel Wladzinski <pawel.wladzinski@vayana.pl>. GPL-2.0-only.
