# V10 Final TCC Cleanup Audit

## Scope

V10 is a submission-polish pass over V9, not a rewrite. It preserves the TCC-oriented structure while applying the final reviewer-risk cleanup from the main(3)/V9 reevaluation.

## Changes

- Shortened the Table 1 evaluation-corpus cell and pushed detailed rates into the evaluation summary table.
- Removed CVE/EPSS from the index terms and kept threat-intelligence hooks framed as future enrichment.
- Replaced broad safety wording with verifier-bound language such as verification gates, verifier checks, no-new-violation gates, and policy/schema/API admissibility.
- Reduced Grok/xAI branding in manuscript prose; remaining provider-specific strings are limited to exact artifact paths, the reproducibility configuration table, and pricing citation context.
- Reworded the hostPath/emptyDir escape example to describe incomplete remediation under the verifier re-check instead of implying a new unrelated policy violation.
- Renamed the rendered failure table caption to "API-backed LLM" rather than "Grok/xAI."

## Verification

- Built with `tectonic --keep-logs --outdir build/v10 main.tex`.
- Output PDF: `build/v10/main.pdf`.
- Rendered page images: `docs/panel_evidence/images/v10_pages/v10_page_01.png` through `v10_page_15.png`.
- Contact sheet: `docs/panel_evidence/images/v10_contact_sheet.png`.
- Extracted PDF text: `docs/panel_evidence/pdf_texts/v10_built.txt`.
- PDF text scan found no unresolved `??`, `Figure ??`, `Table ??`, undefined markers, or targeted reviewer-risk phrases (`Grok/xAI`, `CVE, EPSS`, `LLM+RAG`, `Operator A/B study`, `Why ours`, broad standalone `safe/safety`).
- Visual review of the contact sheet plus pages 2, 10, and 12 found no obvious overlap, clipping, corrupted images, or unrelated screenshot artifacts.

## Remaining Warnings

- The build still reports layout warnings: one font-map warning, the known `algorithmic.sty` UTF-8 warning, underfull boxes, and small overfull boxes in dense tables.
- The overfull boxes inspected visually did not produce cut-off rendered content in the V10 page images.
