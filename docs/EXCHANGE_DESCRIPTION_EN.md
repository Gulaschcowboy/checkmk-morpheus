# HPE Morpheus Monitoring

Read-only HPE Morpheus REST API monitoring for Checkmk 2.4.

## Features

- Appliance/application health, CPU, JVM heap, database connections, storage, threads, Elasticsearch and RabbitMQ health.
- Cloud state and synchronization.
- Datastore capacity, state and multipath counters where available.
- Hypervisor CPU, RAM, power, maintenance and membership.
- Cluster state, members, HA information and worker CPU/RAM.
- Hardware sensor summaries and optional individual sensor checks.
- VM state, power, guest-agent status, CPU, RAM and API storage through piggyback.
- Primary utilization/capacity graphs, readable metric units and Perf-O-Meters.

## Compatibility

Targets Checkmk 2.4. Integration environment: Checkmk 2.4.0p26 CME and Morpheus 9.1.0.1 with HVM. Other editions/providers/versions require validation; Checkmk 2.5 compatibility is not claimed. The exact 1.0.4 publication archive has local unit/public-API validation; verify live behavior in a test site.

## Configuration

Install and enable the MKP. Store a read-access Morpheus API token in Checkmk's Password store. Configure the **HPE Morpheus** rule on one API source host, enter the appliance URL, discover services and activate changes. VM hosts consume piggyback data and can be created manually or using a separately configured DCD connector.

The package contains no installation credentials or customer-specific connection defaults. TLS verification is enabled by default.

## Important behavior

VM CPU preserves the provider's API scale, which can exceed 100%; thresholds must match that scale. VM storage describes API used/capacity values, not guest filesystems. Missing metrics are not fabricated. Last-valid snapshots retain their original timestamps and age into WARN/CRIT. Infrastructure service names changed in 1.0.3; review discovery and matching rules when upgrading older versions.

## Maintainer and license

**Pawel Wladzinski** — pawel.wladzinski@vayana.pl  
**GPL-2.0-only**

Independent community integration; not an official HPE or Checkmk product. See the repository README and changelog for installation details and limitations.

Source, documentation and issues: https://github.com/pwladzinski/checkmk-morpheus

