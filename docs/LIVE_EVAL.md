# Live-Cluster Evaluation

Goal
- Validate that server-side dry-run aligns with live application and surface divergence causes.

Setup
- Use a local Kind or dev cluster with CRDs installed for common resources (Prometheus, Traefik, etc.).
- Seed RBAC and default NetworkPolicies via `make fixtures`.

Run
```
./scripts/live_cluster_eval.sh
```

Measures
- Dry-run acceptance vs. live-apply acceptance on the same set
- Failure taxonomy (schema errors, API defaults, missing namespaces/CRDs)
- Per-policy family outcomes

Divergence Tracking
- Record cases where `kubectl apply --dry-run=server` succeeds but live-apply fails; categorize by root cause (e.g., missing CRD, RBAC, admission default mismatch)

Notes
- CRD/app versions can impact outcomes; pin versions in the artifact bundle.

