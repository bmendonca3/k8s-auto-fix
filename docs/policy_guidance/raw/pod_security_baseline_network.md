---
policies:
  - no_host_network
  - no_host_pid
  - no_host_ipc
  - no_host_ports
source: "Kubernetes Pod Security Standards (Baseline)"
citation: "https://kubernetes.io/docs/concepts/security/pod-security-standards/"
id: pod_security_baseline_network
---
# Baseline network policy

Avoid using host namespaces and host networking in workloads that do not require it. The Baseline profile forbids hostNetwork/hostPID/hostIPC by default.
