# Verifier Failure Report

Source: `/Users/brianmendonca/Documents/k8s-auto-fix/data/batch_runs/grok43_20260522_5000/verified_grok43_limit_5000.json`
Total: 5000 | Accepted: 4473 | Rejected: 527

## Rejected By Failing Gates

| Failing gates | Count | Sample ids |
| --- | ---: | --- |
| ok_safety | 512 | 00017, 00173, 00174, 00175, 00176, +507 more |
| ok_policy, ok_safety | 7 | 01494, 01495, 01496, 02680, 04211, +2 more |
| ok_policy | 6 | 00120, 00226, 02065, 02896, 03362, +1 more |
| ok_rescan | 2 | 01328, 03216 |

## Rejected By Policy

| Policy id | Count | Sample ids |
| --- | ---: | --- |
| set_requests_limits | 175 | 00017, 00193, 00194, 00195, 00196, +170 more |
| run_as_non_root | 126 | 00120, 00186, 00187, 00188, 00189, +121 more |
| read_only_root_fs | 122 | 00173, 00174, 00175, 00176, 00177, +117 more |
| drop_capabilities | 39 | 00180, 00181, 00182, 00183, 00184, +34 more |
| no_latest_tag | 34 | 01366, 01367, 02346, 02610, 02611, +29 more |
| no_privileged | 29 | 00185, 00558, 00945, 02006, 02242, +24 more |
| env_var_secret | 2 | 03914, 03915 |

## Top Errors

| Error | Count | Sample ids |
| --- | ---: | --- |
| hostPath '/dev' not in allowlist | 87 | 02004, 02005, 02006, 02007, 02008, +82 more |
| hostPath '/opt/cni/bin' not in allowlist | 67 | 00173, 00174, 00175, 00176, 00177, +62 more |
| hostPath '/lib/modules' not in allowlist | 65 | 00173, 00174, 00175, 00176, 00177, +60 more |
| hostPath '/etc/cni/net.d' not in allowlist | 62 | 00173, 00174, 00175, 00176, 00177, +57 more |
| hostPath '/var/run/cilium' not in allowlist | 62 | 00173, 00174, 00175, 00176, 00177, +57 more |
| hostPath '/var/lib/kubelet/plugins_registry/' not in allowlist | 58 | 02346, 02347, 02348, 02349, 02350, +53 more |
| hostPath '/var/run/docker.sock' not in allowlist | 55 | 00556, 00558, 00561, 00582, 00583, +50 more |
| hostPath '/sys/fs/bpf' not in allowlist | 54 | 00173, 00174, 00175, 00176, 00177, +49 more |
| ... | 107 more group(s) hidden | ... |

## Suggested Next Actions

- `ok_policy=false` (13): Adjust the patch for the target policy; compare patched YAML against the policy-specific verifier check.
- `ok_safety=false` (519): Review patch side effects; remove unsafe hostPath, hostPort, capability, privilege, or rootfs regressions.
- `ok_rescan=false` (2): Run the detector rescan locally and inspect kube-linter or Kyverno output for residual violations.
