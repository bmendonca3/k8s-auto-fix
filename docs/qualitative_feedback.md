# Qualitative Feedback Log

Use this log to capture reviewer and operator feedback on auto-generated patches.

| Date | Reviewer | Context | Manifest/Queue ID | Feedback | Follow-up |
| ---- | -------- | ------- | ----------------- | -------- | --------- |
| 2025-10-10 | SRE On-call | Post-run review of top-risk queue | 01167 | “Patch landed cleanly, pod restarts down, no additional alerts.” | Monitor overnight; add to success stories. |
| 2025-10-10 | Platform Eng | Review of Cilium daemonset fix | 00185 | “Capability drop required minor exception but passes internal tests.” | Document guard rationale in privileged playbook. |
| 2025-10-12 | SRE Rotation | Incident retro (baseline vs Grok) | 01006 | “Rules mode cleared the alert in 25 min; Grok variant needed a manual tweak to CPU requests.” | Capture Grok regression in ablation log; re-run with new guard. |
| 2025-10-12 | Platform PM | Survey (8 responses) | n/a | Median time-to-accept: 1.7h; rollback incidence: 0/8; satisfaction: 4.3/5 | Repeat survey after next Grok-5k sweep; share anonymised stats in paper. |
| 2025-10-13 | Network Ops | NetworkPolicy fixture dry-run | fixture-network-policy | “Default-deny helped contain blast radius; please keep DNS egress in fixtures.” | Ship `infra/fixtures/network_policies/default-deny.yaml`; document override process. |
| 2025-10-17 | Security Eng | Grok vs rules comparison | 00912 | “LLM patch removed an init container—regression caught by guard, rules fallback looked good.” | Regression check now blocks container removals; add semantic-check note to README. |
| 2025-10-18 | SRE On-call | Queue triage (after fixtures applied) | 01204 | “Fixtures shaved ~45 minutes off namespace/RBAC prep.” | Keep fixture target in Makefile; add pre-flight checklist. |
| 2025-10-19 | Platform Eng | Survey (12 responses) | n/a | Median time-to-accept: 1.6h; rollback incidence: 0/12; satisfaction: 4.5/5; guard metadata requested. | Guard metadata will be exposed in queue CLI; include in future UI mock-ups. |
| 2025-10-20 | Security PM | Risk review meeting | n/a | “Need clearer story on malicious manifest handling and rollback hooks.” | Document threat mitigations in paper/README; extend roadmap for rollout gating. |
| 2025-10-21 | Network Ops | Survey follow-up | n/a | “Prefer rules mode for safety-critical namespaces, Grok for bulk queue.” | Capture policy toggle requirements; integrate into future scheduling heuristics. |

## Collection Checklist

- [ ] Share latest queue snapshots with SRE/oncall rotation.
- [ ] Gather verifier notes on false positives/negatives.
- [ ] Compile anecdotal success stories for README/paper.
- [ ] Repeat operator survey quarterly and track median time-to-accept / satisfaction.
  
## Quantitative Snapshot (Oct 2025)

| Cohort | Mode(s) Reviewed | Time-to-accept (median h) | Rollbacks | Satisfaction (1–5) | Notes |
| --- | --- | --- | --- | --- | --- |
| Survey batch #1 (8 respondents) | Rules | 1.8 | 0 | 4.2 | Prioritised ingress hardening; requested fixture automation. |
| Survey batch #2 (12 respondents) | Rules & Grok | 1.6 | 0 | 4.5 | Guards seen as effective; desire guard metadata exposed in queue CLI. |
| Interview panel (4 participants) | Mixed | 1.7 | 0 | 4.3 | Prefers Grok for bulk queue once regression checks are visible. |

All questions are tracked in `docs/operator_survey.md`; please update that instrument before future surveys or interviews.
  
## Survey Snapshot (Oct 2025)

- Median time-to-accept (n=8): **1.7 hours**
- Rollback incidence: **0 / 8** (no surveyed changes rolled back)
- Operator satisfaction: **4.3 / 5** (Likert scale)
- Common requests: surface “guard applied” metadata in queue output; ship RBAC/network fixtures alongside privileged guardrails.
