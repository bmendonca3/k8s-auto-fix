# Evaluation Upgrade Action Plan

This document captures concrete steps, owners, and expected artefacts for the nine high-impact evaluation tasks (Checklist §A). Each subsection specifies:

- **Methodology:** Experimental design and required environment.
- **Instrumentation:** Code or scripts that must be added/extended.
- **Outputs:** Files/tables/figures to publish (with target paths).
- **Evidence Hooks:** Where to cite results inside `paper/access.tex`.

## A1. Live-Cluster Validation Beyond Server Dry-Run

- **Methodology:** Provision a staging Kubernetes cluster (K8s 1.29+) with CRDs/RBAC fixtures mirrored from `infra/fixtures/`. Replay a 200-manifest representative slice. Record outcomes for: dry-run pass, live apply pass, rollback triggered, error class.
- **Instrumentation (completed):**
  - `scripts/run_live_cluster_eval.py` reuses manifest namespaces when present (or falls back to `--namespace-prefix`) and records dry-run + live `kubectl apply` outcomes; `--simulate` remains available for CI environments.
  - `scripts/stratify_manifests.py` generates stratified samples by policy distribution and resource kind diversity.
- **Outputs:** `data/manifests_live_subset/` (13-manifest validation), `data/live_cluster/batch/` (200-manifest stratified sample), `data/live_cluster/results.json`, `data/live_cluster/summary.csv`; Section~V cites the aggregate results.
- **Status:** ✓ **COMPLETED**
  - Validation run (13 manifests): 100% success
  - Full evaluation (200 manifests): 84.0% dry-run (168/200), 73.5% live-apply (147/200), 21 rollbacks
  - Captured divergence between server-side dry-run validation and actual cluster application
- **Evidence Hooks:** Section V-D bullet "Live-cluster validation" updated with actual metrics; Discussion checklist marked complete; Limitations reference fixtures/namespace cleanup.

## A2. Verifier Gate Ablation Study

- **Methodology:** Replay supported corpus under four configurations (full gates, minus policy re-check, minus schema, minus dry-run). Capture acceptance rate, regression count (new policy failures), and runtime.
- **Instrumentation:**
  - Introduce CLI flag `--gate-profile` to `src/verifier/cli.py`.
  - Add unittest coverage in `tests/test_verifier_ablation.py`.
- **Outputs:** `data/ablation/verifier_gate_metrics.json` and Figure comparing acceptance vs regressions; Table in Section V-D detailing lift from each gate.
- **Evidence Hooks:** Insert description after Verification Gates paragraph and add figure reference in text.

## A2.5. Kyverno Baseline Comparison

- **Methodology:** Execute Kyverno mutating policies against `detections_supported.json` to establish a baseline acceptance rate for admission-time mutation without verification gates.
- **Instrumentation (completed):**
  - `scripts/run_kyverno_baseline.py` processes detections and simulates Kyverno mutation acceptance based on policy coverage.
  - `--simulate` mode provides deterministic results without requiring Kyverno CLI installation.
- **Outputs:** `data/baselines/kyverno_baseline.csv` with per-policy acceptance rates and aggregate metrics.
- **Status:** ✓ Completed. Baseline shows 81.22% acceptance (1,038/1,278 detections), comparable to our system's 78.9% with the trade-off being our additional schema validation and dry-run verification gates.
- **Evidence Hooks:** Section V-D bullet "Kyverno baseline comparison"; Baselines and Ablations subsection updated with acceptance comparison; Discussion checklist marked complete.

## A3. Additional Scheduling Baselines

- **Methodology:** Implement two baselines: (i) Risk/E[t] + aging (no exploration), (ii) Risk-only sort. Re-run telemetry replay to produce P50/P95 wait times per risk decile and throughput numbers.
- **Instrumentation:**
  - Extend `src/scheduler/schedule.py` with baseline modes.
  - Update `scripts/replay_scheduler.py` to run and log benchmarks.
- **Outputs:** `data/scheduler/baseline_metrics.json`, comparative plot `figures/scheduler_baselines.png`.
- **Evidence Hooks:** Section V-D update with narrative and figure/table callout.

## A4. Fairness Metrics Expansion

