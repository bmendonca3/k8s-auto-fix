---
id: cis_kubernetes_requests
policies:
  - set_requests_limits
source: CIS Kubernetes Benchmark (v1.24) - Section 5.7.2
citation: https://www.cisecurity.org/benchmark/kubernetes
---
The CIS Kubernetes Benchmark recommends setting explicit CPU and memory requests and limits for every container. Defining `resources.requests` ensures the scheduler can reserve capacity, while `resources.limits` prevents noisy-neighbor contention. Baseline values such as `requests.cpu: 100m`, `requests.memory: 128Mi`, `limits.cpu: 500m`, and `limits.memory: 256Mi` satisfy the control and match common hardening templates.
