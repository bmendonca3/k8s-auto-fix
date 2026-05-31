# Submission Gap Register

Last checked: 2026-05-31 03:55 MST.

This is the local risk-ranked gap register for the TCC-2025-12-0666
major-revision packet. It is not a submission artifact and should not be
uploaded.

## Status Summary

Local packet organization is in good shape: the manuscript sources build, the
response letter exists, uploadable artifacts are inventoried, and response-letter
claims have local evidence. The packet is still **not go for submission** because
the editorial permission gate remains unresolved.

## Open Gaps

| Priority | Gap | Risk if ignored | Current evidence | Required closeout |
|---|---|---|---|---|
| P0 | TCC/EIC permission to resubmit or reopen TCC-2025-12-0666 as a major revision | Submitting through the wrong path could create a procedural rejection or duplicate/new-manuscript conflict. | `paper/REVISION_TRACKING.md` row 14 records the decision of record as Reject and says the EIC reply is still awaited. `paper/SUBMISSION_PACKET.md`, `docs/ieee_submission_checklist.md`, and `paper/response_to_reviewers.md` all keep the gate explicit. | Received editorial confirmation, then update this register, `paper/SUBMISSION_PACKET.md`, `docs/ieee_submission_checklist.md`, `paper/cover_letter.md`, and `paper/response_to_reviewers.md` if the required path differs from a reopened major revision. |
| P1 | Final portal-bound packet review after any future edit | A stale PDF, cover letter, response letter, or hash inventory could be uploaded after local files change. | `paper/SUBMISSION_ARTIFACT_INVENTORY.md` records current hashes; `paper/RESPONSE_LETTER_CLAIM_CHECK.md` maps response-letter claims to artifacts; `paper/SUBMISSION_PACKET.md` says to rerun the checklist before upload. | Re-run build, link/metric checks, stale scan, hash check, and response-letter claim check against the exact files selected for upload. |
| P1 | Named-agent head-to-head against Aardvark or KubeIntellect | Reviewers may still view the no-policy ablation as insufficient compared with a literal competing-agent experiment. | `paper/REVISION_TRACKING.md` rows 11-12 distinguish mitigated guardrail ablation from the still-open named-agent head-to-head. `paper/access.tex` and `paper/response_to_reviewers.md` explicitly defer the named-agent experiment to future work. | Author-approved experiment plan, runnable competing agent or access, funded API/compute budget, and a like-for-like protocol. Otherwise keep the manuscript scoped to the verified ablation. |
| P2 | Novelty rebuttal remains a scientific/editorial judgment | Even with stronger positioning, the response may not satisfy the reviewer if they expect a different novelty standard. | `paper/REVISION_TRACKING.md` row 13 marks this open; `paper/access.tex` sharpens the contribution around the closed verification loop and risk-aware scheduling. | Final author review, especially from Professor Madisetti, to decide whether the current positioning is sufficient or needs a stronger conceptual framing. |
| P2 | Overleaf/source upload hygiene | Source-upload requirements may differ by portal, and `paper/overleaf/main.pdf` remains a local reference PDF rather than a source input. | Tracked Overleaf scratch files (`main.aux`, `main.log`, `main.out`, `missfont.log`, and nested `paper/missfont.log`) were removed from the repository; `.gitignore` now excludes LaTeX aux files; unreferenced `dheer_toprani_photo.png` leftovers were removed from the source trees; `paper/SUBMISSION_ARTIFACT_INVENTORY.md`, `docs/ieee_submission_checklist.md`, `docs/REVIEW_RESPONSE.md`, and `paper/LOCAL_WORKTREE_STATE.md` still say to assemble a clean package rather than upload the directory as-is. | If source upload is requested, assemble only the needed source package from the current `paper/overleaf/` tree and exclude `main.pdf`, stale archives, local-only packet notes, and any regenerated scratch files. |

## Closed Local Organization Gaps

- Local packet front door exists: `paper/SUBMISSION_PACKET.md`.
- Uploadable artifact inventory exists: `paper/SUBMISSION_ARTIFACT_INVENTORY.md`.
- Response-letter claim traceability exists: `paper/RESPONSE_LETTER_CLAIM_CHECK.md`.
- Portal checklist separates local packet notes from submission artifacts:
  `docs/ieee_submission_checklist.md`.
- Portal checklist now lists all local-control files in its packet map before
  repeating the do-not-upload exclusions.
- Automated packet hygiene checker exists: `scripts/check_submission_packet.py`.
- Reviewer-response navigation note points to current packet files:
  `docs/REVIEW_RESPONSE.md`.

## Do Not Upload

- This file.
- `paper/SUBMISSION_PACKET.md`.
- `paper/LOCAL_WORKTREE_STATE.md`.
- `paper/SUBMISSION_ARTIFACT_INVENTORY.md`.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md`.
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`.
- `paper/source_verification_mcp_2026-05-31.json`.
- `paper/REFERENCE_FIX_CHANGES.md`.
- `paper/REVISION_CHANGES_2026-05-30.md`.
- `paper/REVISION_TRACKING.md`.
- `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md`.
- Any panel-review, Kiro, Antigravity, or local scratch logs.
