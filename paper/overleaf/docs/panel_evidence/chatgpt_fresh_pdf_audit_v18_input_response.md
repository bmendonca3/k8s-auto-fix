# Fresh ChatGPT PDF Audit Feeding V18

The fresh bounded ChatGPT audit was run in a new chat against the latest pushed
V17 PDF. The browser tab became heavy during the response, and the user provided
the final response text from that run.

## Fresh Audit Verdict

Final verdict: `SUBMIT AFTER LIGHT PROOFREAD`.

Blockers: None. The reviewer reported no unresolved references, missing/corrupt
figures, cut-off tables, or metric contradiction requiring hold.

## Non-blocking Polish Items Reported

1. Page 4: the "Reproduction entry points" boxed paragraph overlaps/touches the
   following "Scalability considerations" heading.
2. Page 13: the conclusion says 93.54% acceptance is in "Table 10"; Table 10 is
   a risk-calibration table, not primarily an acceptance/latency table.
3. Page 10/Table 11: the full-corpus row omits thousands separators
   (`13338/13373`) while surrounding text uses `13,338/13,373`.
4. Page 14/references: several URLs are visibly awkwardly line-broken, though
   hyperlink annotations appear intact.

## Metric Consistency Reported

| Claim | Consistency |
| --- | --- |
| 15,718 | Consistent full-detection denominator. |
| 13,373 | Consistent attempted/patched denominator. |
| 13,338 | Consistent accepted/auto-fixed numerator. |
| 99.74% | Consistent with 13,338/13,373. |
| 0.8486 | Consistent with 13,338/15,718. |
| 1,000/1,000 | Consistent and qualified as fixture-seeded live replay. |
| 88.52% | Consistent optional LLM 5k: 4,426/5,000. |
| 93.54% | Numerically consistent: 4,677/5,000; citation/table placement needs polish. |
| 7.9x | Consistent with 102.3 h / 13.0 h ≈ 7.9. |
| 42.97 vs 43.40 | Consistent; framed as comparable mean risk closure. |
| 247 over 152 | Consistent: Figure 5/text use 247 assignments over 152-item toy queue. |

## V18 Fixes Applied

- Shortened the page 4 reproduction-entry box by replacing the three-line
  command block with inline commands and adding explicit vertical spacing before
  "Scalability considerations."
- Revised the Table 10 caption to say "Risk calibration and accepted-fix
  summary," making the accepted-count column explicit.
- Revised the conclusion to say "4,677/5,000 accepted patches (93.54%)" before
  citing Table 10.
- Added thousands separators to Table 11 acceptance counts.
- Compacted Table 11's full-corpus row so the comma fix remains readable and
  does not introduce a table-width problem.
- Slightly increased URL stretchability to improve reference line breaks where
  possible without changing citation content or increasing the page count.

## V18 Verification

- Rebuilt with `tectonic --keep-logs --outdir build/v18 main.tex`.
- Output stayed at 14 pages.
- Extracted text saved to `docs/panel_evidence/pdf_texts/v18_built.txt`.
- Rendered page checks saved for pages 4, 10, 13, and 14 under
  `docs/panel_evidence/images/v18_pages/`.
- Text scan found no `Figure ??`, `Table ??`, undefined-citation marker,
  missing-file marker, stale uncomma'd count strings, or stale conclusion phrase.
- Visual review confirmed the page 4 box no longer touches the next heading,
  Table 11 is readable with comma'd counts, the conclusion carries the clearer
  4,677/5,000 phrasing, and reference URLs remain line-broken but not malformed
  or cut off.
