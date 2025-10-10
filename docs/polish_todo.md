# Polish TODO Tracker

## In-flight / Upcoming

| Task | Status | Notes |
| ---- | ------ | ----- |
| Consolidate evaluation matrix | Pending | Rerun rules + Reasoning API sweeps with fixed seeds, publish a single acceptance/latency table, reconcile Grok-5k vs 1.3k/1.313 claims. |
| LLM ablations & safety analysis | Pending | Compare deterministic vs API-backed proposer on identical corpora, capture failure taxonomy deltas, check semantic regressions, document token/cost trade-offs. |
| Scheduler baselines & sensitivity | Pending | Add R/Et+aging and risk-only comparators, sweep exploration/aging coefficients, report fairness beyond mean-rank. |
| Broaden policy surface & fixtures | In progress | Extend guards/fixtures for additional Pod Security profiles, RBAC/network policies, and close infra gaps flagged in `logs/grok5k/failure_summary_latest.txt`. |
| Operator feedback study | In progress | Convert notes in `docs/qualitative_feedback.md` into structured interviews/metrics (rollback incidence, time-to-accept), feed back into limitations. |
| Paper/packaging polish | Pending | Remove draft artefacts (TBD DOI, mixed timestamps), add consolidated experiment appendix, ensure repro scripts mirror latest runs. |
| RAG-backed proposer maturation | Planned | Implement retrieval loop, cache failures, add semantic regression checks before advertising Reasoning API mode as default. |

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
