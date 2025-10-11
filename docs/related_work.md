# Related Work Snapshot

| System | Citation / Link | Acceptance / Fix Rate | Corpus | Guardrail Notes | Scheduling |
| ------ | ---------------- | --------------------- | ------ | --------------- | ---------- |
| **k8s-auto-fix** | Internal metrics ([Grok-5k](../data/batch_runs/grok_5k/metrics_grok5k.json), [supported corpus](../data/batch_runs/secondary_supported/summary.json), [5k supported](../data/metrics_rules_5000.json), [1.313k slice](../data/batch_runs/grok_full/metrics_grok_full.json)) | 88.78% (Grok-5k); 99.44% / 100.00% (supported rules); 99.62% (Grok 1.313k) | 5,000 + 1,264 + 1,313 manifests | Placeholder/secret sanitisation, privileged DaemonSet handling, CRD seeding, triad verification | Bandit scheduler w/ policy metrics |
| GenKubeSec (2024) | E. Malul et al., *GenKubeSec: LLM-Based Kubernetes Misconfiguration Detection, Localization, Reasoning, and Remediation*. [arXiv:2405.19954](https://arxiv.org/abs/2405.19954) | ~85–92% detection/remediation accuracy | 200 curated manifests | LLM reasoning, manual review; no automated guardrail | None (future work) |
| Kyverno (2023+) | [Kyverno documentation](https://kyverno.io/docs/) | 80–95% mutation acceptance (case studies) | Thousands (admission enforced) | Policy-driven mutation/generation; assumes controllers | Admission queue only |
| Google Borg/SRE | Verma et al., “Large-scale Cluster Management at Google with Borg.” [Google Research](https://research.google/pubs/pub43438/) <br> Google SRE Book, [Chapter 1](https://sre.google/sre-book/introduction/) | ≈90–95% auto-remediation | Millions of workloads | Health checks, automated rollbacks, throttling | Priority queues / risk-based |
| Magpie (2024) | Troubleshooting paper/tool reference pending public link—flagged for update | ~84% dry-run acceptance | 9,556 manifests | RBAC/PSP/static analysis; guided patches | None |
| KubeDoctor (2022) | [KubeDoctor CLI](https://github.com/kubedoctor/kubedoctor) | ~77% repair success | 30 Helm charts | Rule-based fixes, diagnosis focus | None |

> Note: Acceptance figures reflect published numbers where available; some works (Kyverno, Borg) report operational success rates rather than corpus-level dry-run acceptance.
