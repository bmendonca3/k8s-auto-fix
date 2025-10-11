# Polish TODO Tracker

## In-flight / Upcoming

| Task | Status | Notes |
| ---- | ------ | ----- |
| Consolidate evaluation matrix | Complete | Seed-locked runs captured in `data/eval/unified_eval_summary.json`; README/paper tables refreshed for Grok-5k, supported 1.264k, and 1.313k slices. |
| LLM ablations & safety analysis | Complete | Rules vs Grok ablation captured in `docs/ablation_rules_vs_grok.md` with failure taxonomy, latency/cost notes, and Grok-5k context. |
| Scheduler baselines & sensitivity | Complete | Risk/Et+aging baseline + fairness sweep (`data/metrics_schedule_compare.json`, `data/metrics_schedule_sweep.json`) documented in `docs/scheduler_visualisation.md`. |
| Broaden policy surface & fixtures | Complete | New guards remove ephemeral `clusterName`, clean pod-level `allowPrivilegeEscalation`, clamp resource requests, and fixtures live under `infra/fixtures/`. |
| Operator feedback study | Complete | Structured survey/interview log in `docs/qualitative_feedback.md`; findings referenced in README and paper. |
| Paper/packaging polish | Complete | DOI placeholder set, evaluation table expanded with seeds/latencies, and Makefile/docs updated for fixtures/regression checks. |
| RAG-backed proposer maturation | Complete | GuidanceRetriever + failure cache drive targeted prompt hints; semantic regression checks block destructive Grok patches. |

## Next Improvements

| Task | Status | Notes |
| ---- | ------ | ----- |
| Reproducibility bundle | Complete | `make reproducible-report` regenerates the evaluation tables, Markdown/\\LaTeX snippets, and `data/eval/unified_eval_summary.json`, linking every metric to its source JSON. |
| Grok rerun with telemetry | Complete | Token/latency summaries recomputed from Grok-1.313k and Grok-5k artifacts; results published in the reproducibility bundle and paper. |
| External corpus check | Complete | Supported 5k dataset metrics incorporated into the README/paper tables and reproducibility report. |
| Operator study expansion | Complete | Survey instrument captured in `docs/operator_survey.md` with additional cohorts and aggregated results in `docs/qualitative_feedback.md`. |
| Threat/risk discussion | Complete | Added Threats & Mitigations subsection to the paper and referenced semantic regression safeguards in README/paper. |
| Future-work roadmap | Complete | README Roadmap section now details quarterly milestones for reproducibility, telemetry reruns, external validation, operator surveys, and hardening. |

## Baseline foundations (completed)

| Task | Status | Notes |
| ---- | ------ | ----- |
| Infrastructure seeding for missing CRDs/controllers | Complete | Bulk-seeded 212 CRDs (`data/collected_crds.yaml`) and supplied manual overrides in `infra/crds/manual_overrides.yaml`; `kubectl apply --server-side` now succeeds. |
| CRD/controller fixtures for privileged DaemonSets | Complete | Guardrails + manual CRDs allow Cilium/Longhorn DaemonSets to pass; documented in `docs/privileged_daemonsets.md`. |
| Scheduler visualisation updates | Complete | `docs/scheduler_visualisation.md` captures ranking/telemetry tables (charts optional for paper). |
| Secondary dataset evaluation | Complete | Rules-mode sweep over 200 supported detections (200/200 accepted); see `docs/secondary_dataset_evaluation.md`. |
| Proposer/verifier token & latency instrumentation | Complete | `src/proposer/cli.py --metrics-out` and verifier telemetry capture timings; sample JSON in `tmp/proposer_metrics_secondary.json`. |
| Runtime/acceptance telemetry integration | Complete | `scripts/compute_policy_metrics.py` populates `data/policy_metrics.json`; scheduler consumes via `--policy-metrics`. |
| Guidance indexer automation | Complete | `scripts/refresh_guidance.py` + `docs/policy_guidance/sources.yaml` keep guidance snippets current without 404s. |
| Placeholder/env-var guards | Complete | Sanitisation, secret rewrites, and privileged hardening now cover Grok-5k regressions. |
