# Artifact Map

This file maps each manuscript table, figure, and headline claim to the
checked-in artifact and command that regenerates or audits it. Paths are
relative to the repository root packaged with the manuscript.

## Quickstart

```bash
make reproducible-report
make metrics-consistency
make docs-link-check
.venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'
```

The default reproducible path uses recorded JSON/CSV artifacts and deterministic
rules-mode runs. Grok/xAI replay artifacts are checked in; rerunning the live API
path requires external credentials and budget.

## Command Scope

| Command | Regenerates or checks | Does not rerun |
|---|---|---|
| `make reproducible-report` | `data/eval/unified_eval_summary.json`, `docs/reproducibility/report.md`, and `docs/reproducibility/tables.tex` from checked-in JSON/CSV artifacts | live-cluster replay, cross-cluster replay, Grok/xAI API sweeps, or PNG figure rendering |
| `make metrics-consistency` | paper-facing metric consistency checks against canonical checked-in artifacts | source experiments or external API calls |
| `make docs-link-check` | repository documentation link validation | evaluation metrics or figures |
| `.venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'` | verifier unit-test checks for policy/schema/safety behavior | live `kubectl` replay or workload semantic testing |

## Headline Claims

| Claim | Primary artifact | Regeneration / check |
|---|---|---|
| Supported rules corpus accepts `1264/1264` manifests | `data/batch_runs/secondary_supported/metrics_rules.json` | `make reproducible-report` |
| Archived rules-5k verifier-record snapshot accepts `4677/5000` manifests | `data/metrics_rules_5000.json` | Snapshot-only context for Figure 4 and ablation discussion; not used as a current acceptance result or fresh verifier rerun |
| Full rules+guardrails run accepts `13589/13656` patched items (`99.51%`); auto-fix `0.8646` over `15718` detections; median patch size `8` | `data/metrics_rules_full.json`, `data/metrics_latest.json`, current raw `.json.gz` inputs | `make metrics-consistency` |
| Grok/xAI 1.313k slice accepts `1313/1313` manifests | `data/batch_runs/grok_full/metrics_grok_full.json` | `make reproducible-report` |
| Grok/xAI 5k sweep accepts `4426/5000` manifests | canonical: `data/batch_runs/grok_5k/metrics_grok5k.json`; mirrored output: `data/outputs/batch_runs/grok_5k/metrics_grok5k.json` | `make metrics-consistency` |
| Live replay applies `1000/1000` accepted manifests with zero rollback | `data/live_cluster/results_1k.json`, `data/live_cluster/summary_1k.csv` | `scripts/run_live_cluster_eval.py` |
| Bandit top-risk P95 wait is `13.0 h` vs FIFO `102.3 h` | `data/metrics_schedule_compare.json` | `make metrics-consistency` |
| Long replay high-risk starvation falls from `93.4%` to `19.1%` | `data/scheduler/fairness_metrics.json` | `make metrics-consistency` |
| Acceptance-boundary matrix shows 312 rules-mode historical snapshot rejects and 551 Grok/xAI policy-only snapshot rejects under weaker boundaries | `data/ablation/acceptance_boundary_matrix.json`, `data/ablation/acceptance_boundary_matrix.csv` | `python3 scripts/build_acceptance_boundary_matrix.py --dataset rules_5k:data/verified_rules_5000.json --dataset grok_5k:data/batch_runs/grok_5k/verified_grok5k.json` |
| Verifier pilot ablation catches four policy escapes | `data/ablation/verifier_gate_metrics.json` | `make metrics-consistency` |

## Manuscript Evidence Map

