# HPE Morpheus Monitoring 1.0.4

Publication-ready source and installation package for the Checkmk 2.4 integration.

- English README with installation, API-source and VM-piggyback configuration.
- Changelog, contribution guidance and security-reporting contact.
- GPL-2.0-only license text and source notices; installed COPYING file.
- Optional project URL in the package builder.
- Monitoring behavior and service/metric identities remain as in 1.0.3.

Targets Checkmk 2.4. Integration environment: Checkmk 2.4.0p26 CME and Morpheus 9.1.0.1/HVM. This exact release has local validation: 67 unit tests plus public Checkmk 2.4 API/graph checks. Perform target-site validation before wider deployment. No Checkmk 2.5 support is claimed.

## Assets

- `morpheus-1.0.4.mkp`: Checkmk installation package; also the file to submit to Checkmk Exchange.
- `SHA256SUMS.txt`: checksum for the MKP.

## Upgrade notes

From 1.0.3, install/enable 1.0.4 and validate plugins. From 1.0.2 or earlier, also rediscover infrastructure/cloud services: 1.0.3 changed their names. Review vanished services and rules matching old service items. Historical data is not automatically migrated between renamed services.

