# Cover Letter — IEEE Access Submission

```
Dear IEEE Access Editors,

Please consider our manuscript “Closed-Loop Threat-Guided Auto-Fixing of Kubernetes YAML Security Misconfigurations” for publication in IEEE Access.

The work targets a pressing pain point in cloud-native security: production teams continue to surface Kubernetes misconfigurations without receiving actionable, validated fixes. We contribute k8s-auto-fix, a closed-loop system that detects violations, proposes JSON patches, verifies candidate fixes, and schedules remediation according to risk.

Practical impact:
- Comprehensive benchmarking on 5,000 manifests drawn from the Grok/xAI corpus with 4,439/5,000 (88.78%) acceptance under `kubectl --dry-run=server`.
- Deterministic rules coverage reaching 13,589/13,656 detections (99.51%) and perfect acceptance on the supported 1,264-manifest corpus.
- Operator validation from two SRE/platform rotations (n=20) reporting 4.3/5 satisfaction with zero rollbacks after accepting generated patches.

Evaluation rigor and safety:
- Detector performance meets the promised F1 ≥ 0.85 threshold (1.00 precision/recall/F1 across eight policies) on a labelled hold-out set.
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
