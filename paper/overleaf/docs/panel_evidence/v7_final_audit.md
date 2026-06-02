# V7 Final Audit

## Progression Decision

- Best supplied rendered PDF before repair: `TCC_2025_12_0666_Major_Revision___k8s_auto_fix-4.pdf` (V4), because it was the most complete coherent supplied PDF: 14 pages and about 10.1k extracted words.
- Supplied `overleaf/main.pdf` behaved like a stale/regressed artifact: 11 pages, about 5.7k extracted words, IEEE Access styling, and unresolved reference markers in the earlier extraction.
- V7 builds from canonical `paper/access.tex` into `build/v7/main.pdf`: 14 pages and 9,834 extracted words.
- V4-to-V7 bag-of-words cosine similarity: 0.945. This indicates V7 preserves the V4/V6 technical lineage while tightening claims and layout.

## Artifact-Backed Metrics

- Full rules+guardrails artifact (`data/metrics_latest.json`): 13,338/13,373 patched items accepted (99.74%); auto-fix rate 0.8486; median patch ops 9; detections 15,718.
- Unified full-corpus row (`data/eval/unified_eval_summary.json`): accepted 13,338, total 13,373, acceptance 0.997383, auto-fix 0.8486.
- Grok-5k row: 4,426/5,000 (88.52%); median patch ops 9.
- Supported rules slice: 1,264/1,264 (100.00%); median patch ops 8.
- Live replay: 1000/1000 records passed dry-run, live apply, and no rollback.
- Risk calibration rows: [{'dataset': 'supported', 'detections': '1278', 'accepted': '1259', 'rejected': '19', 'risk_total': '56990.0', 'risk_resolved': '55935.0', 'risk_residual': '1055.0', 'risk_reduction_ratio': '0.9815', 'delta_r_per_time_unit': '4.4856'}, {'dataset': 'rules5k', 'detections': '5000', 'accepted': '4677', 'rejected': '323', 'risk_total': '242300.0', 'risk_resolved': '227330.0', 'risk_residual': '14970.0', 'risk_reduction_ratio': '0.9382', 'delta_r_per_time_unit': '4.8773'}].

## Panel Issue Disposition

Accepted and fixed:
- V5/main.pdf was stale/regressed; V7 is built from canonical source.
- Fatal build path issues, missing Grok table, and font map paths were fixed in V6 and preserved in V7.
- Stale full-corpus metrics were reverted to checked artifact-backed values: 13,338/13,373, 99.74%, auto-fix 0.8486, median patch ops 9.
- Overclaiming was narrowed: live result is fixture-seeded dry-run/live-apply acceptance; scheduler result is deterministic queue replay.
- Figure 4 was regenerated from `data/baselines/mode_comparison.csv`; old 88.78% visual label is gone.
- Formula definitions now stay together visually; no page split of the No-new-violations label/formula in page-image review.

Rejected or already resolved after DAD verification:
- `kubectl apply --dry-run=server` was already correct in source; the single-dash panel finding was stale.
- Quickstart commands already render as `make detect`, `make propose`, `make verify`; missing-space finding was stale.
- The walkthrough patch uses `add` for `/capabilities/drop`; the panel's remove-nonexistent-path concern did not match current source.
- The b1/b2/b3 bibliography claim was rejected after source inspection; those placeholders had already been removed from the active paper.

## Final Verification

- Build: `tectonic --keep-logs --outdir build/v7 main.tex` succeeded.
- Built PDF: `build/v7/main.pdf`.
- Extracted text: `docs/panel_evidence/pdf_texts/v7_built.txt`.
- Rendered images: `docs/panel_evidence/images/v7_pages/v7_page_01.png` through `v7_page_14.png`.
- Text scan: no `??`, no `Figure ??`, no `Table ??`, no `13,589`, no `88.78`; `---`/`+++` diff markers extract on page 12.
- Log scan: no undefined refs/citations, missing files, missing characters, font-map failures, or LaTeX errors found; only box warnings and the template `algorithmic.sty` UTF-8 warning remain.

## Residual Risks

- The PDF still has standard IEEE two-column underfull/overfull box warnings, including a known small overfull warning in Table 11 notes. Visual spot checks on pages 2, 10, 12, and 13 found no obvious overlap or cut-off text.
- Some artifact paths are cited as public GitHub paths; this audit verified the local checked artifact bundle at `/Users/brianmendonca/Documents/k8s-auto-fix`, not a fresh full rerun of all proposers/verifiers.
