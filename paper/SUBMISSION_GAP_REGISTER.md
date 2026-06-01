# Submission Gap Register

Last checked: 2026-06-01 00:02 MST.

This is the local risk-ranked gap register for the TCC-2025-12-0666
major-revision packet. It is not a submission artifact and should not be
uploaded.

## Status Summary

Local packet organization is in good shape: the manuscript sources build, the
supplemental appendix source now rebuilds its PDF, the response letter exists,
uploadable artifacts are inventoried, and response-letter claims have local
evidence. The packet is still **not go for submission** because the editorial
permission gate remains unresolved.

## Open Gaps

| Priority | Gap | Risk if ignored | Current evidence | Required closeout |
|---|---|---|---|---|
| P0 | TCC/EIC permission to resubmit or reopen TCC-2025-12-0666 as a major revision | Submitting through the wrong path could create a procedural rejection or duplicate/new-manuscript conflict. | `paper/REVISION_TRACKING.md` row 14 records the decision of record as Reject. Gmail was rechecked on 2026-05-31 12:17 MST with targeted `TCC-2025-12-0666`, Song Guo, TCC, resubmit, reopen, and major-revision queries; the current thread still contains only the 2026-05-30 rejection, Professor Madisetti's question asking whether a major revision can be resubmitted, and Brian's forward to George Jobi. No EIC/editorial approval reply was found. `paper/SUBMISSION_PACKET.md`, `docs/ieee_submission_checklist.md`, and `paper/response_to_reviewers.md` all keep the gate explicit. | Received editorial confirmation, then update this register, `paper/SUBMISSION_PACKET.md`, `docs/ieee_submission_checklist.md`, `paper/cover_letter.md`, and `paper/response_to_reviewers.md` if the required path differs from a reopened major revision. |
| P1 | Final portal-bound packet review after any future edit | A stale PDF, cover letter, response letter, or hash inventory could be uploaded after local files change. | `paper/SUBMISSION_ARTIFACT_INVENTORY.md` records current hashes; `paper/RESPONSE_LETTER_CLAIM_CHECK.md` maps response-letter claims to artifacts; `paper/SUBMISSION_PACKET.md` says to rerun the checklist before upload. | Re-run build, link/metric checks, stale scan, hash check, and response-letter claim check against the exact files selected for upload. |
| P1 | Executed acceptance-boundary comparator matrix | Reviewer 3 may still read the current guardrail ablation as a proxy rather than the requested scientific-state-of-the-art comparison, leaving the novelty objection unresolved. | The current paper reports the real no-policy verifier ablation and explicitly does not claim it is a named-agent comparison. The latest review recommends reframing novelty around the question "what verifier acceptance boundary is necessary for safe automated remediation?" and comparing weaker boundaries directly. | Author-approved protocol and run for a small matrix: ungated/weakly gated LLM proposer, scanner-only acceptance, admission/Kyverno-style acceptance, and full `k8s-auto-fix` verifier boundary on the same manifest slice. Report accepted count, unsafe/incomplete accepted patches, failures, runtime/cost, and artifact paths; update `paper/access.tex`, `paper/response_to_reviewers.md`, figures/tables, and `ARTIFACTS.md`. |
| P1 | Named-agent head-to-head against Codex Security or KubeIntellect | Reviewers may still view the no-policy ablation as insufficient compared with a literal competing-agent experiment. | `paper/REVISION_TRACKING.md` rows 11-12 distinguish mitigated guardrail ablation from the still-open named-agent head-to-head. `paper/access.tex` and `paper/response_to_reviewers.md` explicitly defer the named-agent experiment to future work. | Author-approved experiment plan, runnable competing agent or access, funded API/compute budget, and a like-for-like protocol. Otherwise keep the manuscript scoped to the verified ablation. |
| P1 | Full citation audit before any resubmission | Reviewer 1 explicitly flagged nonexistent references; any remaining metadata drift would revive the "AI-generated" credibility concern. | The three previously fabricated references are gone. A 2026-06-01 spot-check found that arXiv:2509.02449 is `KubeIntellect` by Mohsen Seyedkazemi Ardebili and Andrea Bartolini, matching the current BibTeX family-name metadata; the inline bibliography uses the abbreviated form `M. S. Ardebili`. Other preprints still need a complete primary-source recheck immediately before resubmission. | Verify every bibliography entry against primary sources: title, authors, venue/journal, year, DOI, arXiv ID, and URL. Refresh `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md` or create a new dated source-verification note, then update the response letter to say all references were verified against primary sources. |
| P2 | Novelty rebuttal remains a scientific/editorial judgment | Even with stronger positioning, the response may not satisfy the reviewer if they expect a different novelty standard. | `paper/REVISION_TRACKING.md` row 13 marks this open; `paper/access.tex` sharpens the contribution around the closed verification loop and risk-aware scheduling. | Final author review, especially from Professor Madisetti, to decide whether the current positioning is sufficient or needs a stronger conceptual framing. |
| P2 | Presentation follow-through after any comparator work | If new evidence is added without trimming the narrative, the paper may regress toward the "product manual" and sprawling-evaluation critique. | The current manuscript already uses standard section order, systematic related-work categories, and an explicit explanation for different comparison-table rosters. The latest review still recommends literal R3 follow-through: keep detailed numbers out of the Introduction body, make table rosters explicit, discuss every table system in prose, and move low-level artifact enumeration out of the main flow where possible. | After comparator/citation decisions, run a short presentation pass over `paper/access.tex`: intro scan, table-roster explanation, related-work coverage map, evaluation-length cut list, and response-letter mapping. Rebuild PDFs and rerun packet checks afterward. |
| P2 | Point-by-point response update for the latest strategic framing | A response letter that only describes polish may fail to show that R1/R3's core novelty and comparison concerns were handled. | `paper/response_to_reviewers.md` exists and already maps many changes. It does not yet claim an executed named-agent or comparator-matrix experiment. | Once the author decides whether to add the comparator experiment, update the response letter with "Changed X, see Section/Table Y" entries for novelty, comparator evidence, citation audit, presentation cleanup, and any intentionally deferred external-agent comparison. |
| P2 | Overleaf/source upload hygiene | Source-upload requirements may differ by portal, and `paper/overleaf/main.pdf` remains a local reference PDF rather than a source input. | Tracked Overleaf scratch files (`main.aux`, `main.log`, `main.out`, `missfont.log`, and nested `paper/missfont.log`) were removed from the repository; `.gitignore` now excludes LaTeX aux files; unreferenced `dheer_toprani_photo.png`, `paper/overleaf/paper/overleaf_images/`, `paper/overleaf/figures/failure_taxonomy.png`, and unused IEEE template image leftovers were removed from the source tree; `paper/SUBMISSION_ARTIFACT_INVENTORY.md`, `docs/ieee_submission_checklist.md`, `docs/REVIEW_RESPONSE.md`, and `paper/LOCAL_WORKTREE_STATE.md` still say to assemble a clean package rather than upload the directory as-is. | If source upload is requested, assemble only the needed source package from the current `paper/overleaf/` tree and exclude `main.pdf`, stale archives, local-only packet notes, unused template images, and any regenerated scratch files. |

