# Response Letter Claim Check

Last checked: 2026-06-04 13:11 MST.

This is a local evidence checklist for `paper/response_to_reviewers.md`. It is
not a submission artifact and should not be uploaded.

## Gate

- The response letter remains gated on TCC/EIC confirmation that
  TCC-2025-12-0666 may be resubmitted or reopened as a major revision.
- If the manuscript, cover letter, or response letter changes, rerun this check
  before any portal upload.

## Checked Claims

| Response-letter claim | Current evidence | Status |
|---|---|---|
| Problematic references were replaced with Shamim et al., Xia et al., and Shu et al.; old placeholder keys are absent. | `paper/access.tex` cites `shamim2020`, `xia2023`, and `shu2017`; citation checks now report 38 cited keys, 38 bibitems, 0 missing, 0 uncited; targeted stale scan found no old fake-reference strings. | verified locally |
| Contribution is framed as a closed verification loop, not a single scanner or LLM proposer. | Introduction and contribution bullets in `paper/access.tex` describe policy re-check, schema validation, server-side dry-run, universal safety gates, and risk-aware scheduling. | verified locally |
| Related Work is organized into five classes and includes Polaris and LLMSecConfig. | `paper/access.tex` has five numbered related-work categories and cites `polaris` and `llmsecconfig`. | verified locally |
| Reviewer 2's introduction-split and alternative-tool requests are represented without inventing a reviewer concern. | `paper/response_to_reviewers.md` now has explicit Reviewer 2 concerns for the introduction structure and alternative tools/technologies; the operator-study cleanup is labeled as an author-side clarification rather than attributed to Reviewer 2. | verified locally |
| Reviewer 3's concern about Tables 1 and 2 comparing different systems is answered directly. | `paper/response_to_reviewers.md` explains that Table 1 is a lifecycle-role comparison and Table 2 has per-policy baselines with different denominators and evidence scopes. | verified locally |
| Architecture/setup include concrete component versions. | Figure caption in `paper/access.tex` lists kube-linter 0.7.6, kubectl 1.34.1, kind 0.30.0, Kubernetes 1.34.0, and Grok/xAI `grok-4.3`; evidence table records the environment. | verified locally |
| Limitations distinguish API-admission safety from full semantic equivalence. | `paper/access.tex` limitations state the verifier establishes policy, schema, and API-admission safety, not full workload semantic equivalence. | verified locally |
| Operator-study language is scoped to replay/simulation, not a finished live study. | Evidence-status table marks scheduler comparison as replay-based and Operator A/B as simulated only; stale scan found no completed-live-operator wording. | verified locally |
| No-policy ablation supports the agent-style acceptance-regime discussion without claiming a named-agent head-to-head. | `data/ablation/verifier_gate_metrics.json` reports 19 total patches, 15 baseline accepted, baseline acceptance 0.789474, no-policy 19 accepted, no-policy acceptance 1.0, no-new-violations 0.789474, and escapes `007`, `012`, `013`, `016`; `data/ablation/verifier_gate_details.json` records all four as policy re-check failures with `capabilities.drop missing ALL`; manuscript labels this as a guardrail ablation and future work for named agents; `paper/response_to_reviewers.md` now states that the 312/551 acceptance-boundary counts are historical snapshot-derived escapes, not a fresh current-verifier rerun or proxy results for a named agent. | verified locally |
| Acceptance-boundary snapshot caveats are visible in the manuscript and response letter. | `paper/access.tex` labels the extended-5k 4,677/5,000 (93.54%) result as a checked-in historical verifier-record snapshot and says current visible-verifier reruns differ; the verifier-ablation text, table caption, risk-calibration caption, and limitations all describe the rules-only 5k evidence as archived/snapshot-derived rather than a current verifier rerun. `paper/response_to_reviewers.md` uses historical snapshot-derived escape wording for the 312/551 counts. | verified locally |
| Live replay and cross-cluster rows are scoped to current artifacts. | `data/live_cluster/results_1k.json` has 1000 records, 1000 dry-run pass, 1000 live-apply pass, and 0 rollbacks; cross-cluster summaries show AKS 200/200, GKE 200/200, EKS 198/200, matching the manuscript table. | verified locally |
| Grok/xAI metrics use token counts and current-pricing guidance instead of a stale fixed dollar estimate. | `data/batch_runs/grok_5k/metrics_grok5k.json` reports 4426/5000 accepted, auto-fix rate 0.8852, 4,376,199 prompt tokens, 689,779 visible completion tokens, and 11,399,926 total tokens including xAI-reported reasoning tokens; manuscript cites `xai_pricing` rather than a fixed dollar total; `paper/overleaf/paper/access.tex` was synchronized from `paper/access.tex` on 2026-06-04 so the nested Overleaf source no longer carries the stale `~$1.22` wording. | verified locally |
| Scheduler headline numbers are artifact-backed. | `data/metrics_schedule_compare.json` reports FIFO top-risk P95 102.3333 hours and bandit top-risk P95 13.0 hours; manuscript rounds these as 102.3 h and 13.0 h. | verified locally |
| Full deterministic replay headline numbers are artifact-backed. | `data/metrics_rules_full.json` reports 15,718 detections, 13,373 patches/verified, 13,338 accepted, auto-fix rate 0.8486, and median patch ops 9. | verified locally |
| Standalone and Overleaf sources are synchronized for content, with path-only packaging differences. | `diff -u paper/access.tex paper/overleaf/paper/access.tex` now shows only Overleaf font-map path differences after the 2026-06-04 source sync; `paper/grok_failures_table.tex` matches its Overleaf mirror byte-for-byte; standalone, Overleaf, and appendix Tectonic builds passed from the synchronized sources. | verified locally |
| Packet hash inventory reflects the rebuilt local PDFs and synchronized mirrors. | `paper/access.pdf`, `paper/overleaf/main.pdf`, and `paper/appendices.pdf` were rebuilt from the synchronized sources; `paper/SUBMISSION_ARTIFACT_INVENTORY.md` now carries current SHA-256 values for the checked artifacts. `make submission-packet-check` now fails only on the pre-existing packet-tag gate because `tcc-2025-12-0666-packet-2026-05-31` points at an older packet commit than the current branch head; no local tag update was made. | verified with tag gate remaining |

