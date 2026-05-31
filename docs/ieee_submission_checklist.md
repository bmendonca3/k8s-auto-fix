# TCC / ScholarOne Submission Checklist — k8s-auto-fix

## Submission Gate
- Do not submit until IEEE Transactions on Cloud Computing confirms that
  TCC-2025-12-0666 may be resubmitted or reopened as a major revision.
- If permission is denied or the paper must be submitted as a new manuscript,
  update the cover letter and any response text before upload.

## Local Packet Map
- `paper/SUBMISSION_PACKET.md` — local packet index and current gate summary;
  use it to navigate the packet, but do not upload it.
- `paper/LOCAL_WORKTREE_STATE.md` — local worktree preservation note; do
  not upload it.
- `paper/SUBMISSION_GAP_REGISTER.md` — local risk-ranked register of remaining
  gaps and closeout evidence; do not upload it.
- `paper/SUBMISSION_ARTIFACT_INVENTORY.md` — local inventory of uploadable
  artifacts, source dependencies, hashes, and exclusions; do not upload it.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md` — local response-letter evidence
  checklist; do not upload it.
- `paper/REVISION_TRACKING.md` — local reviewer-item ledger and evidence map; do
  not upload it.

## Submission Artifacts
- `paper/access.pdf` — final manuscript PDF compiled from `paper/access.tex`.
- `paper/access.tex` — authoritative source for the manuscript.
- `paper/grok_failures_table.tex` — included failure-taxonomy table.
- `docs/reproducibility/baselines.tex` — included baseline table source.
- Repository-root `figures/*.png`, `paper/overleaf/figures/*.png`, and the two
  author photos referenced by the source.
- `paper/cover_letter.md` — TCC resubmission cover-letter draft.
- `paper/response_to_reviewers.md` — point-by-point response draft for the
  major-revision packet.
- `paper/overleaf/` — source-package root when an online TeX upload is needed;
  assemble a clean package from this tree instead of uploading the directory
  as-is.

## Do Not Upload
- `paper/SUBMISSION_PACKET.md` — local organization note.
- `paper/LOCAL_WORKTREE_STATE.md` — local worktree preservation note, not
  submission prose.
- `paper/SUBMISSION_GAP_REGISTER.md` — local gap register, not submission prose.
- `paper/SUBMISSION_ARTIFACT_INVENTORY.md` — local artifact inventory, not
  submission prose.
- `.DS_Store` files.
- `notes/to-do list` — local planning notes, not submission material.
- `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md` — local audit artifact,
  not submission prose.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md` — local response-letter evidence
  checklist, not submission prose.
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md` — local source-verification
  audit snapshot, not submission prose.
- `paper/source_verification_mcp_2026-05-31.json` — local source-verification
  evidence registry, not submission prose.
- `paper/REFERENCE_FIX_CHANGES.md` — local reference-fix audit, not submission
  prose.
- `paper/REVISION_CHANGES_2026-05-30.md` — local revision change log, not
  submission prose.
- `paper/REVISION_TRACKING.md` — local reviewer-item ledger, not submission
  prose.
- `paper/archives/overleaf_upload.zip` — stale archive; rebuild a clean package
  from the current `paper/overleaf/` tree if the portal needs source files.
- `appendix/appendices.tex` — retired duplicate appendix source; use
  `paper/appendices.tex` only if supplemental appendix source is requested.
- `data/failures/taxonomy_summary.csv` and
  `data/batch_runs/grok_5k/metrics_history.json` — retired stale summaries; use
  `data/metrics_rules_full.json`,
  `data/batch_runs/grok_5k/metrics_grok5k.json`, and cited taxonomy artifacts.
- Local helper binaries and class copies such as `paper/tectonic`,
  `paper/ieeeaccess.cls`, and `paper/overleaf/ieeeaccess.cls`.
- Local cloud helper scripts or failed build logs such as
  `add_iam_policy_binding.sh`, `access.log`, and `logs/access.log`.
- Transient Overleaf build products such as `main.aux`, `main.log`, `main.out`,
  `missfont.log`, and nested `missfont.log` files.
- Unreferenced author-photo leftovers such as `dheer_toprani_photo.png`.
- Antigravity, Kiro, or panel-review logs.

## Rebuild Commands
```
cd paper
tectonic -X compile access.tex --outdir /tmp/k8s_tcc_build --keep-logs
cd ..
cd paper/overleaf
tectonic -X compile main.tex --outdir /tmp/k8s_overleaf_build --keep-logs
cd ../..
make submission-packet-check
make docs-link-check metrics-consistency
.venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'
git diff --check
.venv/bin/python -c "import json; d=json.load(open('data/metrics_schedule_compare.json')); print('FIFO P95:', d['telemetry']['fifo']['top_risk_wait_hours']['p95']); print('Bandit P95:', d['telemetry']['baseline']['top_risk_wait_hours']['p95'])"
.venv/bin/python -c "import json; print('Detector F1:', json.load(open('data/eval/detector_metrics.json'))['f1'])"
```

## Clean Source Package Guard
Before any Overleaf or source upload, identify source-tree build products and
confirm the selected upload set excludes them:

```
find paper/overleaf -maxdepth 3 -type f \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name 'missfont.log' -o -name '.DS_Store' \) -print | sort
```

Any files printed by that command are local build products and should not be in
the upload package.

To preview a clean package without writing files or uploading anything, run:

```
rsync -ain --delete --exclude='*.aux' --exclude='*.log' --exclude='*.out' --exclude='missfont.log' --exclude='.DS_Store' --exclude='main.pdf' --exclude='cover_letter.md' --exclude='paper/dheer_toprani_photo.png' --exclude='ieeeaccess.cls' --exclude='tectonic' paper/overleaf/ /tmp/k8s_overleaf_clean_package_preview/
```

Remove `-n` only after the submission gate is satisfied and the portal's source
requirements are known.

## Portal Checklist
1. Upload `paper/access.pdf` as the main manuscript.
2. Paste or upload `paper/cover_letter.md` only after the resubmission gate is satisfied.
3. Paste or upload `paper/response_to_reviewers.md` only after the resubmission gate is satisfied.
4. Attach supplemental/reproducibility materials if the portal allows them.
5. Complete author and affiliation metadata exactly as in the manuscript.
6. Confirm keywords match the manuscript.
7. Confirm that all reviewer-response claims match the current PDF and artifacts.
8. Retain the portal confirmation email and manuscript ID.
