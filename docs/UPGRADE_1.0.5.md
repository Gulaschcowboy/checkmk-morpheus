# Upgrade to 1.0.5

The ZIP contains source files and `package/morpheus-1.0.5.mkp`. Install the MKP, not the ZIP. Existing rules, host names, infrastructure service names and metric identities are retained. VM caches migrate automatically; do not delete them to upgrade.

## Install

Copy the MKP into the home directory of the Checkmk site that runs the Morpheus source host. As that site user:

```bash
mkp inspect ~/morpheus-1.0.5.mkp
mkp add ~/morpheus-1.0.5.mkp
mkp enable morpheus 1.0.5
mkp list
cmk-validate-plugins
```

For distributed monitoring, install/enable the package wherever the special agent and checks run. Keep matching rule/graph definitions on the central configuration/GUI site through the deployment method used for your Checkmk installation. Installing only on a different site cannot change the running collector.

Open the existing Morpheus API rule and save it if necessary; no new credentials are required. If graph/rule definitions are still cached, restart the site's Apache (`omd restart apache`), which briefly interrupts web access.

## Discover additional services

1. Rescan the API source host. The cluster State service gains online/total member metrics without changing its name.
2. Rescan the VM hosts. Accept the new **Morpheus VM Disk IO** service where the API provides read/write IOPS.
3. Activate pending changes.
4. Existing CPU, RAM and storage services do not need to be deleted or recreated. No history migration is required for this update.

DCD discovery during host creation does not necessarily discover new services on hosts that already exist. Rescan existing VM hosts explicitly or use your existing periodic discovery policy.

## Verify source and VM collection

As the site user, replace the two example host names with your configured names:

```bash
cmk -nv MORPHEUS_SOURCE
cmk -nv MORPHEUS_VM_EXAMPLE
```

The source host collects the API data. VM hosts consume the resulting piggyback data. A successful API request does not prove that every resource is healthy or every statistic is fresh.

## Failure and recovery acceptance

| Test condition | Expected behavior |
| --- | --- |
| Member reports `unclean` and power is `unknown` | Hypervisor State and cluster State are CRIT, not UNKNOWN solely because of that power value. |
| Hypervisor is unavailable | CPU, RAM and hardware services explain unavailability and emit no resource/sensor readings. |
| Surviving hypervisor is healthy | Its fresh CPU/RAM/hardware readings continue normally. |
| Shared datastore remains accessible | It can remain OK; its multipath service does not certify paths on the unavailable host. |
| Only VM RAM is missing | Fresh CPU/storage retain their own values/timestamps. Only RAM uses its last valid sample, if available. |
| Cached sample exceeds 900 seconds | Its metric group is CRIT with default settings and emits no usage reading as current. |
| API returns a valid new sample | The corresponding metric group resumes with the API timestamp. |
| Hypervisor returns online/powered on | Fresh resource and sensor readings resume; stale data still obeys age rules. |

The package does not execute shutdowns, start VMs, enable HA, verify quorum or prove VM failover. Check guest/application reachability separately during failover testing. Planned host shutdowns still produce availability alarms; schedule Checkmk downtime when appropriate.

## Rollback

Keep the previous MKP available. As the site user, enable the previous installed release:

```bash
mkp enable morpheus 1.0.4
cmk-validate-plugins
```

The older collector does not read schema-2 VM cache files. It establishes a new complete baseline when the API provides one. This can temporarily expose missing-statistics alarms. After rollback, review the newly added Disk IO service as vanished; do not remove established CPU/RAM/storage services.

## Validation limits

The supplied source passes local regression tests and construction/evaluation using the public Checkmk 2.4 APIs. There is no running Checkmk monitoring core or live Morpheus appliance in the build environment. Run `cmk-validate-plugins` and the failure/recovery acceptance checks on the exact installed package before publication of 1.0.5.
