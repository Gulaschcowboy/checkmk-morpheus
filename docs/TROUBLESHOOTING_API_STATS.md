# Incomplete or stale VM statistics

The provider can return a fresh `server.stats.ts` with capacity, CPU Ready and running state but without CPU usage, used RAM, used storage or IOPS. A current guest-agent heartbeat does not prove that the resource sample is complete. The detail endpoint can return the same partial sample as the listing.

The collector therefore retains the last valid metric group and its original timestamp. WARN/CRIT describe that measurement age. A new request timestamp or a successful Check_MK piggyback check cannot make the old resource reading fresh. Untimestamped root stats and their zeros are not used to fabricate missing current values.

## Observe a full update cycle

Keep both Python files from `tools/` in the same directory. Run the sampler interactively with the API token prompted:

```bash
python3 tools/sample_vm_stats.py \
  --url https://morpheus.example.com \
  --vm-id 3 \
  --samples 12 --interval 5 \
  --output ~/tmp/morpheus_vm_samples.txt
```

If the certificate is deliberately untrusted/self-signed, add `--insecure`. The default run samples approximately one minute. It uses only GET and does not read/reset Checkmk caches. Review private resource names before sharing its TXT/JSON output; the token is not written.

Compare each API response's own timestamp and field presence. If complete samples appear between incomplete ones, this documents provider update-phase behavior. If no complete samples appear, it documents a resource-telemetry gap despite possible agent connectivity. A single partial response cannot establish the cause or duration of a multi-minute gap.

If API samples are complete/fresh but the corresponding Checkmk metric group remains stale, collect a sanitized current piggyback sample and investigate the collector's selection, capacity fingerprint and cache. If the API itself is persistently incomplete, retain the sample report plus agent/platform versions for investigation of the Morpheus provider/agent pipeline.

Do not reset cached timestamps, replace missing values by untimestamped aggregate zeros or raise critical ages solely to conceal a telemetry gap.

## Storage and NIC limitations

`volumes[].usedStorage` can describe disk backing/allocation and has no independently observed measurement timestamp. It does not establish the free space of C:, D: or guest mount points. For full-filesystem alerts use guest OS filesystem monitoring.

Interface `active` is an inventory/configuration field. Virtual-switch uplinks expose NIC mappings, sync status and last configuration sync, not verified physical carrier/LACP/counter measurements. For those alerts obtain host/switch operational counters with explicit units and timestamps.

For HVM layout 1.3/2.0 agent quorum evidence, the supplied audit tool also supports local use on each hypervisor:

```bash
python3 tools/morpheus_api_audit.py --local-quorum --insecure \
  --output ~/tmp/morpheus_quorum.txt
```

This local mode queries only `https://localhost:7443/quorum` and sends no manager token. A quorum implementation still requires response validation from the installed layout/version. Corosync's quorate flag alone is not a substitute for the Morpheus agent quorum state.
