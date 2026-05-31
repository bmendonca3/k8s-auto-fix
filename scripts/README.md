# Script Index

The `scripts/` directory gathers operational helpers for the detector →
proposer → verifier → scheduler pipeline. To keep the flat layout compatible
with existing Makefile targets, files remain in place, but they are organised
here by function so you can quickly locate the right tool.

## Pipeline execution
- `run_grok43_benchmark.py`, `run_grok_batches.py`, `process_batches.py`,
  `merge_batches.py` – manage safe namespaced Grok 4.3 slices and parallel
  proposer/verifier batch runs.
- `run_pipeline.py` – print or run a lightweight detector → proposer →
  verifier → risk → scheduler plan; dry-run, rules mode, no kubectl
  requirement, optional reproducibility manifest output, per-stage status JSON
  with declared input/output hashes and remediation hints, and
  resume-from-status are supported.
- `run_tiny_regression.py` – validate the tiny regression fixture pack across
  builtin detector checks, rule-based proposer/verifier behavior, scheduler
  priority, and temp queue enqueue/pick without external scanner or cluster
  dependencies.
- `run_live_cluster_eval.py`, `live_cluster_eval.sh`, `seed_dry_run_cluster.py`
  – provision fixtures and replay manifests against a live (Kind) cluster.
- `parallel_runner.py`, `monitor_background.py`, `monitor_live_cluster_progress.py`
  – coordination utilities for long-running proposer/verifier jobs.

## Evaluation and reporting
- `compute_policy_metrics.py`, `eval_detector.py`, `eval_risk_throughput.py`,
  `multi_seed_summary.py`, `scheduler_sweep.py`, `compare_schedulers.py` –
  reproduce the metrics referenced in the paper.
- `aggregate_failure_taxonomy.py`, `summarize_failures.py`, `plot_failure_taxonomy.py`,
  `plot_mode_comparison.py`, `plot_operator_ab.py` – failure analysis and visualisations.
- `build_repro_bundle.py`, `reproduce_all.sh`, `generate_corpus_appendix.py`,
  `update_metrics_docs.py` – assemble the reproducibility bundle.
- `build_review_packet.py`, `render_patch_diff.py`, `verifier_report.py`,
  `scheduler_explain.py`, `queue_report.py` – operator-facing review packets,
  concise PR/release summaries, rollout batch annotations, patch diffs,
  verifier triage, scheduler explainability, and queue health reports.
- `build_evidence_manifest.py` – compose selected artifact traceability records
  with producer commands, optional claim labels, pipeline manifest/status stage
  metadata, expected claim-table coverage, and claim-coverage summaries into
  JSON or Markdown. Add `--fail-on-uncovered-claims` with `--claims-table` when
  uncovered expected claims should fail the command.

## Baselines and comparative runs
- `run_kyverno_baseline.py`, `run_kyverno_webhook_baseline.py`,
  `run_polaris_baseline.py`, `run_mutatingadmission_baseline.py`,
  `run_llmsecconfig_slice.py` – external tool comparisons.
- `compare_baselines.py`, `cross_version_report.py`, `risk_calibration.py` –
  summarise baseline outputs and cross-version simulations.

## Maintenance and support
- `build_policy_guidance_index.py`, `refresh_guidance.py`,
  `collect_artifacthub.py`, `sample_the_stack.py` – dataset curation and guidance refresh.
- `artifact_index.py`, `fixtures_report.py`, `seed_fixture_manifests.py`,
  `hash_corpus.py` – inventory and integrity tooling for tracked artifacts,
  fixtures, and manifests.
- `artifact_traceability.py` – emit per-artifact size, SHA-256, producer, and
  category records for reproduction manifests or review packets.
- `doctor.py`, `validate_configs.py`, `kind_up.sh`, `measure_runtime.py`,
  `probe_grok_rate.py` – environment bootstrapping, config validation, and
  sanity checks.
- `check_docs_links.py` – local Markdown link and heading-anchor checks for the
  docs set.
- `check_submission_packet.py` – local TCC packet hygiene checks for gate
  wording, do-not-upload coverage, artifact hashes, dirty-worktree snapshot
  coverage, and clean Overleaf package guidance.
- `scan_secrets.py` – lightweight stdlib scanner for tracked and unignored
  repo text files; reports common token/private-key patterns with redacted
  evidence and skips artifact-heavy sample/generated paths by default.
- `clean_generated.py` – dry-run listing and explicit deletion of ignored,
  allowlisted generated outputs.
- `gitops_writeback.py`, `capture_environment.py`, `operator_ab_pipeline.py` –
  operational workflows around GitOps and operator studies. The writeback
  helper supports `--dry-run` and `--plan-out` so operators can inspect skipped
  patches and file changes before mutating a manifest repository.

If new scripts are added, group them under the section that best reflects their
role or introduce a new heading here so that the directory stays searchable.
