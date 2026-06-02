# V11 KEV Wording Cleanup Audit

## Scope

V11 is a light proofreading pass over V10. It only standardizes the scheduler urgency wording so the current evaluated artifact is not described as performing a live CISA KEV mapping.

## Changes

- Replaced current-artifact phrases such as "KEV-derived boost," "KEV flags," and "maps to a CISA advisory" with "configured KEV-style urgency boost," "configured urgency flags," or "urgent handling."
- Renamed the scheduler subsection and pseudocode caption from KEV preemption to urgency preemption.
- Preserved the CISA KEV citation only in the future-work threat-intelligence hook.

## Verification

- Built with `tectonic --keep-logs --outdir build/v11 main.tex`.
- Output PDF: `build/v11/main.pdf`.
- Extracted PDF text: `docs/panel_evidence/pdf_texts/v11_built.txt`.
- Rendered spot-check pages: `docs/panel_evidence/images/v11_pages/v11_page_02.png`, `v11_page_06.png`, and `v11_page_11.png`.
- Text scan found no unresolved `??`, `Figure ??`, `Table ??`, undefined markers, or stale current-artifact phrases such as `KEV-derived`, `maps to a CISA`, `CISA advisory`, `KEV boost`, `KEV flag`, `KEV preemption`, or `KEV-listed`.
- Visual spot checks confirmed the updated Table 1, architecture figure, and scheduler notation page remain readable without obvious clipping.

## Remaining Warnings

- The build still reports the existing layout/font warnings from V10: font-map warnings, the known `algorithmic.sty` UTF-8 warning, underfull boxes, and small overfull boxes in dense tables.
