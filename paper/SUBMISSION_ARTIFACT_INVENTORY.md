# Submission Artifact Inventory

Last checked: 2026-07-16 MST.

This is a local inventory for the TCC-2025-12-0666 packet. It is not a
submission artifact and should not be uploaded.

## Gate

Do not email, upload, or submit any artifact until IEEE Transactions on Cloud
Computing confirms that TCC-2025-12-0666 may be resubmitted or reopened as a
major revision.

## Manuscript Authority

Overleaf is the canonical manuscript source and PDF. The files under
`paper/overleaf/` are downstream mirrors imported from a verified paper-repo
commit; `paper/access.tex` and `paper/access.pdf` are deprecated compatibility
copies during migration. Do not use either artifact-repository copy to update
Overleaf.

Static manuscript hashes are intentionally not maintained in this prose file.
The next verified Overleaf import records source-tree, canonical-PDF, artifact
commit, and paper-repository commit hashes in generated sync locks.

## Supplemental Appendix Artifact

The supplemental appendix is not part of the primary portal manuscript unless
the portal or authors request it, but the tracked source and PDF now compile
together:

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/appendices.pdf` | Optional supplemental appendix PDF | `af99af7a122ae071b198c1def25c2ac8346769d3b3670573eced7bc2f442ab7d` |
| `paper/appendices.tex` | Optional supplemental appendix source | `901e3e581ac3aa7fd005ad7b22db56fa2f1cad39baa04ab0616952aa63d47580` |

## Deprecated Standalone Source Dependencies

`paper/access.tex` currently includes or references:

- `paper/reproducibility/baselines.tex`
- `paper/grok_failures_table.tex`
- `figures/fairness_waits.png`
- `figures/admission_vs_posthoc.png`
- `figures/mode_comparison.png`
- `paper/brian_mendonca_photo.png`
- `paper/vijay_madisetti_photo.png`

The inactive `live_per_policy` LaTeX input has been removed from the manuscript
source; the checked-in `docs/reproducibility/live_per_policy.tex` file is
retained only as a historical artifact.

## Overleaf Source Package

Treat `paper/overleaf/` as a downstream source-package mirror only. Assemble a
clean package from it for verification or archival purposes, never to overwrite
the canonical Overleaf project.
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

See `docs/OVERLEAF_SYNC.md` for the release order and verification gates. Hash
equality claims are made only from generated lock files after import, not from
this manually edited inventory.

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
- Any PDF not exported from the current canonical Overleaf revision. The
  imported Overleaf PDF is the only manuscript PDF eligible for portal use.
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
