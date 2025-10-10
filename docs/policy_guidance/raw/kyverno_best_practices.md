---
{
  "source": "docs/policy_guidance/static/kyverno_best_practices.md",
  "description": "Kyverno best-practice policies",
  "fetched_at": "2025-10-10T15:41:42.434985Z"
}
---
# Kyverno Best Practices (Extract)

## Drop Capabilities

Kyverno recommends dropping high-risk Linux capabilities from containers. Policies typically enforce:

- Remove dangerous capabilities (`NET_RAW`, `NET_ADMIN`, `SYS_MODULE`, `SYS_PTRACE`, `SYS_CHROOT`, `SYS_ADMIN`).
- Ensure workloads do not add these capabilities back via `capabilities.add`.

## Enforce Read-Only Root Filesystems

Set `securityContext.readOnlyRootFilesystem: true` to limit write access and reduce persistence opportunities.

## Require Non-Root Execution

Configure `securityContext.runAsNonRoot: true` or set explicit non-zero UID/GID values so workloads cannot run as root.

These local excerpts provide stable input for automation; see the upstream Kyverno policy catalog for full context.
