# Submission Artifact Inventory

Last checked: 2026-05-31 11:28 MST.

This is a local inventory for the TCC-2025-12-0666 packet. It is not a
submission artifact and should not be uploaded.

## Gate

Do not email, upload, or submit any artifact until IEEE Transactions on Cloud
Computing confirms that TCC-2025-12-0666 may be resubmitted or reopened as a
major revision.

## Primary Portal Artifacts

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/access.pdf` | Main manuscript PDF | `2db5e83248411e3a0dad3c5d4ebe27d84359152766fb34d7dd019744f17e9d61` |
| `paper/access.tex` | Authoritative standalone manuscript source | `2c6bd41102cae98e6b8738a677ccdedec882c12a4708f1240c5a8cef8dbc6b2e` |
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
below still excludes regenerated scratch files and the local reference PDF. The
minimal source path is `paper/overleaf/main.tex`, which inputs `paper/access.tex`
inside the Overleaf package.

A dry-run clean-package preview is available with:

```sh
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='paper/dheer_toprani_photo.png' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```

This preview command does not write files because it keeps `-n`.

Current key Overleaf hashes:

| Artifact | Purpose | Current SHA-256 |
|---|---|---|
| `paper/overleaf/main.tex` | Overleaf entry point | `6df68ddd89f4e5716fd0e8c16d005e0a11ac4c481675e28cf861148b15f3c7a8` |
| `paper/overleaf/paper/access.tex` | Overleaf manuscript source | `a4439a0b38551d2c9c4bf1418af27c8978f225ed1a6cc4a5519e379d358bdf25` |
| `paper/overleaf/paper/references.bib` | Overleaf BibTeX mirror | `e65d4702ab1f6e11a3c642f872e6c2d39a67a6220738e90c49e3c3d868ff7895` |
| `paper/overleaf/main.pdf` | Local reference PDF, not required for source upload | `7c50c9a30ea2951e3e97ac008c8732649a1b31e964bc16b7ca3140e79223717d` |
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
- `.DS_Store` files.
- `notes/to-do list`.
- Transient build products from `paper/overleaf/`: `main.aux`, `main.log`,
  `main.out`, `missfont.log`, and nested `missfont.log` files.
- `paper/overleaf/main.pdf` for source-only uploads; it is a local reference PDF,
  while `paper/access.pdf` is the manuscript PDF selected for portal upload.
- Unreferenced image leftovers, including `paper/dheer_toprani_photo.png` and
  `paper/overleaf/paper/dheer_toprani_photo.png`.
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
./tectonic -X compile access.tex --outdir /tmp/k8s_goal_wholepaper_standalone --keep-logs
../tectonic -X compile main.tex --outdir /tmp/k8s_goal_wholepaper_overleaf --keep-logs
find paper/overleaf -maxdepth 3 -type f \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name 'missfont.log' -o -name '.DS_Store' \) -print | sort
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='paper/dheer_toprani_photo.png' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```
