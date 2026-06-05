# Submission Artifact Inventory

Last checked: 2026-06-04 13:11 MST.

This is a local inventory for the TCC-2025-12-0666 packet. It is not a
submission artifact and should not be uploaded.

## Gate

Do not email, upload, or submit any artifact until IEEE Transactions on Cloud
Computing confirms that TCC-2025-12-0666 may be resubmitted or reopened as a
major revision.

## Primary Portal Artifacts

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/access.pdf` | Main manuscript PDF | `36be4880d1810b3c7c281440bce935cf3a2428a9b32d8f44bf98eae482fae999` |
| `paper/access.tex` | Authoritative standalone manuscript source | `29c1f14b4a7b80223648ba5d6776a2b0e22afbe2276981af1c57811335071bae` |
| `paper/cover_letter.md` | Cover-letter draft | `c399eb46d035e1eed47e20544cd3b4a72fbb3e0bf8185c705e946c4561d54c96` |
| `paper/response_to_reviewers.md` | Point-by-point response draft | `594ed598057eb854289aecbdc4eada3efb51aaf59ffb5f5c7f47c7e686afc72e` |
| `paper/references.bib` | BibTeX mirror of the active inline bibliography | `e65d4702ab1f6e11a3c642f872e6c2d39a67a6220738e90c49e3c3d868ff7895` |

## Supplemental Appendix Artifact

The supplemental appendix is not part of the primary portal manuscript unless
the portal or authors request it, but the tracked source and PDF now compile
together:

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/appendices.pdf` | Optional supplemental appendix PDF | `9f74a2fe157e873b5e01dfef21e271974fc59ea8d0fb729188a3276eb7804d27` |
| `paper/appendices.tex` | Optional supplemental appendix source | `fa1e8b6f7b0c4b1681c1b7d8d848fa5b9a00c5a42df25f7b51b60a163d59b681` |

## Standalone Source Dependencies

`paper/access.tex` currently includes or references:

- `docs/reproducibility/baselines.tex`
- `paper/grok_failures_table.tex`
- `figures/fairness_waits.png`
- `figures/admission_vs_posthoc.png`
- `figures/mode_comparison.png`
- `figures/operator_ab.png`
- `paper/brian_mendonca_photo.png`
- `paper/vijay_madisetti_photo.png`

The inactive `live_per_policy` LaTeX input has been removed from the manuscript
source; the checked-in `docs/reproducibility/live_per_policy.tex` file is
retained only as a historical artifact.

## Overleaf Source Package

Use `paper/overleaf/` as the source-package root if Overleaf upload is needed,
but assemble a clean package from it instead of uploading the directory as-is.
Tracked LaTeX scratch files were removed from this tree; the dry-run command
below still excludes regenerated scratch files, local reference PDFs, local
draft prose, and retired helper copies. The minimal source path is
`paper/overleaf/main.tex`, which inputs `paper/access.tex` inside the Overleaf
package. `ieeeaccess.cls` and the Tectonic executable are not source-package
inputs; the current manuscript builds with `IEEEtran`, so local legacy class
helper copies are unused and excluded from clean package previews.

A dry-run clean-package preview is available with:

```sh
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='cover_letter.md' --exclude='paper/dheer_toprani_photo.png' --exclude='paper/overleaf_images/' --exclude='figures/failure_taxonomy.png' --exclude='paper/author1.png' --exclude='paper/aws.jpg' --exclude='paper/bullet.png' --exclude='paper/equation3.png' --exclude='paper/fig1.png' --exclude='paper/logo.png' --exclude='paper/notaglinelogo.png' --exclude='ieeeaccess.cls' --exclude='tectonic' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```

This preview command does not write files because it keeps `-n`.

