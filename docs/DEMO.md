# Demo Path

This short path is for reviewers who want to understand the project without
setting up a Kubernetes cluster, API keys, or external scanners.

## What This Demonstrates

`k8s-auto-fix` treats remediation as an evidence-backed workflow:

1. detect a Kubernetes misconfiguration
2. propose a candidate JSON Patch
3. verify the candidate through guardrails
4. prioritize accepted fixes
5. package review evidence for an operator

The smoke path below exercises that shape with checked-in fixtures.

## Commands

```bash
make doctor
make tiny-regression
make pipeline-plan
make evidence-manifest-smoke
make review-packet-concise-smoke
```

## Expected Signals

- `make doctor` should report Python dependencies as available. Cluster tools
  such as `kubectl`, `kind`, `kube-linter`, and `kyverno` are optional for this
  local smoke path.
- `make tiny-regression` should report `Status: PASS`.
- `make pipeline-plan` should print the detector -> proposer -> verifier ->
  risk -> scheduler command sequence without running it.
- `make evidence-manifest-smoke` should write an ignored evidence manifest under
  `tmp/`.
- `make review-packet-concise-smoke` should build a bounded operator-facing
  review summary without changing git state.

## Cluster-Backed Validation

For server-side dry-run and live-apply behavior, use a local Kind/dev cluster and
follow [LIVE_EVAL.md](LIVE_EVAL.md). The smoke path intentionally avoids cluster
requirements so reviewers can first validate the repository shape quickly.

## Safety Boundaries

- The proposer is not trusted as the source of truth.
- The verifier is the acceptance boundary.
- The scheduler ranks only accepted patches.
- Operators remain responsible for production approval, rollout timing,
  monitoring, and rollback.
