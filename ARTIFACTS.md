# Artifacts and Reproducibility

This repository includes scripts and manifests to regenerate all tables and figures referenced in the paper.

One-command reproduction
- `scripts/reproduce_all.sh` rebuilds the reproducibility bundle and baseline summaries in simulation mode. It also runs the LLMSecConfig slice if `OPENAI_API_KEY` is set.

Key outputs
- `docs/reproducibility/report.md` – human-readable summary of datasets and metrics
- `docs/reproducibility/tables.tex` – LaTeX table snippet
- `docs/reproducibility/baselines.md` / `baselines.tex` – baseline comparison tables
- `data/eval/unified_eval_summary.json` – machine-readable evaluation summary
- `data/baselines/*.csv` – baselines (Kyverno, Polaris, MAP) and LLMSecConfig slice; unified summary in `data/baselines/baseline_summary.csv`
- `data/metrics_risk_throughput.json` – risk-closure throughput with sensitivity analysis
- `data/corpus_hashes.csv` / `data/corpus_manifest.txt` – corpus ledger with SHA-256 per file

Live-cluster evaluation
- `scripts/live_cluster_eval.sh` installs common CRDs and executes detect→propose→verify with server-side dry-run enabled. Requires a working `kubectl` context.

DOI and artifact archive
- For IEEE Access, publish a tagged archive (e.g., Zenodo) containing:
  - Corpus manifests and SHA-256 listing
  - Exact scripts under `scripts/` used to regenerate every number
  - Model prompts and latency CSVs for LLM-backed runs
  - Environment versions (kubectl, Kind, kube-linter, Python deps)
