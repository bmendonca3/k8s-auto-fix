# Response to Reviewers - TCC-2025-12-0666

Dear Professor Guo and Reviewers,

Thank you for the detailed reviews of our manuscript, "Closed-Loop
Threat-Guided Auto-Fixing of Kubernetes Container Security Misconfigurations."
We have substantially revised the paper to address the concerns about reference
integrity, novelty, organization, experimental scope, reproducibility, and
overclaiming. The revision keeps the contribution focused on the closed
verification loop: a candidate JSON Patch is accepted only after policy
re-check, schema validation, server-side dry-run, and no-new-violation checks.

Below we summarize the changes made in response to each reviewer. Line numbers
may shift in the final PDF, so we identify the affected sections, tables, and
artifacts.

## Response to Reviewer 1

**Concern: Several references appeared to be fabricated or could not be found.**

We agree this was a serious issue and corrected it directly. The three
problematic references were removed and replaced with verifiable sources:
Shamim et al. (IEEE SecDev 2020), Xia et al. (ICSE 2023), and Shu et al.
(CODASPY 2017). We also rechecked the citation graph so that every cited key has
a corresponding bibliography entry and every bibliography entry is cited.

Evidence: `paper/access.tex` now cites `shamim2020`, `xia2023`, and `shu2017`;
the removed placeholder keys are absent. The reference-fix audit is recorded in
`paper/REFERENCE_FIX_CHANGES.md`, and the current build has 38 cited keys and 38
defined bibliography entries.

**Concern: The paper needed a clearer contribution beyond an assembly of
existing tools.**

We revised the introduction and related work to clarify that the contribution is
not any single scanner, policy engine, or LLM proposer. The contribution is the
acceptance boundary: every generated patch must clear Kubernetes-specific
invariants before it can be accepted. The manuscript now explains this as a
closed loop over detection, proposal, verification, evidence capture, and
risk-aware scheduling.

Changes made: the Introduction now states the threat-guided framing explicitly;
Related Work is reorganized into five tool classes; and the evaluation includes
an ablation showing what happens when the domain-specific policy re-check is
removed.

**Concern: Claims needed tighter evidence and reproducibility support.**

We added an evidence-status table and strengthened artifact links throughout the
evaluation. We also reconciled the manuscript against the released CSV/JSON
artifacts so that secondary numbers match the evidence bundle.

Examples of corrections include the Grok/xAI latency values, the AKS
cross-cluster row, the live-cluster environment description, Grok failure
denominators, risk-weight examples, and pricing wording. The paper now reports
input, visible completion, and total xAI token counts for Grok/xAI runs and
directs readers to compute dollar cost against the then-current xAI pricing page,
avoiding a stale fixed dollar estimate.

## Response to Reviewer 2

**Concern: The introduction should better separate objective, motivation,
justification, and problem framing.**

We revised the introduction into labeled paragraphs for problem, approach,
contributions, and organization while retaining a standard single Introduction
section for the TCC manuscript format. This separates the motivation and
research objective from the evaluation claims, and it keeps headline numeric
results in the evaluation section where they are tied to the released artifacts.

**Concern: The paper should provide more detail on decisions regarding
alternative tools and technologies.**

We expanded Related Work and the comparison tables so the design choices are
grounded against detection-only tools, admission-time policy engines,
LLM-based repair, SRE automation, and emerging security agents. The revised
text explains that the paper does not treat detection or patch generation alone
as the acceptance boundary; the differentiating mechanism is the closed loop
that binds candidate patches to policy re-checking, schema validation,
server-side dry-run, evidence capture, and risk-aware queueing.

**Concern: The architecture figure and experimental setup needed more concrete
implementation detail.**

We expanded the architecture caption and evidence table to report evaluated
component versions, including kube-linter, Kyverno CLI, kubectl, kind,
Kubernetes, and the optional Grok/xAI proposer configuration. We also clarified
the role of server-side dry-run and the fixture-seeded live replay.

**Concern: The limitations needed to distinguish API-admission safety from full
semantic equivalence.**

We expanded the limitations section to state that the verifier establishes
policy, schema, and API-admission safety, not full workload semantic
equivalence. The revised text now explicitly calls out limitations for hostPath
rewrites, read-only root filesystem changes, dropped capabilities, LLM latency,
provider drift, and queue-replay evaluation.

**Additional author-side clarification: The manuscript should avoid overclaiming
operator-study results.**

We removed language that could imply finished human-operator validation. The
current manuscript labels the scheduler and operator A/B evidence as
deterministic or simulated replays, and it identifies the live human-in-the-loop
rotation as planned future work.

## Response to Reviewer 3

**Concern: The paper structure was nonstandard and the introduction anticipated
results too early.**