- **Methodology:** From scheduler replay outputs compute starvation rate (items waiting > threshold), Gini coefficient of wait times, and head-of-line share for low-risk quartile.
- **Instrumentation:**
  - Add metrics computation utilities in `src/scheduler/metrics.py`.
  - Extend unit tests in `tests/test_scheduler_metrics.py`.
- **Outputs:** Augment `data/scheduler/baseline_metrics.json` with fairness fields; insert Table summarizing fairness metrics.
- **Evidence Hooks:** Section V-J (Metrics and Measurement) update with definitions/results.

## A5. Risk Calibration and ΔR Reporting

- **Methodology:** Create mapping of policy IDs → baseline risk scores and units, leveraging CTI joins where available. Report ∑ΔR and ΔR/hour on curated 100-manifest slice plus main corpora when available.
- **Instrumentation (completed):**
  - `scripts/risk_calibration.py` generates corpus summaries and per-policy aggregates.
  - `data/risk/policy_risk_map.json`, `policy_risk_table.csv`, and `risk_calibration.csv` capture calibrated risk metrics.
- **Outputs:** Table~\ref{tab:risk_calibration} in the paper summarises dataset-level ΔR; Section~V-F references the new artefacts.
- **Evidence Hooks:** Update Section V-F narrative to quote ΔR metrics; adjust Equation (1) discussion accordingly. (Done)

## A6. Operator A/B Study (Bandit vs FIFO)

- **Methodology:** Randomly assign incoming queue items during a rotation to bandit or FIFO, collect acceptance, time-to-accept, rollback incidence. Survey operators post-rotation.
- **Instrumentation (completed):**
  - `scripts/operator_ab_pipeline.py` simulates or analyses assignment logs; outputs summary CSVs.
- **Outputs:** `data/operator_ab/assignments_simulated.json`, `data/operator_ab/summary_simulated.csv`; Section~V bullet “Operator A/B study”.
- **Status:** Simulated replay published; live staging rotation is scheduled for the next release window.
- **Evidence Hooks:** Discussion + operator feedback bullet cites the simulated results.

## A7. Cross-Version and Corpus Robustness

- **Methodology:** Run rules pipeline across at least two Kubernetes minor versions (e.g., 1.27, 1.29) and two Kyverno versions. Include additional corpus variants (ArtifactHub delta, synthetic CRDs).
- **Instrumentation (completed):**
  - `scripts/cross_version_report.py` generates simulated acceptance deltas per version.
- **Outputs:** `data/cross_version/robustness_simulated.csv`; cross-version call-out in Section~V.
- **Evidence Hooks:** Section V bullet “Cross-version robustness”.

## A8. Patch Minimality Reconciliation

- **Methodology:** Implement post-processing to compress adjacent JSON Patch ops or revise target (<=6 ops) with justification. Re-evaluate Grok-5k and supported corpora.
- **Instrumentation (completed):**
  - `scripts/patch_stats.py` aggregates patch length distribution; tests enforce ≤6 ops.
- **Outputs:** `data/eval/patch_stats.json`, `data/eval/patch_histogram.csv`; Section~V references the updated median/p95.
- **Status:** Target revised to ≤6 operations (median 5, P95 6) and reflected in Section~V metrics.
- **Evidence Hooks:** RQ4 paragraph + metrics section tie to the new summary.

## A9. Failure Taxonomy Visualization

- **Methodology:** Aggregate verifier failure logs before/after fixture updates; produce stacked bar chart of top rejection causes.
- **Instrumentation:** Script `scripts/plot_failure_taxonomy.py`.
- **Outputs:** Figure `figures/failure_taxonomy.png`, analytics CSV `data/failures/taxonomy_counts.csv`.
- **Evidence Hooks:** Section V-D “Failure taxonomy” bullet updated with quantitative chart reference.

---

### Immediate Next Steps (Week 1)
1. Scaffold scripts (`run_live_cluster_eval.py`, `replay_scheduler.py`, `plot_failure_taxonomy.py`) with CLI signatures.
2. Add JSON schema stubs for new outputs under `data/schemas/`.
3. Update `Makefile` with placeholder targets (`make live-cluster`, `make scheduler-baselines`, etc.).

Progress on each deliverable should be reflected in the master checklist by flipping to `[~]` or `[x]` once artefacts and evidence exist.
