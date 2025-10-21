# Reviewer Response and Revision Summary

This document maps the reviewer’s key blockers and revision requests to concrete changes in this repository and the paper draft.

## Addressed blockers
- Missing auto-remediation baselines
  - Added baselines for Kyverno, Polaris, and MutatingAdmissionPolicy with simulate/real modes
    - `scripts/run_kyverno_baseline.py`
    - `scripts/run_polaris_baseline.py`
    - `scripts/run_mutatingadmission_baseline.py`
  - Unified comparison generator (CSV/MD/TeX): `scripts/compare_baselines.py`
  - LLMSecConfig-style slice (500 manifests, prompts + verifier): `scripts/run_llmsecconfig_slice.py`
- Unsupported Borg acceptance comparison
  - Removed numeric Borg comparisons from README and paper
  - Reframed as “no public acceptance %”; retained SRE principles discussion
  - Files updated: `paper/access.tex`, `overleaf_upload/paper/access.tex`, `docs/literature_comparison.md`, `docs/related_work.md`, `README.md`
- Reproducibility gaps
  - One-command rebuild: `scripts/reproduce_all.sh`
  - Risk throughput evaluation: `scripts/eval_risk_throughput.py`
  - Corpus hashing ledger: `scripts/hash_corpus.py` → `data/corpus_hashes.csv`
  - Artifact map and instructions: `ARTIFACTS.md`, `docs/reproducibility/`

## Strengthened methodology and documentation
- Verifier triad and patch semantics
  - `docs/VERIFIER.md` documents server-side dry-run and patch mode choices (JSON Patch default)
- GitOps/drift control
  - `docs/GITOPS.md` and `scripts/gitops_writeback.py` for PR-based write-back
- Baseline how-to
  - `docs/BASELINES.md` with real/simulated flows and a unified table
- Risk evaluation details
  - `docs/RISK_EVAL.md` with KEV/EPSS as inputs and throughput metrics
- Live-cluster evaluation
  - `docs/LIVE_EVAL.md` and helper `scripts/live_cluster_eval.sh`

## Paper integration (draft updates made)
- Abstract and table edits to remove unsupported Borg numbers
- Related work text reframed accordingly
- Comparison tables remain; a LaTeX snippet for baseline comparisons is generated to include when real runs are executed: `docs/reproducibility/baselines.tex`

## What remains to finalize for submission
- Run baselines in real mode and regenerate tables
  - Kyverno/Polaris on matched corpora; update `data/baselines/*.csv`
  - MAP remains simulation-only until the GA API supports per-container mutations (track upstream CEL enhancements)
  - Generate `docs/reproducibility/baselines.{md,tex}` via `scripts/compare_baselines.py`
- LLMSecConfig slice with API key
  - Execute `scripts/run_llmsecconfig_slice.py --limit 500` and include results in the unified table
- DOI artifact
  - Publish a tagged archive (Zenodo) including corpus hashes, scripts, and environment capture
- Expand live-cluster set
  - Use `scripts/live_cluster_eval.sh` to seed CRDs and expand beyond 200 manifests; add per-policy breakdown and any dry-run/live divergences

## Reproducibility checklist
- `make reproduce-all` populates artifacts under `data/` and `docs/reproducibility/`
- `make paper` rebuilds the PDF after updating LaTeX snippets
- All changed files and scripts are self-contained and versioned here
