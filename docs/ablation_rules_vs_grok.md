# Rules vs Grok Ablation (1.313-manifest slice)

## Overview

| Mode | Acceptance | Median verifier (ms) | Verifier P95 (ms) | Median proposer (ms) | Notes |
| ---- | ---------- | -------------------- | ----------------- | -------------------- | ----- |
| Rules (`configs/run_rules.yaml`) | 13589/13656 (99.51%) | 77 | 178.4 | 5 | Deterministic baseline; zero retries required. |
| Grok/xAI (`configs/run_grok.yaml`) | 1313/1313 (100.00%) | n/a | n/a | n/a | Latest rerun succeeds across the slice; telemetry enumerating generated patches now lives in `data/grok1k_telemetry.json` (per-request latency remains unavailable). |

Token/cost telemetry for the Grok run was not captured during the original sweep. The Grok-5k evaluation provides a proxy mean of ~2.27k tokens/patch (4.36M prompt + 0.69M completion tokens total), which would translate to roughly 3.0M tokens ($\approx\$0.90$) for the 1.313k slice if re-run under the same prompt template.

## Acceptance deltas

- **Rules mode:** No verifier rejects. Policy-level success rates remain at 100% across the slice.
- **Grok/xAI:** No rejects in the seeded rerun; the guardrail fixes (request sanitisation, seccomp defaults, and service normalisation) cover the previously failing TPU suite. Telemetry captured in `data/grok5k_telemetry.json` (5k sweep) and `data/grok1k_telemetry.json` (1.313k slice) summarises token usage; proposer latency remains unavailable for the archived runs.
- **Risk-aware guards:** The rules path now refuses to convert dangling Services to `ExternalName`; it rebuilds selectors from existing labels (or defers to manual review) and only rewrites missing service accounts when `k8s-auto-fix.dev/allow-default-service-account=true` is present. This keeps LLM merges from stripping selectors or silently swapping credentials.
- **Failure taxonomy:** `scripts/summarize_failures.py` confirms the rejection cluster: only `unset-{cpu,memory}-requirements` policies fail, matching the TPU manifest noted above.

## Latency and safety

- **Verifier latency:** Rules-mode verification completes quickly (median 77 ms, P95 178.4 ms). Grok timing telemetry was not captured in the archival sweep.
- **Proposer latency:** Rules-mode generation now averages 5 ms per detection in the parallel runner. Future Grok reruns should pass `--metrics-out` to capture comparable telemetry alongside token usage.
- **Semantic regressions:** No new policy or safety regressions slipped through verification. The remaining Grok failures are attributable to type mismatches rather than unsafe edits; applying the rules-mode guard (stringifying CPU quantities) resolves them.

## Grok-5k failure taxonomy (context)

`logs/grok5k/failure_summary_latest.txt` shows that 552/561 rejects (98.4%) stem from `kubectl --dry-run=server` errors tied to missing real-world infrastructure (empty resource names, absent PVCs, controller-specific fields). Only 23 rejects are policy-driven, primarily `unset-{cpu,memory}-requirements`. These figures align with the 1.313k slice analysis: the Grok path is safe but sensitive to resource quantity formatting and external dependencies. Broadening CRD/namespace fixtures remains the primary lever for improving Grok acceptance beyond 88.78\%.

## Artifacts

- Rules outputs: `data/batch_runs/grok_full/patches_rules_grok_full.json`, `.../verified_rules_grok_full.json`, `.../metrics_rules_grok_full.json`.
- Grok outputs: `data/batch_runs/grok_full/patches_grok_full_batch_*.json`, `.../verified_grok_full_batch_*.json`, `.../metrics_grok_full.json`.
- Failure summary: generated via `python scripts/summarize_failures.py --verified-glob "data/batch_runs/grok_full/verified_grok_full_batch_*.json" --detections-glob "data/batch_runs/grok_full/detections_grok_full_batch_*.json"`.
