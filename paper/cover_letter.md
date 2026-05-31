# Cover Letter — TCC Resubmission Draft

Dear Professor Guo,

If the editorial office permits a major-revision resubmission of manuscript
TCC-2025-12-0666, please consider our substantially revised manuscript,
"Closed-Loop Threat-Guided Auto-Fixing of Kubernetes Container Security
Misconfigurations," for IEEE Transactions on Cloud Computing.

The revision directly addresses the reviewers' concerns about novelty,
overclaiming, reproducibility, and comparison scope. We reframed the contribution
as a closed verification loop for Kubernetes remediation: each candidate JSON
Patch is accepted only after policy re-check, schema validation, server-side
dry-run, and universal no-new-violation gates. We also clarified that the live
replay validates dry-run/apply acceptance on a fixture-seeded subset, not general
workload semantic equivalence.

The current manuscript reports:
- 13,338 accepted patches out of 13,373 patched items in the full deterministic
  rules+guardrails run (99.74%; auto-fix rate 0.8486 over 15,718 detections).
- 1,000/1,000 dry-run/apply acceptance with zero rollbacks on the fixture-seeded
  live-cluster replay.
- 4,426/5,000 accepted patches in the optional Grok/xAI proposer run (88.52%).
- A risk-aware scheduler replay that lowers top-risk P95 wait time from 102.3 h
  under FIFO to 13.0 h while keeping all scheduler and operator results clearly
  labeled as replay-based or simulated.

The manuscript now includes an evidence-status table, corrected reference set,
expanded limitations, explicit artifact links, and a reproducibility package.
We do not claim finished human-operator validation; the human-in-the-loop rotation
is identified as planned future work.

Thank you for considering whether this revision can proceed under the TCC review
process.

Sincerely,

Brian Mendonca and Vijay K. Madisetti
Georgia Institute of Technology