| Manuscript item | Backing artifact(s) |
|---|---|
| Comparison of remediation systems (`tab:comparison`) | `docs/literature_comparison.md`, `docs/related_work.md`, cited references |
| Per-policy baseline slice (`tab:baselines`) | `docs/reproducibility/baselines.tex`, `data/baselines/baseline_summary.csv` |
| Detector wrapper hold-out (`tab:detector_performance`) | `scripts/eval_detector.py`, `data/eval/holdout_labels.json`, `data/eval/holdout_detections.json`, `data/eval/detector_metrics.json` |
| ArtifactHub structural-label agreement prose | `scripts/label_artifacthub_detector_structural.py`, `scripts/eval_detector.py`, `scripts/summarize_artifacthub_detector_errors.py`, `data/eval/artifacthub_sample_labels_structural.json`, `data/eval/artifacthub_sample_detections.json`, `data/eval/artifacthub_sample_metrics.json`, `data/eval/artifacthub_detector_error_summary.json`, `data/eval/artifacthub_sample_labeling_protocol.md` |
| Pipeline evidence (`tab:evidence`) | source paths under `src/`, generated artifacts under `data/` |
| Execution environment (`tab:environment`) | `data/repro/environment.json` |
| Grok/xAI configuration (`tab:llm_config`) | `configs/run.yaml`, `configs/run_grok.yaml` |
| Grok failure taxonomy (`tab:failure_taxonomy`) | `paper/grok_failures_table.tex`, `data/grok_failure_analysis.csv` |
| Metric denominators (`tab:denominators`) | `data/eval/unified_eval_summary.json`, `data/metrics_rules_full.json` |
| Verifier failure taxonomy (`tab:failure_taxonomy`) | `data/failures/taxonomy_counts.csv`, `scripts/aggregate_failure_taxonomy.py` |
| Risk calibration (`tab:risk_calibration`) | `data/risk/risk_calibration.csv` |
| Acceptance summary; latency reported only for regenerated rows (`tab:eval_summary`) | `data/eval/unified_eval_summary.json`, `docs/reproducibility/tables.tex` |
| Artifact index (`tab:artifact_index`) | this file plus the concrete paths in `paper/access.tex` |
| Cilium patch example (`tab:cilium_patch`) | `docs/privileged_daemonsets.md` |
| Cross-cluster replay (`tab:cross_cluster_replication`) | `data/cross_cluster/{eks,gke,aks}/summary.csv`, `data/cross_cluster/{eks,gke,aks}/results.json` |
| Acceptance-boundary matrix (`tab:verifier_ablation`) | `paper/acceptance_boundary_matrix.tex`, `data/ablation/acceptance_boundary_matrix.{json,csv}`, `scripts/build_acceptance_boundary_matrix.py` |
| Evidence status (`tab:evidence_status`) | downstream manuscript mirror under `paper/overleaf/`, `docs/operator_survey.md` |

## Manuscript Figures

| Manuscript item | Backing artifact(s) |
|---|---|
| Figure 1, architecture | `paper/access.tex` picture environment |
| Figure 2, top-50 queue waits | `figures/fairness_waits.png`, `data/metrics_schedule_compare.json`, `scripts/plot_scheduler_waits.py`; matched 1,259-item historical supported-queue replay with uniform 10-minute fallback service time and zero initial ages/exploration inputs |
| Figure 3, admission vs post-hoc | `figures/admission_vs_posthoc.png`, `data/baselines/kyverno_baseline.csv`, `scripts/create_comparison_chart.py` |
| Figure 4, matched mode comparison | `figures/mode_comparison.png`, downstream `paper/overleaf/figures/mode_comparison.png`, `data/baselines/mode_comparison.csv`, `data/metrics_rules_5000.json`, `data/batch_runs/grok_5k/metrics_grok5k.json`; byte-identical 5,000-record detection input, archival verifier snapshots rather than current reruns; `scripts/plot_mode_comparison.py` |

## Reproducibility Outputs

| Output | Purpose |
|---|---|
| `data/eval/unified_eval_summary.json` | Machine-readable summary consumed by the paper and docs |
| `docs/reproducibility/report.md` | Human-readable summary with source artifact paths |
| `docs/reproducibility/tables.tex` | Generated LaTeX table used as a paper-facing consistency target |
| `data/eval/table4_counts.csv` and `data/eval/table4_with_ci.csv` | Acceptance counts and Wilson confidence intervals |
| `data/eval/significance_tests.json` | Acceptance and latency significance tests |

## Notes for Artifact Evaluators

- The default paper claims can be audited without external API calls.
- `make reproducible-report` regenerates the summary report artifacts listed
  above; it is not a promise to rerun every live, cross-cluster, LLM, or figure
  generation step.
- Optional Grok/xAI regeneration requires configured credentials; the checked-in
  telemetry lets reviewers recompute acceptance, token counts, and cost using
  the current public xAI pricing page.
- Live-cluster and cross-cluster results are fixture-seeded replay outputs; they
  establish API-admission behavior, not full workload semantic equivalence.
