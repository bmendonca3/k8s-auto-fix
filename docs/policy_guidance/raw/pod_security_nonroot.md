---
policies:
  - run_as_non_root
  - run_as_user
source: "Kubernetes Pod Security Standards (Restricted)"
citation: "https://kubernetes.io/docs/concepts/security/pod-security-standards/"
id: pod_security_nonroot
---
# Non-root requirement

Ensure containers are not running as the root user. Configure `spec.template.spec.securityContext.runAsNonRoot: true` or set a non-zero `runAsUser`/`runAsGroup` value. Pod Security Restricted level requires non-root containers and forbid privilege escalation via UID 0.
