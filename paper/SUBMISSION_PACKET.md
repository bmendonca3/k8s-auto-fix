# TCC Submission Packet Index

Last local organization pass: 2026-05-31 16:19 MST.

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
- `paper/cover_letter.md` - cover-letter draft gated by editorial permission.
- `paper/response_to_reviewers.md` - point-by-point response draft gated by
  editorial permission.
- `paper/LOCAL_WORKTREE_STATE.md` - local worktree preservation note; do
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
- `paper/archives/overleaf_upload.zip`; the stale tracked archive was removed,
  and any regenerated archive should stay out of the portal/source upload path.
- Retired duplicate appendix source `appendix/appendices.tex`; use
  `paper/appendices.tex` only if supplemental appendix source is requested.
- Stale failure and run-history summaries such as
  `data/failures/taxonomy_summary.csv` and
  `data/batch_runs/grok_5k/metrics_history.json`.
- Local helper binaries, logs, and class copies such as `paper/tectonic`,
  `paper/missfont.log`, `paper/ieeeaccess.cls`,
  `paper/ieeeaccess.cls.backup`, `paper/overleaf/ieeeaccess.cls`, and
  `paper/overleaf/paper/ieeeaccess.cls`.
- Local cloud helper scripts or failed build logs such as
  `add_iam_policy_binding.sh`, `access.log`, and `logs/access.log`.
- Transient build products such as `main.aux`, `main.log`, `main.out`,
  `missfont.log`, and nested `missfont.log` files.
- `paper/overleaf/main.pdf` for source-only uploads; use `paper/access.pdf` as
  the portal manuscript PDF.
- Unreferenced image leftovers such as `dheer_toprani_photo.png`,
  `paper/overleaf/paper/overleaf_images/`, and unused IEEE template figures.
- Any Antigravity, Kiro, panel-review, or local scratch logs.

## Public Repo Note

The local packet-control and audit-summary files above are intentionally kept in the repository for traceability while the packet is being reviewed. They are
accepted as public repository context, but they are not submission artifacts and
must not be copied into a portal upload or Overleaf source package.

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
  2026-05-31 16:19 MST Kiro-nitpick source-package polish edits.
- `paper/appendices.pdf` was rebuilt from `paper/appendices.tex`; the appendix
  build produced 3 pages with no hard LaTeX errors.
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
- `tectonic -X compile access.tex --outdir /tmp/k8s_nitpick_final_standalone
  --keep-logs` passed from `paper/`; log reports 17 pages.
- `tectonic -X compile main.tex --outdir /tmp/k8s_nitpick_final_overleaf
  --keep-logs` passed from `paper/overleaf/`; log reports 17 pages.
- `tectonic -X compile appendices.tex --outdir /tmp/k8s_nitpick_appendices
  --keep-logs` passed from `paper/`; log reports 3 pages.

Before any upload, rerun the checklist in `docs/ieee_submission_checklist.md` and
confirm the final PDF, cover letter, and response letter still agree.

If source upload is requested, assemble a clean package from `paper/overleaf/`
instead of dragging the directory as-is; exclude `main.pdf`, local-only notes,
stale archives, unused template images, and any regenerated build products.
