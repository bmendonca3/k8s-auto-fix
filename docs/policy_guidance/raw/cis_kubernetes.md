---
{
  "source": "docs/policy_guidance/static/cis_kubernetes.md",
  "description": "CIS Kubernetes Benchmark v1.24 (excerpt)",
  "fetched_at": "2025-10-10T15:41:42.434445Z"
}
---
# CIS Kubernetes Benchmark Notes

The following excerpts summarise guidance from the CIS Kubernetes Benchmark (v1.24). Content is provided locally so the guidance refresh script has a stable source.

## Disable Privileged Containers

Privileged containers can bypass kernel isolation. Ensure that workloads do not set `securityContext.privileged: true` and audit custom controllers that request it.

## Drop Dangerous Capabilities

Containers should drop super-user capabilities such as `NET_ADMIN`, `SYS_MODULE`, and `SYS_PTRACE`. Restrict any explicit `capabilities.add` lists to the minimum safe set.

## Enforce Seccomp Profiles

Configure `securityContext.seccompProfile.type: RuntimeDefault` for Pods and containers to reduce kernel attack surface.

## Restrict Host Namespace Access

Disallow sharing the host network, IPC, or PID namespaces using the `hostNetwork`, `hostIPC`, and `hostPID` flags unless explicitly justified.
