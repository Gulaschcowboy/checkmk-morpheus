# HPE Morpheus Monitoring

Read-only HPE Morpheus REST API monitoring for Checkmk 2.4, 2.5 and 3.0.

## Features

- Appliance/application health, CPU, JVM heap, database connections, storage, threads, Elasticsearch and RabbitMQ health.
- Cloud state and synchronization.
- Datastore capacity, state and multipath counters where available.
- Hypervisor CPU, RAM, power, maintenance and membership.
- Cluster state, member counts/graphs, HA information and worker CPU/RAM.
- Hardware sensor summaries and optional individual sensor checks.
- VM state, power, guest-agent status, CPU, RAM, API storage and conditional read/write disk IOPS through piggyback.
- VM power overview and individual power checks on the API source host, plus a snapshot overview when collection is enabled.
- Primary utilization/capacity graphs, readable metric units and Perf-O-Meters.

- Optional snapshot age/count/size, API volume inventory, health alarms, license expiration/capacity and virtual-switch/uplink configuration sync checks.

## Compatibility

Targets Checkmk 2.4. Integration environment: Checkmk 2.4.0p26 CME and Morpheus 9.1.0.1 with HVM. The package can be installed up to Checkmk 3.0 (usable before 3.1.0); it was installed and exercised on a Checkmk 3.0.0 daily build against a mock Morpheus API. Checkmk 2.5 and other editions/providers/versions require validation. The exact 1.1.0 publication archive has local unit/public-API validation; verify live behavior in a test site.

## Configuration

Install and enable the MKP. Store a read-access Morpheus API token in Checkmk's Password store. Configure the **HPE Morpheus** rule on one API source host, enter the appliance URL, discover services and activate changes. VM hosts consume piggyback data and can be created manually or using a separately configured DCD connector.

The package contains no installation credentials or customer-specific connection defaults. TLS verification is enabled by default.

## Important behavior

VM CPU preserves the provider's API scale, which can exceed 100%; thresholds must match that scale. VM storage describes API used/capacity values, not guest filesystems. Missing metrics are not fabricated. Metric groups retain independent last-valid samples with original timestamps and age into WARN/CRIT. Unavailable hypervisors raise availability alarms instead of reporting healthy zero CPU/RAM; unclean membership is critical. Infrastructure service names changed in 1.0.3; review discovery and matching rules when upgrading older versions.

## Maintainer and license

**Pawel Wladzinski** — pawel.wladzinski@vayana.pl
**GPL-2.0-only**

Independent community integration; not an official HPE or Checkmk product. See the repository README and changelog for installation details and limitations.

Source, documentation and issues: https://github.com/pwladzinski/checkmk-morpheus


New optional collections must be enabled in the special-agent rule. API volume data is not guest filesystem usage; virtual-switch sync is not physical NIC/LACP monitoring. Alarm/license summaries use appliance/account scope. See the API coverage and upgrade guides before enabling.
