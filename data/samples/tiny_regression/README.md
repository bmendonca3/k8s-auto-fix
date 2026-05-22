# Tiny Regression Pack

This pack is a tiny, hand-curated fixture set for fast CI coverage. It is
intended to exercise detector builtin findings, rule-based proposer and verifier
success and failure paths, scheduler priority scoring, queue enqueue and pick
behavior, and a benign negative case.

The manifests are deliberately small and deterministic. They avoid external
state, generated data, and cluster-specific assumptions.

## Contents

- `manifests/benign-pod.yaml`: safe Pod expected to produce no builtin detector
  rules.
- `manifests/env-secret-pod.yaml`: Pod for a successful `env_var_secret`
  rule-based patch that rewrites a password-like env value to a `secretKeyRef`.
- `manifests/latest-tag-pod.yaml`: Pod for a successful `no_latest_tag`
  rule-based patch and a verifier rejection override that leaves `:latest`
  unresolved.
- `manifests/privileged-pod.yaml`: Pod for a successful `no_privileged`
  rule-based patch.
- `manifests/hostpath-hostport-pod.yaml`: Pod with `hostPath` and `hostPort`
  builtin detector findings, and a successful `no_host_path` patch case.
- `manifests/sys-admin-cap-pod.yaml`: Pod with a `cap-sys-admin` builtin
  detector finding and a successful `drop_cap_sys_admin` patch case.

`cases.json` contains the patch/regression cases. Accepted cases can be reused
as a small scheduler and queue fixture because each case includes `risk`,
`probability`, `expected_time`, and `kev`. Cases may also set
`expected_scheduler_rank` or `expected_queue_next` to make scheduling and queue
ordering regressions fail the pack instead of only being reported.

`detector_expectations.json` maps manifest paths, relative to this pack root, to
the builtin detector rules expected for each manifest.
