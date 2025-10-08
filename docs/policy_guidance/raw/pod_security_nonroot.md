---
id: pod_security_nonroot
policies:
  - run_as_non_root
  - run_as_user
source: Kubernetes Pod Security Standards - Restricted Profile
citation: https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted
---
Restricted pods must run as non-root users. Set `securityContext.runAsNonRoot: true` and provide an explicit numeric `runAsUser` greater than zero (for example, `1000`). Avoid inheriting the root user from the container image. This guidance enforces least privilege and aligns with the Kubernetes Pod Security Restricted profile.
