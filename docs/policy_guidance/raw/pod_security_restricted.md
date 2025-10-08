---
id: pod_security_restricted
policies:
  - no_privileged
  - drop_capabilities
  - enforce_seccomp
source: Kubernetes Pod Security Standards - Restricted Profile
citation: https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted
---
The Restricted profile prohibits privileged workloads and requires pods to run with a locked-down securityContext. Containers must set `privileged: false`, block privilege escalation, and restrict Linux capabilities to the minimal set, typically dropping `NET_RAW`, `SYS_ADMIN`, and similar sensitive flags. Seccomp must use `RuntimeDefault` or a custom profile that is at least as strict. These controls limit the blast radius if the container is compromised and align with the Kubernetes Pod Security Restricted guidance.