Current key Overleaf hashes:

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/overleaf/main.tex` | Overleaf entry point | `6df68ddd89f4e5716fd0e8c16d005e0a11ac4c481675e28cf861148b15f3c7a8` |
| `paper/overleaf/paper/access.tex` | Overleaf manuscript source | `dbe4a72420d76a339ca8d4ecb33a6058e4e78a4e2406dfec7a25a8f8c4e3bb5c` |
| `paper/overleaf/paper/references.bib` | Overleaf BibTeX mirror | `e65d4702ab1f6e11a3c642f872e6c2d39a67a6220738e90c49e3c3d868ff7895` |
| `paper/overleaf/main.pdf` | Local reference PDF, not required for source upload | `d68f038fc912118aee4814334ec507fa6a4fca89b631a3a2d399bd79d76ea554` |
| `paper/overleaf/paper/grok_failures_table.tex` | Included failure-taxonomy table | `6b941cf21c4115a078d5a5f8f9ef7de75941cd2cf9001c7207cb294a13f85318` |
| `paper/overleaf/paper/reproducibility/baselines.tex` | Included baseline table | `6ca9d5f49d4d07a5b2980330ff0caad8d7219f2a15c34376367e4677ea804fcd` |

The standalone and Overleaf manuscript sources differ only by source-package
font-map paths.
`paper/references.bib` matches the Overleaf copy byte-for-byte,
`paper/grok_failures_table.tex` matches the Overleaf copy byte-for-byte, and
`docs/reproducibility/baselines.tex` matches the Overleaf copy byte-for-byte.

## Do Not Upload

- This file.
- `paper/SUBMISSION_PACKET.md`.
- `paper/SUBMISSION_GAP_REGISTER.md`.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md`.
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`.
- `paper/source_verification_mcp_2026-05-31.json`.
- `paper/REFERENCE_FIX_CHANGES.md`.
- `paper/REVISION_CHANGES_2026-05-30.md`.
- `paper/LOCAL_WORKTREE_STATE.md`.
- `paper/REVISION_TRACKING.md`.
- `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md`.
- `paper/archives/overleaf_upload.zip`; the stale tracked copy was removed, and
  any regenerated archive should stay out of the portal/source upload path.
- Legacy standalone appendix source `appendix/appendices.tex`; use
  `paper/appendices.tex` only if supplemental appendix source is requested.
- Stale failure and run-history summaries such as
  `data/failures/taxonomy_summary.csv` and
  `data/batch_runs/grok_5k/metrics_history.json`; use
  `data/metrics_rules_full.json`,
  `data/batch_runs/grok_5k/metrics_grok5k.json`, and cited taxonomy artifacts
  instead.
- `.DS_Store` files.
- `notes/to-do list`.
- Local helper binaries, logs, and class copies such as `paper/tectonic`,
  `paper/missfont.log`, `paper/ieeeaccess.cls`,
  `paper/ieeeaccess.cls.backup`, `paper/overleaf/ieeeaccess.cls`, and
  `paper/overleaf/paper/ieeeaccess.cls`.
- Local cloud helper scripts or failed build logs such as
  `add_iam_policy_binding.sh`, `access.log`, and `logs/access.log`.
- Transient build products: `main.aux`, `main.log`, `main.out`,
  `missfont.log`, and nested `missfont.log` files.
- `paper/overleaf/main.pdf` for source-only uploads; it is a local reference PDF,
  while `paper/access.pdf` is the manuscript PDF selected for portal upload.
- Unreferenced image leftovers, including stale copies of
  `paper/dheer_toprani_photo.png` or
  `paper/overleaf/paper/dheer_toprani_photo.png` if they reappear.
- Unreferenced Overleaf template/image leftovers, including
  `paper/overleaf/paper/overleaf_images/`,
  `paper/overleaf/figures/failure_taxonomy.png`, and unused IEEE template
  images such as `paper/overleaf/paper/fig1.png`.
- Antigravity, Kiro, panel-review, or local scratch logs.

The local packet-control and audit-summary files listed here are intentionally public in the repository for traceability, but they are not part of the
submission packet or clean source package.

## Commands Used

```sh
rg -n -F '\input{' paper/access.tex paper/overleaf/paper/access.tex paper/overleaf/main.tex
rg -n -F '\includegraphics' paper/access.tex paper/overleaf/paper/access.tex paper/overleaf/main.tex
shasum -a 256 paper/access.pdf paper/access.tex paper/appendices.pdf paper/appendices.tex paper/cover_letter.md paper/response_to_reviewers.md paper/overleaf/main.pdf paper/overleaf/main.tex paper/overleaf/paper/access.tex paper/references.bib paper/overleaf/paper/references.bib paper/grok_failures_table.tex docs/reproducibility/baselines.tex paper/overleaf/paper/grok_failures_table.tex paper/overleaf/paper/reproducibility/baselines.tex scripts/check_submission_packet.py
diff -u paper/references.bib paper/overleaf/paper/references.bib
diff -u paper/grok_failures_table.tex paper/overleaf/paper/grok_failures_table.tex
diff -u docs/reproducibility/baselines.tex paper/overleaf/paper/reproducibility/baselines.tex
tectonic -X compile access.tex --outdir /tmp/k8s_goal_standalone --keep-logs
tectonic -X compile main.tex --outdir /tmp/k8s_goal_overleaf --keep-logs
tectonic -X compile appendices.tex --outdir /tmp/k8s_goal_appendices --keep-logs
find paper/overleaf -maxdepth 3 -type f \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name 'missfont.log' -o -name '.DS_Store' \) -print | sort
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='cover_letter.md' --exclude='paper/dheer_toprani_photo.png' --exclude='paper/overleaf_images/' --exclude='figures/failure_taxonomy.png' --exclude='paper/author1.png' --exclude='paper/aws.jpg' --exclude='paper/bullet.png' --exclude='paper/equation3.png' --exclude='paper/fig1.png' --exclude='paper/logo.png' --exclude='paper/notaglinelogo.png' --exclude='ieeeaccess.cls' --exclude='tectonic' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```
