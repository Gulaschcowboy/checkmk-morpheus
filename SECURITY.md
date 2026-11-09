# Security reports

Contact **pawel.wladzinski@vayana.pl** privately for suspected vulnerabilities. Do not put credentials or an exploitable issue with sensitive installation details in a public ticket. No response-time or support SLA is promised.

Provide package, Checkmk and Morpheus versions, a minimal sanitized reproduction, expected impact and any suggested mitigation. Never send a live token; revoke credentials if they were exposed.

Use a dedicated read-access API account, TLS verification and appropriately restricted Checkmk access. The package reads monitoring data through HTTPS and does not modify Morpheus objects. Token arguments and debug output still need local access controls; see the README.

Only the documented Checkmk 2.4 release line is currently targeted. Other versions require validation before use.

