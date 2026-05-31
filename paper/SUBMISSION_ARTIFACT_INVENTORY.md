# Submission Artifact Inventory

Last checked: 2026-05-31 14:16 MST.

This is a local inventory for the TCC-2025-12-0666 packet. It is not a
submission artifact and should not be uploaded.

## Gate

Do not email, upload, or submit any artifact until IEEE Transactions on Cloud
Computing confirms that TCC-2025-12-0666 may be resubmitted or reopened as a
major revision.

## Primary Portal Artifacts

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/access.pdf` | Main manuscript PDF | `8d439184dc2c6f5c9ea009bd2a86065332e6e6fc93ec28f7c1b63bc66065664b` |
| `paper/access.tex` | Authoritative standalone manuscript source | `f4ec26c63c0273f6f0774e6d8f81d421b3e749ea64fcee68f7fc1d5fbcaf8f4d` |
| `paper/cover_letter.md` | Cover-letter draft | `995bdbfdb1888f64d6279e91de80089f82831a206f95dcfe0731d43d3d1f3dae` |
| `paper/response_to_reviewers.md` | Point-by-point response draft | `13f68901137ccee87a88c95e7fbf238b541b5c53c3bb576175496e21a512c1f8` |
| `paper/references.bib` | BibTeX mirror of the active inline bibliography | `e65d4702ab1f6e11a3c642f872e6c2d39a67a6220738e90c49e3c3d868ff7895` |

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

The standalone source also has a commented-out input for
`docs/reproducibility/live_per_policy.tex`; it is not active in the current
build.

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
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='cover_letter.md' --exclude='paper/dheer_toprani_photo.png' --exclude='ieeeaccess.cls' --exclude='tectonic' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```

This preview command does not write files because it keeps `-n`.

Current key Overleaf hashes:

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/overleaf/main.tex` | Overleaf entry point | `6df68ddd89f4e5716fd0e8c16d005e0a11ac4c481675e28cf861148b15f3c7a8` |
| `paper/overleaf/paper/access.tex` | Overleaf manuscript source | `0b89c704e1c1da0ab049c2f3da23b8e003ae665bad6e6ca6ee8e85a823956e25` |
| `paper/overleaf/paper/references.bib` | Overleaf BibTeX mirror | `e65d4702ab1f6e11a3c642f872e6c2d39a67a6220738e90c49e3c3d868ff7895` |
| `paper/overleaf/main.pdf` | Local reference PDF, not required for source upload | `b1efc68567003955f5782a03f9e0fcc70a950060a5b866a3c354c32da01e2517` |
| `paper/overleaf/paper/grok_failures_table.tex` | Included failure-taxonomy table | `93211d9fde64b27cc0d07376d30fd7dc83dd63882c597f6a1a1d235fdf30a7ef` |
| `paper/overleaf/paper/reproducibility/baselines.tex` | Included baseline table | `6ca9d5f49d4d07a5b2980330ff0caad8d7219f2a15c34376367e4677ea804fcd` |

The standalone and Overleaf manuscript sources differ only by packaging paths:
font map paths, table input paths, figure paths, and biography image paths.
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
- `paper/archives/overleaf_upload.zip`; it is stale.
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
- Antigravity, Kiro, panel-review, or local scratch logs.

The local packet-control and audit-summary files listed here are intentionally public in the repository for traceability, but they are not part of the
submission packet or clean source package.

## Commands Used

```sh
rg -n -F '\input{' paper/access.tex paper/overleaf/paper/access.tex paper/overleaf/main.tex
rg -n -F '\includegraphics' paper/access.tex paper/overleaf/paper/access.tex paper/overleaf/main.tex
shasum -a 256 paper/access.pdf paper/access.tex paper/cover_letter.md paper/response_to_reviewers.md paper/overleaf/main.pdf paper/overleaf/main.tex paper/overleaf/paper/access.tex paper/references.bib paper/overleaf/paper/references.bib paper/grok_failures_table.tex docs/reproducibility/baselines.tex paper/overleaf/paper/grok_failures_table.tex paper/overleaf/paper/reproducibility/baselines.tex
diff -u paper/references.bib paper/overleaf/paper/references.bib
diff -u paper/grok_failures_table.tex paper/overleaf/paper/grok_failures_table.tex
diff -u docs/reproducibility/baselines.tex paper/overleaf/paper/reproducibility/baselines.tex
tectonic -X compile access.tex --outdir /tmp/k8s_goal_wholepaper_standalone --keep-logs
tectonic -X compile main.tex --outdir /tmp/k8s_goal_wholepaper_overleaf --keep-logs
find paper/overleaf -maxdepth 3 -type f \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name 'missfont.log' -o -name '.DS_Store' \) -print | sort
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='cover_letter.md' --exclude='paper/dheer_toprani_photo.png' --exclude='ieeeaccess.cls' --exclude='tectonic' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```
