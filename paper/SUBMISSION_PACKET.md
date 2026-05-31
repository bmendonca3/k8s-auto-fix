# TCC Submission Packet Index

Last local organization pass: 2026-05-31 03:55 MST.

This file is the local front door for the TCC-2025-12-0666 major-revision
packet. It is not an instruction to submit. Do not email, upload, open a pull
request, or comment externally unless explicitly requested.

## Gate

The packet remains gated. Do not submit until IEEE Transactions on Cloud
Computing confirms that TCC-2025-12-0666 may be resubmitted or reopened as a
major revision.

If the editorial office requires a new manuscript instead of a reopened major
revision, revise both `paper/cover_letter.md` and `paper/response_to_reviewers.md`
before upload.

## Use These Artifacts

- `paper/access.pdf` - manuscript PDF.
- `paper/access.tex` - authoritative manuscript source.
- `paper/overleaf/` - source-package root for assembling a clean Overleaf upload.
- `paper/cover_letter.md` - gated cover-letter draft.
- `paper/response_to_reviewers.md` - gated point-by-point response draft.
- `paper/LOCAL_WORKTREE_STATE.md` - local dirty-worktree preservation note; do
  not upload it.
- `paper/SUBMISSION_GAP_REGISTER.md` - local risk-ranked register of remaining
  gaps and closeout evidence; do not upload it.
- `paper/SUBMISSION_ARTIFACT_INVENTORY.md` - local inventory of uploadable
  artifacts, source dependencies, hashes, and exclusions; do not upload it.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md` - local evidence checklist for the
  response draft; do not upload it.
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md` - local 38/38 source-verification
  summary; do not upload it.
- `docs/ieee_submission_checklist.md` - portal checklist, do-not-upload list,
  and rebuild commands.
- `paper/REVISION_TRACKING.md` - source of truth for reviewer items, evidence,
  and remaining gaps.

## Do Not Upload

- `.DS_Store`.
- `notes/to-do list`.
- `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md`.
- `paper/LOCAL_WORKTREE_STATE.md`.
- `paper/SUBMISSION_GAP_REGISTER.md`.
- `paper/SUBMISSION_ARTIFACT_INVENTORY.md`.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md`.
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`.
- `paper/source_verification_mcp_2026-05-31.json`.
- `paper/REFERENCE_FIX_CHANGES.md`.
- `paper/REVISION_CHANGES_2026-05-30.md`.
- `paper/REVISION_TRACKING.md`.
- `paper/archives/overleaf_upload.zip`; it is a stale archive, so use the
  current `paper/overleaf/` tree as input when a source upload is needed.
- Transient Overleaf build products such as `main.aux`, `main.log`, `main.out`,
  `missfont.log`, and nested `missfont.log` files.
- `paper/overleaf/main.pdf` for source-only uploads; use `paper/access.pdf` as
  the portal manuscript PDF.
- Unreferenced author-photo leftovers such as `dheer_toprani_photo.png`.
- Any Antigravity, Kiro, panel-review, or local scratch logs.

## Current Remaining Gaps

- EIC/editorial permission is still the hard external gate.
- The point-by-point response letter now has a local claim-check ledger, but it
  must still be rechecked against the exact final PDF and artifacts before any
  portal upload.
- A named-agent head-to-head against Aardvark or KubeIntellect remains future
  work unless the authors approve and fund a new experiment.
- The novelty rebuttal remains an author/scientific judgment, not a local code
  or formatting task.

## Last Local Checks

The most recent organization and packaging pass verified:

- `paper/access.pdf` and `paper/overleaf/main.pdf` were rebuilt from the
  2026-05-31 03:55 MST source-precision manuscript edits.
- Standalone and Overleaf Tectonic builds both produced 17 pages with 0 fatal
  errors, 0 undefined references/citations, 0 `??` markers, and 0 overfull boxes.
- `.venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'` passed.
- `.venv/bin/python scripts/check_submission_packet.py` passed with current
  hash, source-package, stale-wording, mirror, repository snapshot, and checklist
  command guards.
- `make docs-link-check metrics-consistency` passed.
- `git diff --check` passed.
- Targeted stale-wording scan was clean for old metric values, stale fixed
  pricing, bad salutations, old venue wording, and tool-specific branding.
- `paper/cover_letter.md` and `paper/overleaf/paper/cover_letter.md` match.
- `./tectonic -X compile access.tex --outdir /tmp/k8s_source_precision_standalone
  --keep-logs` passed from `paper/`; log reports 17 pages.
- `../tectonic -X compile main.tex --outdir /tmp/k8s_source_precision_overleaf
  --keep-logs` passed from `paper/overleaf/`; log reports 17 pages.

Before any upload, rerun the checklist in `docs/ieee_submission_checklist.md` and
confirm the final PDF, cover letter, and response letter still agree.

If source upload is requested, assemble a clean package from `paper/overleaf/`
instead of dragging the directory as-is; the current tree contains local build
products that are explicitly excluded above.
