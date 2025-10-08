---
id: pod_security_baseline_network
policies:
  - no_host_path
  - no_host_ports
source: Kubernetes Pod Security Standards - Baseline Profile
citation: https://kubernetes.io/docs/concepts/security/pod-security-standards/#baseline
---
The Baseline profile limits host access to reduce privilege escalation paths. Avoid `hostPath` volumes unless combined with a read-only root filesystem and narrow subPath rules. Services should prefer cluster networking; remove `hostPort` mappings so the kubelet cannot bind privileged ports on the node. Where host networking is unavoidable, document the exception and add compensating controls.
