# HPE Morpheus Monitoring 1.1.0

This release adds VM and infrastructure monitoring to the Checkmk 2.4 integration since the public 1.0.4 release.

- VM power overview and one power service per VM on the API source host. Set the expected state for selected VMs using the **Morpheus VM expected power state** rule.
- Snapshot overview for the monitored inventory scope and per-VM snapshot count and age. Incomplete API coverage is reported explicitly.
- Optional API volume inventory, appliance and VM alarms, license expiration and capacity, and virtual switch and uplink configuration status.
- Independent VM CPU, memory, storage and disk I/O samples keep their original timestamps when reused from the cache.
- Improved handling of unavailable hypervisors, missing hardware sensor data, and unclean cluster membership.

Targets Checkmk 2.4 and the Morpheus 9.1 API. The source archive includes the upgrade guide and the release passed 126 unit tests and validation against the public Checkmk 2.4 plugin APIs. Verify the exact MKP on your Checkmk site before rolling it out.

Enable optional collections in the HPE Morpheus special-agent rule as needed, run service discovery, and activate changes. See [the upgrade guide](https://github.com/pwladzinski/checkmk-morpheus/blob/v1.1.0/docs/UPGRADE_1.1.0.md).

Maintainer: Pawel Wladzinski <pawel.wladzinski@vayana.pl>. License: GPL-2.0-only.
