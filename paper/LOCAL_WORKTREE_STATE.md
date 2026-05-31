# Local Worktree State

Last checked: 2026-05-31 11:43 MST.

This is a local preservation note for the `k8s-auto-fix` worktree around the
2026-05-31 packet cleanup. It is not a submission artifact and should not be
uploaded.

## Repository

- Branch: `improvmenets`.
- Upstream: `origin/improvmenets`.
- Local branch state at capture time: ahead by 2 commits before the packet
  cleanup push.
- Remote verified: `https://github.com/bmendonca3/k8s-auto-fix.git`.
- Latest local commits:
  - `6c82e58` (`2026-05-30T23:16:48-07:00`) by `bmendonca3`: Tighten K8S camera-ready claims and rank labels.
  - `12f255e` (`2026-05-30T22:51:41-07:00`) by `bmendonca3`: Cite scheduling evidence and update cost-reference prose.

## Preservation Rule

Do not clean, reset, checkout, or revert these local changes unless explicitly
asked. Some files are local-only packet controls, and some tracked changes may be
user-owned.

The tracked/untracked file set below was rechecked at 2026-05-31 11:43 MST
before the packet-cleanup commit. After commit or push, use `git status --short
--branch` as the current state and treat this section as a preservation record.

## Tracked Modified Files

Current `git diff --name-status` reports:

- `.DS_Store`
- `ARTIFACTS.md`
- `Makefile`
- `README.md`
- `data/baselines/mode_comparison.csv`
- `data/eval/unified_eval_summary.json`
- `docs/REVIEW_RESPONSE.md`
- `docs/ieee_submission_checklist.md`
- `figures/mode_comparison.png`
- `notes/to-do list`
- `paper/REFERENCE_FIX_CHANGES.md`
- `paper/REVISION_CHANGES_2026-05-30.md`
- `paper/REVISION_TRACKING.md`
- `paper/access.pdf`
- `paper/access.tex`
- `paper/cover_letter.md`
- `paper/overleaf/figures/mode_comparison.png`
- `paper/overleaf/main.pdf`
- `paper/overleaf/paper/access.tex`
- `paper/overleaf/paper/cover_letter.md`
- `paper/overleaf/paper/references.bib`
- `paper/references.bib`
- `scripts/README.md`
- `scripts/build_repro_bundle.py`

## Untracked Files

Current `git ls-files --others --exclude-standard` reports:

- `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md`
- `paper/LOCAL_WORKTREE_STATE.md`
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md`
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`
- `paper/SUBMISSION_ARTIFACT_INVENTORY.md`
- `paper/SUBMISSION_GAP_REGISTER.md`
- `paper/SUBMISSION_PACKET.md`
- `paper/response_to_reviewers.md`
- `paper/source_verification_mcp_2026-05-31.json`
- `scripts/check_submission_packet.py`

## Packet Role Summary

- Upload-facing drafts: `paper/access.pdf`, `paper/access.tex`,
  `paper/cover_letter.md`, and `paper/response_to_reviewers.md`.
- Source-package input: `paper/overleaf/`; assemble a clean source package from
  this tree instead of uploading the directory as-is. Tracked aux/log/out
  byproducts have been removed, but still exclude regenerated scratch files and
  `paper/overleaf/main.pdf` unless the portal explicitly requests a compiled PDF
  inside the TeX source bundle.
- Local-only packet controls: `paper/SUBMISSION_PACKET.md`,
  `paper/SUBMISSION_GAP_REGISTER.md`,
  `paper/SUBMISSION_ARTIFACT_INVENTORY.md`,
  `paper/RESPONSE_LETTER_CLAIM_CHECK.md`, `paper/REVISION_TRACKING.md`, and
  this file.
- Local-only audit/scratch material:
  `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md`,
  `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`,
  `paper/source_verification_mcp_2026-05-31.json`,
  `paper/REFERENCE_FIX_CHANGES.md`,
  `paper/REVISION_CHANGES_2026-05-30.md`,
  `notes/to-do list`, `.DS_Store`, and panel/Kiro/Antigravity logs.

## Verification Snapshot

- Fresh standalone compile to `/tmp/k8s_goal_wholepaper_standalone` passed and
  reported 17 pages.
- Fresh Overleaf compile to `/tmp/k8s_goal_wholepaper_overleaf` passed and
  reported 17 pages.
- Hard-error scan over both fresh logs found no fatal errors, undefined
  references/citations, `??` markers, or overfull boxes.

## Commands Used

```sh
git status --short --branch
git remote -v
git diff --name-status
git ls-files --others --exclude-standard
git log -2 --pretty=format:'%h %cI %an <%ae> %s'
.venv/bin/python scripts/check_submission_packet.py
tectonic -X compile access.tex --outdir /tmp/k8s_goal_wholepaper_standalone --keep-logs
tectonic -X compile main.tex --outdir /tmp/k8s_goal_wholepaper_overleaf --keep-logs
rg -n "Undefined control sequence|Citation .*undefined|Reference .*undefined|Fatal|Emergency stop|LaTeX Error|Overfull|\?\?" /tmp/k8s_goal_wholepaper_standalone/access.log /tmp/k8s_goal_wholepaper_overleaf/main.log
```
