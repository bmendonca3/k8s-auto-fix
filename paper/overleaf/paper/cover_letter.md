# Cover Letter — TCC Resubmission Draft

Dear Professor Guo,

If the editorial office permits a major-revision resubmission of manuscript
TCC-2025-12-0666, please consider our substantially revised manuscript,
"Closed-Loop Threat-Informed Remediation of Cloud-Native Kubernetes Security
Misconfigurations," for IEEE Transactions on Cloud Computing.

The revision directly addresses the reviewers' concerns about novelty,
overclaiming, reproducibility, and comparison scope. We reframed the contribution
as a proposer-independent four-gate acceptance contract for Kubernetes
remediation: trigger-policy re-check, JSON Patch application, server-side API
dry-run, and universal no-new-violation checks. We also clarified which gates
each campaign exercised and that the live replay validates dry-run and live
apply acceptance on a fixture-seeded subset, not general workload semantic
equivalence.

The current manuscript reports:
- 13,589 accepted patches out of 13,656 patched items in the full deterministic
  rules+guardrails run (99.51%; auto-fix rate 0.8646 over 15,718 detections;
  median patch size 8 operations), with 67 rejected records.
- 1,000/1,000 server-side dry-run and live apply acceptance on the fixture-seeded
  live-cluster replay.
- 4,426/5,000 accepted patches in the optional Grok/xAI proposer run (88.52%).
- A matched finite-queue replay in which static risk-priority ordering lowers
  top-50 P95 wait from 147.2 h under FIFO to 7.8 h under a shared 10-minute
  service-time fallback. This is a scheduling replay, not live operator latency.

The manuscript now includes an evidence-status table, corrected reference set,
expanded limitations, explicit artifact links, and a reproducibility package.
We do not claim finished human-operator validation; the human-in-the-loop
rotation is identified as planned future work.

Thank you for considering whether this revision can proceed under the TCC review
process.

Sincerely,

Brian Mendonca and Vijay K. Madisetti
Georgia Institute of Technology
