# Infra Fixtures

These fixtures seed common RBAC objects and NetworkPolicies encountered in the Grok-5k corpus. Apply them to the verification cluster before long Grok runs:

```bash
kubectl apply -f infra/fixtures/rbac/placeholder_clusterroles.yaml
kubectl apply -f infra/fixtures/network_policies/default-deny.yaml
```

They're intentionally minimal and non-destructive.

## Manifests

`infra/fixtures/manifests/` contains drift-prone examples (CronJob scanner, Bitnami PostgreSQL StatefulSet) used to reproduce detector/proposer/verifier edge cases. Apply them selectively when debugging a specific failure mode.
