# Verifier Failure Report

Source: `data/batch_runs/grok43_20260521_200/verified_grok43_limit_200.json`
Total: 200 | Accepted: 171 | Rejected: 29

## Rejected By Failing Gates

| Failing gates | Count | Sample ids |
| --- | ---: | --- |
| ok_safety | 28 | 00173, 00174, 00175, 00176, 00177, +23 more |
| ok_policy | 1 | 00120 |

## Rejected By Policy

| Policy id | Count | Sample ids |
| --- | ---: | --- |
| run_as_non_root | 8 | 00120, 00186, 00187, 00188, 00189, +3 more |
| set_requests_limits | 8 | 00193, 00194, 00195, 00196, 00197, +3 more |
| read_only_root_fs | 7 | 00173, 00174, 00175, 00176, 00177, +2 more |
| drop_capabilities | 5 | 00180, 00181, 00182, 00183, 00184 |
| no_privileged | 1 | 00185 |

## Top Errors

| Error | Count | Sample ids |
| --- | ---: | --- |
| hostPath '/run/cilium/cgroupv2' not in allowlist | 28 | 00173, 00174, 00175, 00176, 00177, +23 more |
| hostPath '/var/run/cilium' not in allowlist | 28 | 00173, 00174, 00175, 00176, 00177, +23 more |
| hostPath '/var/run/netns' not in allowlist | 28 | 00173, 00174, 00175, 00176, 00177, +23 more |
| hostPath '/etc/cni/net.d' not in allowlist | 26 | 00173, 00174, 00175, 00176, 00177, +21 more |
| hostPath '/lib/modules' not in allowlist | 26 | 00173, 00174, 00175, 00176, 00177, +21 more |
| hostPath '/opt/cni/bin' not in allowlist | 26 | 00173, 00174, 00175, 00176, 00177, +21 more |
| hostPath '/proc' not in allowlist | 26 | 00173, 00174, 00175, 00176, 00177, +21 more |
| hostPath '/proc/sys/kernel' not in allowlist | 26 | 00173, 00174, 00175, 00176, 00177, +21 more |
| ... | 5 more group(s) hidden | ... |

## Suggested Next Actions

- `ok_policy=false` (1): Adjust the patch for the target policy; compare patched YAML against the policy-specific verifier check.
- `ok_safety=false` (28): Review patch side effects; remove unsafe hostPath, hostPort, capability, privilege, or rootfs regressions.
