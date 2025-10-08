---
id: cis_kubernetes_secrets
policies:
  - env_var_secret
source: CIS Kubernetes Benchmark (v1.24) - Section 5.5.1
citation: https://www.cisecurity.org/benchmark/kubernetes
---
Store sensitive configuration data in Kubernetes Secrets rather than inline environment variables. Replace literal `env[].value` strings that contain credentials with `valueFrom.secretKeyRef` references, reusing existing mounted Secrets when possible. This control limits accidental disclosure in logs, admission webhooks, and version control systems.
