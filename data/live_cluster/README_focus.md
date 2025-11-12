# Live Cluster Focus Bundle Notes

* 2025-10-28 17:02Z: Initial focus rerun (44 manifests)  22/44 success. Remaining failures due to templated fields, missing CRDs, immutable resources.
* 2025-10-28 17:16Z: Added bundled CRDs + further sanitisation  35/44 success.
* 2025-10-28 17:26Z: Completed manifest hygiene (selector fixes, quantity normalization, placeholder substitution)  44/44 success (`data/live_cluster/summary_focus.csv`).
* 2025-10-28 22:12Z: Sanitised focus manifests copied back into `batch_1k_clean/`; full 1k sweep now passes 1000/1000 with zero live failures (`data/live_cluster/summary_1k.csv`).

Artifacts:
- Manifests: `data/live_cluster/batch_focus/`
- Results (focus): `data/live_cluster/results_focus.json`
- Summary (focus): `data/live_cluster/summary_focus.csv`
- Full run results: `data/live_cluster/results_1k.json`
- Full run summary: `data/live_cluster/summary_1k.csv`
