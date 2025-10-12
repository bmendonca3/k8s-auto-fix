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

## Extended Sweep (updated, seed-locked)

- **Scope**: 1,264 detections from `data/batch_runs/secondary_supported/detections.json` aligned with rule coverage.
- **Result**: 1,264 / 1,264 accepted (100.00%) after normalising `sensitive-host-mounts`/`docker-sock` to the `no_host_path` guard.
- **Telemetry artifacts**:
  - Proposer output: `data/batch_runs/secondary_supported/patches_rules.json`
  - Verifier results: `data/batch_runs/secondary_supported/verified_rules.json`
  - Metrics roll-up: `data/batch_runs/secondary_supported/metrics_rules.json`
  - Historical proposer/verifier telemetry (pre-seed run): `proposer_metrics.json`, `verified.json`
- **Policy metrics**: `data/policy_metrics.json` now reflects the latest acceptance probabilities and expected runtimes for scheduler consumption.

## Extended 5k Sweep

- **Scope**: 5,000 curated manifests (`data/detections_supported_5000.json`) processed in rules mode.
- **Result**: 4,677 / 5,000 accepted (93.54%). Residual rejections underline namespace/RBAC assumptions plus workload-specific controllers that remain out of scope; the failure set is tracked in `logs/grok5k/failure_summary_latest.txt`.
- **Artifacts**:
  - Patches: `data/patches_rules_5000.json`
  - Verifier output: `data/verified_rules_5000.json`
  - Metrics: `data/metrics_rules_5000.json`
- **Notes**: This dataset feeds the reproducibility bundle and provides the “external” data point referenced in the paper table. Historical latency telemetry was not captured during the archived sweep; only acceptance figures are published.

Next steps:
- Promote these runs into `data/batch_runs/secondary_*` for archival.
- Feed qualitative operator notes into `docs/qualitative_feedback.md`.
