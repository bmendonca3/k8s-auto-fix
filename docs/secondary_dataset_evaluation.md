# Secondary Dataset Evaluation

- **Source**: First 200 detections from `data/detections_supported.json` (mix of curated Helm charts).
- **Run mode**: `rules` proposer (`configs/run_rules.yaml`), verifier with live kubectl dry-run.
- **Result**: 200 / 200 accepted (100%).
- **Top accepted policies**:
  - `set_requests_limits`: 91
  - `read_only_root_fs`: 35
  - `dangling_service`: 22
  - `non_existent_service_account`: 21
  - `run_as_non_root`: 15

Artifacts:
- Patches: `tmp/patches_secondary.json`
- Verification log: `tmp/verified_secondary.json`

## Extended Sweep (token-instrumented)

- **Scope**: 1,264 detections from `data/detections_supported.json` aligned with rule coverage.
- **Result**: 1,217 / 1,264 accepted (96.28%). Remaining rejects stem from real-cluster gaps (forbidden pods, missing DaemonSet controllers, etc.).
- **Telemetry artifacts**:
  - Proposer metrics: `tmp/proposer_metrics_supported.json`
  - Verifier results: `tmp/verified_supported.json`
  - Scheduler output (with policy metrics): `tmp/schedule_supported.json`
- **Policy metrics**: `data/policy_metrics.json` now reflects measured acceptance probabilities and expected runtimes for scheduler consumption.

Next steps:
- Promote these runs into `data/batch_runs/secondary_*` for archival.
- Feed qualitative operator notes into `docs/qualitative_feedback.md`.