We renamed Section 1 to "Introduction" and restructured it into the standard
flow: problem, approach, contributions, and organization. We removed anticipated
evaluation numbers from the introduction; headline results now appear in the
evaluation where they can be tied to the evidence artifacts.

**Concern: Related Work was not systematic enough.**

We reorganized Related Work into five categories: detection-only tooling,
admission-time policy engines, LLM-based repair, large-scale SRE automation, and
emerging security agents. We added Polaris and LLMSecConfig to make the
comparison surface more complete.

**Concern: Tables 1 and 2 needed clearer explanation, especially because they
compare different systems under different evidence regimes.**

We revised the table captions and surrounding text to make the denominators
visible. Table 1 is a lifecycle-role comparison, not a single quantitative
leaderboard. Table 2 reports per-policy baselines only where a reusable artifact
or scanner interface allowed a bounded replay, so its rows intentionally have
different denominators and evidence scopes. The response and manuscript now
avoid implying a like-for-like benchmark when the available artifacts do not
support one.

**Concern: Section 3 needed stronger formalization and clearer
research-question rationale.**

We revised the system-design section to define the manifest, detection, patch,
and acceptance predicate more explicitly. We also added false-positive handling,
defined an "attempt" and retry budget, and rewrote the research questions so
that each has a rationale and a separately stated finding.

**Concern: Section 5 read like a product manual.**

We condensed the implementation-status material and merged the detection-record
and test-evidence discussion into a shorter section. We removed low-level
mechanics that were not needed for the paper argument while preserving the
artifact references needed for reproducibility.

**Concern: The work should be compared experimentally against agent-based
remediation systems.**

We partially addressed this with an ablation, but we do not overstate it as a
named-agent head-to-head. The revised evaluation adds a "Domain-invariant
enforcement vs. an agent-style acceptance regime" analysis. Holding candidate
patches fixed, removing the domain-specific policy re-check increases acceptance
from 78.9% (15/19) to 100% (19/19), but four patches are accepted while still
violating the property they were meant to fix. This isolates the mechanism the
paper contributes: Kubernetes-specific invariant re-checking plus server-side
dry-run as the acceptance boundary.

We explicitly state the limitation. Aardvark is a closed beta without a public
interface, and we could not execute a named third-party agent over the full
corpus under the same verifier protocol during this revision. We therefore
report the ablation as guardrail evidence and defer a like-for-like run against
Aardvark or KubeIntellect to future work rather than inventing unsupported
comparison numbers.

**Concern: The novelty argument should be sharper than a tool-combination
claim.**

We strengthened the positioning throughout the manuscript: detection and patch
generation are not the acceptance boundary; the contribution is the closed loop
that binds generated patches to policy re-check, schema validation,
server-side dry-run, evidence capture, and risk-aware queueing. We recognize
that the final assessment of novelty is an editorial and scientific judgment, so
the manuscript now presents the mechanism and its evidence more directly instead
of relying on broad claims.

## Cross-Cutting Revisions

- Corrected the reference set and citation graph.
- Added an evidence-status table and denominator table.
- Reconciled secondary numeric claims against released artifacts.
- Corrected Grok/xAI proposer and verifier latency values.
- Corrected the AKS cross-cluster acceptance row to match the checked-in
  artifact.
- Scoped the 1,000-manifest live replay to the fixture-seeded Kind/Kubernetes
  evaluation environment.
- Removed the unsupported Grok failure denominator and reported the failure
  taxonomy as concrete counts.
- Removed the fixed Grok/xAI dollar estimate and retained reproducible token
  counts plus a pricing citation.
- Scoped Kyverno webhook and scheduler claims to the exact replay evidence.
- Clarified that operator A/B evidence is simulated or replay-based, not a
  finished live study.
- Synchronized the standalone manuscript source and Overleaf package.

## Remaining Scope Limitations

Several issues remain outside what can be honestly resolved without new external
state or additional author-approved experiments:

- A literal head-to-head experiment against Aardvark or KubeIntellect remains
  future work because Aardvark is not publicly runnable and a KubeIntellect run
  requires runnable code, budget, and an agreed protocol.
- The current verification guarantees policy, schema, and API-admission safety;
  it does not prove full workload semantic equivalence.
- The operator A/B and scheduler results are deterministic or simulated replays
  and will be paired with a future live human-in-the-loop rotation.
- The manuscript should be resubmitted only if the editorial office confirms that
  a major-revision resubmission is permitted.

We appreciate the reviewers' feedback. The revised manuscript is narrower,
better evidenced, and more explicit about what has been demonstrated versus what
remains future work.

Sincerely,

Brian Mendonca and V. K. Madisetti

Georgia Institute of Technology