## Commands Used

```sh
perl -ne 'while(/\\cite\{([^}]+)\}/g){ for $k (split /,/, $1){$k=~s/^\s+|\s+$//g; $c{$k}=1}} while(/\\bibitem\{([^}]+)\}/g){$b{$1}=1} END{print "cited_keys=", scalar(keys %c), "\n"; print "bibitems=", scalar(keys %b), "\n"; @missing=grep {!$b{$_}} sort keys %c; @uncited=grep {!$c{$_}} sort keys %b; print "missing=", join(",", @missing), "\n"; print "uncited=", join(",", @uncited), "\n"}' paper/access.tex
jq '{total_patches, baseline_accepted, baseline_acceptance_rate, no_policy: (.scenarios[] | select(.name=="no_policy") | {accepted, acceptance_rate, no_new_violations_rate, escapes})}' data/ablation/verifier_gate_metrics.json
jq '{detections, patches, verified, accepted, auto_fix_rate, median_patch_ops}' data/metrics_rules_full.json
jq '{detections, patches, verified, accepted, auto_fix_rate, median_patch_ops, model_usage}' data/batch_runs/grok_5k/metrics_grok5k.json
jq '{fifo_p95: .telemetry.fifo.top_risk_wait_hours.p95, bandit_p95: .telemetry.baseline.top_risk_wait_hours.p95}' data/metrics_schedule_compare.json
jq '{count: length, dry_run_pass: ([.[] | select(.dry_run_pass==true)] | length), live_apply_pass: ([.[] | select(.live_apply_pass==true)] | length), rollback_triggered: ([.[] | select(.rollback_triggered==true)] | length)}' data/live_cluster/results_1k.json
jq '[.[] | select(.id=="007" or .id=="012" or .id=="013" or .id=="016") | {id, accepted, ok_policy, errors}]' data/ablation/verifier_gate_details.json
jq '{count: length, dry_run_pass: ([.[] | select(.dry_run_pass==true)] | length), live_apply_pass: ([.[] | select(.live_apply_pass==true)] | length)}' data/cross_cluster/aks/results.json data/cross_cluster/gke/results.json data/cross_cluster/eks/results.json
diff -u paper/access.tex paper/overleaf/paper/access.tex
diff -u paper/grok_failures_table.tex paper/overleaf/paper/grok_failures_table.tex
tectonic -X compile access.tex --outdir /tmp/k8s_goal_standalone --keep-logs
tectonic -X compile main.tex --outdir /tmp/k8s_goal_overleaf --keep-logs
tectonic -X compile appendices.tex --outdir /tmp/k8s_goal_appendices --keep-logs
rg -n "Undefined control sequence|Citation .*undefined|Reference .*undefined|Fatal|Emergency stop|LaTeX Error|There were undefined references|\\?\\?" /tmp/k8s_goal_standalone/access.log /tmp/k8s_goal_overleaf/main.log /tmp/k8s_goal_appendices/appendices.log
make docs-link-check
make metrics-consistency
make submission-packet-check
.venv/bin/python -m unittest discover -s tests -p 'test_verifier.py'
diff -u paper/cover_letter.md paper/overleaf/paper/cover_letter.md
diff -u paper/references.bib paper/overleaf/paper/references.bib
diff -u docs/reproducibility/baselines.tex paper/overleaf/paper/reproducibility/baselines.tex
diff -u paper/acceptance_boundary_matrix.tex paper/overleaf/paper/acceptance_boundary_matrix.tex
rg -n "93\\.54|4,677|\\$1\\.22|1\\.22|current reruns|snapshot-derived|historical" paper/access.tex paper/overleaf/paper/access.tex paper/cover_letter.md paper/response_to_reviewers.md
# Also ran the targeted stale-wording scan used by the packet checklist against
# the manuscript, cover letter, response letter, packet index, and checklist.
```

## Remaining Manual Review

- Final author/scientific judgment is still needed for the novelty rebuttal.
- Final portal upload review still needs to compare the exact portal-bound PDF,
  cover letter, and response letter after any future edits.
- The local packet tag still points at an older commit; do not treat the packet
  tag as current until an explicitly requested local commit/tag refresh is done.
