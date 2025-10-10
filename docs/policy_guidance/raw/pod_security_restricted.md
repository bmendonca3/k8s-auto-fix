---
policies:
  - drop_capabilities
  - read_only_root_fs
  - no_privileged
  - no_allow_privilege_escalation
  - enforce_seccomp
source: "Kubernetes Pod Security Standards (Restricted)"
citation: "https://kubernetes.io/docs/concepts/security/pod-security-standards/"
id: pod_security_restricted
---
# Restricted Pod Security profile

The Restricted profile builds on the Baseline requirements and enforces defence-in-depth controls such as mandatory capability drop and seccomp profiles. Containers must not run with `securityContext.privileged: true` and must disallow privilege escalation while using a read-only root filesystem.
