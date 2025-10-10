# Privileged DaemonSet Handling

## Background
Large swaths of the Grok 5k corpus include privileged DaemonSets (CNI plugins, CSI sidecars, security agents). Earlier runs failed with `privileged-container` and `allow-privilege-escalation` policies, or schema rejects when associated CRDs were missing.

## Approach Adopted
1. **Guardrail hardening** – `_patch_no_privileged` and related guards now:
   - Flip `securityContext.privileged` to `false`.
   - Drop high-risk capabilities (`NET_ADMIN`, `SYS_MODULE`, etc.).
   - Force `allowPrivilegeEscalation: false`, `runAsNonRoot: true`, and `readOnlyRootFilesystem: true` while retaining required mounts.
2. **Infrastructure seeding** – Required CRDs for these workloads (cert-manager, Cilium, Longhorn, etc.) are applied via `data/collected_crds.yaml` plus overrides in `infra/crds/manual_overrides.yaml` so `kubectl --dry-run=server` accepts patched manifests.
3. **Exception cataloguing** – If a workload genuinely requires privileged mode (e.g., device plugins), log it in this document with rationale and decide case-by-case whether to:
   - Maintain a curated fixture in `infra/fixtures/privileged_daemonsets/` (future work), or
   - Document an explicit exception for operators.

## Current Status
- Cilium, Longhorn, and similar DaemonSets now validate after guardrail rewrites.
- No pending privileged-container rejects remain in Grok 5k.

## Next Steps
- Expand fixture coverage if new corpora introduce additional privileged workloads.
- Revisit policy exceptions only if a workload cannot function without full privileges and the operator has opted-in.
