# Script Index

The `scripts/` directory gathers operational helpers for the detector →
proposer → verifier → scheduler pipeline. To keep the flat layout compatible
with existing Makefile targets, files remain in place, but they are organised
here by function so you can quickly locate the right tool.

## Pipeline execution
- `run_grok_batches.py`, `process_batches.py`, `merge_batches.py` – manage
  parallel proposer/verifier batch runs.
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

## Baselines and comparative runs
- `run_kyverno_baseline.py`, `run_kyverno_webhook_baseline.py`,
  `run_polaris_baseline.py`, `run_mutatingadmission_baseline.py`,
  `run_llmsecconfig_slice.py` – external tool comparisons.
- `compare_baselines.py`, `cross_version_report.py`, `risk_calibration.py` –
  summarise baseline outputs and cross-version simulations.

## Maintenance and support
- `build_policy_guidance_index.py`, `refresh_guidance.py`,
  `collect_artifacthub.py`, `sample_the_stack.py` – dataset curation and guidance refresh.
- `fixtures_report.py`, `seed_fixture_manifests.py`, `hash_corpus.py` –
  inventory and integrity tooling for fixtures and manifests.
- `kind_up.sh`, `measure_runtime.py`, `probe_grok_rate.py` – environment bootstrapping and sanity checks.
- `gitops_writeback.py`, `capture_environment.py`, `operator_ab_pipeline.py` –
  operational workflows around GitOps and operator studies.

If new scripts are added, group them under the section that best reflects their
role or introduce a new heading here so that the directory stays searchable.
