# Rules vs Grok Ablation (1.313-manifest slice)

## Overview

| Mode | Acceptance | Median verifier (ms) | Verifier P95 (ms) | Median proposer (ms) | Notes |
| ---- | ---------- | -------------------- | ----------------- | -------------------- | ----- |
| Rules (`configs/run_rules.yaml`) | 1313/1313 (100.00%) | 85 | 136 | 400 | Deterministic baseline; zero retries required. |
| Grok/xAI (`configs/run_grok.yaml`) | 1308/1313 (99.62%) | 202 | 659 | n/a | Five rejects confined to TPU jobs; proposer runtime was not recorded in the archived run. |

Token/cost telemetry for the Grok run was not captured during the original sweep. The Grok-5k evaluation provides a proxy mean of ~2.27k tokens/patch (4.38M prompt + 0.69M completion tokens total), which would translate to roughly 3.0M tokens ($\approx\$0.90$) for the 1.313k slice if re-run under the same prompt template.

## Acceptance deltas

- **Rules mode:** No verifier rejects. Policy-level success rates remain at 100% across the slice.
- **Grok/xAI:** 5 rejects (0.4%) triggered the `requests.cpu missing or empty` guard. All five map to `data/manifests/the_stack_sample/sample_0106.yaml` (TPU training job). The Grok patch introduces `requests.cpu: 2` (integer) on container `train`, which fails the string-or-quantity requirement enforced by the rule guard.
- **Failure taxonomy:** `scripts/summarize_failures.py` confirms the rejection cluster: only `unset-{cpu,memory}-requirements` policies fail, matching the TPU manifest noted above.

## Latency and safety

- **Verifier latency:** Grok patches incur a 2.4× verifier median (202 ms vs 85 ms) and 4.8× P95 (659 ms vs 136 ms) relative to rules. The larger JSON patches (extra guardrail ops) drive the difference.
- **Proposer latency:** Not recorded for the Grok run. Future reruns should pass `--metrics-out` to capture end-to-end proposer timing alongside token usage.
- **Semantic regressions:** No new policy or safety regressions slipped through verification. The remaining Grok failures are attributable to type mismatches rather than unsafe edits; applying the rules-mode guard (stringifying CPU quantities) resolves them.

## Grok-5k failure taxonomy (context)

`logs/grok5k/failure_summary_latest.txt` shows that 552/561 rejects (98.4%) stem from `kubectl --dry-run=server` errors tied to missing real-world infrastructure (empty resource names, absent PVCs, controller-specific fields). Only 23 rejects are policy-driven, primarily `unset-{cpu,memory}-requirements`. These figures align with the 1.313k slice analysis: the Grok path is safe but sensitive to resource quantity formatting and external dependencies. Broadening CRD/namespace fixtures remains the primary lever for improving Grok acceptance beyond 88.78\%.

## Artifacts

- Rules outputs: `data/batch_runs/grok_full/patches_rules_grok_full.json`, `.../verified_rules_grok_full.json`, `.../metrics_rules_grok_full.json`.
- Grok outputs: `data/batch_runs/grok_full/patches_grok_full_batch_*.json`, `.../verified_grok_full_batch_*.json`, `.../metrics_grok_full.json`.
- Failure summary: generated via `python scripts/summarize_failures.py --verified-glob "data/batch_runs/grok_full/verified_grok_full_batch_*.json" --detections-glob "data/batch_runs/grok_full/detections_grok_full_batch_*.json"`.