## Latest Feedback Completion Checklist

The 2026-06-01 pasted strategic review is accepted as a planning input, not as
proof of completion. The local closeout checklist is:

- [ ] Decide whether to run the acceptance-boundary comparator matrix before any
  resubmission.
- [ ] If approved, implement the comparator protocol on an identical manifest
  slice and add the resulting table/figure/artifacts to the manuscript packet.
- [ ] If a named agent is runnable with author-approved budget/access, run it;
  otherwise keep Codex Security/KubeIntellect as explicitly deferred and avoid
  assigning proxy counts to either system.
- [ ] Run a full primary-source citation audit, paying special attention to
  arXiv preprints and recently added Kubernetes-agent references.
- [ ] Update the response letter after the comparator/citation decisions so R1
  and R3 can see the exact sections and artifacts that address their core
  objections.
- [ ] Perform a final presentation pass after any new experiment: introduction
  numbers, table rosters, related-work coverage, evaluation length, and
  artifact-table placement.
- [ ] Rebuild `paper/access.pdf` and `paper/overleaf/main.pdf`, refresh hashes,
  rerun packet checks, and only then consider portal/source packaging after the
  TCC/EIC gate is resolved.

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
- Upload-facing GitHub links are pinned to the packet tag rather than mutable
  `main` paths.
- Retired duplicate or stale public artifacts were removed from the tracked
  packet path: `appendix/appendices.tex`, `data/failures/taxonomy_summary.csv`,
  `data/batch_runs/grok_5k/metrics_history.json`, `paper/tectonic`,
  `paper/missfont.log`, `paper/ieeeaccess.cls`,
  `paper/ieeeaccess.cls.backup`, `paper/overleaf/ieeeaccess.cls`,
  `paper/overleaf/paper/ieeeaccess.cls`, `paper/archives/overleaf_upload.zip`,
  `add_iam_policy_binding.sh`, `access.log`, and `logs/access.log`.

## Editorial Follow-Up Draft

Do not send without explicit author approval. Suggested follow-up text if the
authors want to ask the editorial office again:

Dear Professor Guo,

I am following up on Professor Madisetti's question about manuscript
TCC-2025-12-0666. Given that two of the three reviews recommended revision, may
we submit the substantially revised manuscript as a major revision or reopen the
existing manuscript record? If TCC requires a different path, such as a new
submission, please let us know and we will follow that process.

Thank you for your guidance.

Sincerely,

Brian Mendonca and Vijay K. Madisetti

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
- `paper/archives/overleaf_upload.zip`; the stale tracked copy was removed.
- `paper/missfont.log`.
- `paper/ieeeaccess.cls.backup`.
- `paper/overleaf/paper/ieeeaccess.cls`.
- `add_iam_policy_binding.sh`.
- `access.log`.
- `logs/access.log`.
- Any panel-review, Kiro, Antigravity, or local scratch logs.
