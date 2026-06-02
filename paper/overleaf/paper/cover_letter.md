# Cover Letter — IEEE Access Submission

```
Dear IEEE Access Editors,

Please consider our manuscript “Closed-Loop Threat-Guided Auto-Fixing of Kubernetes YAML Security Misconfigurations” for publication in IEEE Access.

The work targets a pressing pain point in cloud-native security: production teams continue to surface Kubernetes misconfigurations without receiving actionable, validated fixes. We contribute k8s-auto-fix, a closed-loop system that detects violations, proposes JSON patches, verifies candidate fixes, and schedules remediation according to risk.

Practical impact:
- Comprehensive benchmarking on 5,000 manifests drawn from the Grok/xAI corpus with 4,426/5,000 (88.52%) verifier acceptance under `kubectl --dry-run=server`.
- Deterministic rules plus guardrails automatically fixed 13,338 detections overall on the 15,718-detection full corpus (auto-fix rate 0.8486); among 13,373 attempted patches, 13,338 were accepted (99.74%).
- Fixture-seeded live replay records 1,000/1,000 dry-run/live-apply acceptance with zero rollbacks, while the supported 1,264-manifest rules slice records 100.00% acceptance.

Evaluation rigor and safety:
- Detector smoke tests meet the F1 ≥ 0.85 target on a synthetic nine-policy hold-out set; the manuscript scopes this as wrapper regression coverage, not a broad detector benchmark.
- Guardrails now preserve Service selectors, require explicit opt-in for service-account rewrites, and block unsafe LLM regressions that remove containers or volumes.
- Scheduler claims are grounded in shipped telemetry: the risk-aware bandit cuts top-risk P95 wait time from 102.3 h (FIFO) to 13.0 h (7.9×).

Reproducibility:
- We ship complete artifacts (detections, patches, verifier evidence, queue scores) and scripts under `docs/` and `data/`, together with Grok telemetry files (`data/grok5k_telemetry.json`, `data/grok1k_telemetry.json`) to support cost analysis.
- The repository’s Makefile and documentation provide end-to-end commands for researchers to replay both deterministic and LLM-backed evaluations.

We believe the manuscript aligns with IEEE Access’s emphasis on practical innovation and transparency in evaluation. Thank you for your consideration.

Sincerely,

Brian Mendonca and Vijay K. Madisetti
Georgia Institute of Technology
```
