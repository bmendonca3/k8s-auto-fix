# Reproducibility Report

Regenerated via `make reproducible-report`. Each row references the JSON artifacts that back the published metrics.

## Dataset Summary

| Dataset | Mode | Seed | Acceptance | Median proposer (ms) | Median verifier (ms) | Verifier P95 (ms) | Token usage (prompt / completion) | Artifacts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Supported 1.264k | rules | 1337 | 1264/1264 (100.00%) | 29.00 | 242.00 | 517.85 | n/a | `data/batch_runs/secondary_supported/metrics_rules.json`<br/>`data/batch_runs/secondary_supported/patches_rules.json`<br/>`data/batch_runs/secondary_supported/verified_rules.json` |
| Supported 5k | rules | 1337 | 4677/5000 (93.54%) | n/a | n/a | n/a | n/a | `data/metrics_rules_5000.json`<br/>`data/patches_rules_5000.json`<br/>`data/verified_rules_5000.json` |
| Manifest 1.313k | rules | 1337 | 13589/13656 (99.51%) | n/a | n/a | n/a | n/a | `data/metrics_rules_full.json`<br/>`data/patches_rules_full.json`<br/>`data/verified_rules_full.json` |
| Manifest 1.313k | grok | 1337 | 1313/1313 (100.00%) | n/a | n/a | n/a | n/a | `data/batch_runs/grok_full/metrics_grok_full.json`<br/>`data/batch_runs/grok_full/patches_grok_full.json`<br/>`data/batch_runs/grok_full/verified_grok_full.json` |
| Grok-5k | grok | 1337 | 4426/5000 (88.52%) | n/a | n/a | n/a | 4,376,199 / 689,779 | `data/batch_runs/grok_5k/metrics_grok5k.json`<br/>`data/batch_runs/grok_5k/patches_grok5k.json`<br/>`data/batch_runs/grok_5k/verified_grok5k.json` |

## Artifact Map

- `data/eval/unified_eval_summary.json` – machine-readable summary consumed by the README and paper tables.
- `docs/reproducibility/tables.tex` – LaTeX snippet mirroring Table~\ref{tab:eval_summary}.
- `docs/reproducibility/report.md` (this file) – human-readable summary linking metrics to artifacts.
