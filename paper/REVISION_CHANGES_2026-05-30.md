# Major-Revision Structural Changes — TCC-2025-12-0666

**File changed:** `paper/access.tex` (authoritative IEEEtran submission source)
**Date:** 2026-05-30
**Author:** bmendonca3
**Reason:** Address the still-open TCC reviewer feedback after the reference-integrity
fix (`REFERENCE_FIX_CHANGES.md`). Reviewer 1 = Major Revision, Reviewer 2 = Minor
Revision, Reviewer 3 = Reject. Decision was Reject; co-author (V. Madisetti) has
asked the EIC whether a major-revision resubmission is permitted.

All edits are structural/prose reorganizations grounded in the existing text and
released artifacts. No evaluation numbers, tables, or methods were changed, and no
new experimental results or citations were fabricated.

---

## Changes

1. **Section 1 renamed `Importance of the Problem` -> `Introduction`** (R3).
   Added `\label{sec:introduction}`. Standard IEEE structure: context ->
   `Problem` -> `Approach` -> itemized `Contributions` -> `Organization`.

2. **Anticipated results removed from the introduction** (R2, R3). The old
   Contributions paragraph front-loaded 1,000/1,000, 7.9x, etc. The intro is now
   result-number-free (verified by grep); headline numbers live only in the
   evaluation.

3. **Explicit novelty + threat-guided tie-in** (R1, R3). The `Approach` paragraph
   defines "threat-guided" concretely in two pipeline-anchored senses: (i) the
   verifier's security invariants must clear the detected threat before acceptance,
   and (ii) the scheduler orders work by an exploit-weighted risk score (KEV/EPSS).
   "Verification, not the candidate generator, is the acceptance boundary."

4. **Related Work made systematic** (R3). Added `\label{sec:related-work}` and
   reorganized into five labeled categories: detection-only tooling, admission-time
   engines, LLM-based repair, large-scale SRE automation, emerging agents. Folded in
   **Polaris** (`\cite{polaris}`, new verified bibitem) and **LLMSecConfig**
   (`\cite{llmsecconfig}`, already in bib but previously uncited). Removed the
   duplicated problem-statement paragraph (now in the intro).

5. **Section 3 tightened** (R3): formal notation (manifest `m`, detection
   `d=(m,pi,v)`, patch `delta`, acceptance predicate `Acc`), an explicit
   **false-positive handling** paragraph (JSON Pointer existence checks + policy
   re-check; unresolved -> human review), and an explicit **definition of an
   "attempt"** plus the retry budget.

6. **Research questions rewritten** with a per-RQ `Rationale` + separated `Finding`
   (R3 said the RQ rationale was unclear). Numbers unchanged.

7. **Section 5 ("Implementation Status and Evidence") condensed** (R3 "reads like a
   product manual"). Merged `Sample Detection Record` + `Test Evidence` into one
   `Detection Records and Test Evidence` subsection; dropped the verbose JSON dump
   and make-target mechanics while keeping the record schema and property-based-test
   evidence.

8. **Architecture figure now reports component versions** (R2). Caption lists
   kube-linter 0.7.6, Kyverno CLI, kubectl 1.34.1, kind 0.30.0, Kubernetes 1.34.0,
   grok-4.3, cross-referencing Table `tab:evidence`.

9. **Limitations expanded** (R2) with intrinsic **LLM-technology limits** (version
   drift, hallucination, cost/throughput floor; single-vendor evidence) and
   **experimental-validity** bounds (simulated A/B, replay-only cross-cloud, no
   head-to-head agent experiment yet).

10. **Orphaned floats given in-text references** (R3 "tables without sufficient
    explanation"): `tab:denominators` and `fig:bandit-pseudocode` now have first
    references; re-cited `kubectl_reference` after the Related Work rewrite.

11. **Section labels added** (`sec:limitations`, `sec:discussion`) so the new intro
    and cross-section references resolve.

---

## Verification

- `tectonic -X compile access.tex` succeeds: **17 pages**, **0 undefined
  references/citations**. Hbox warnings: 118 total (2 overfull, 116 underfull),
  all cosmetic line-breaking; none affect correctness. (Stale earlier draft of
  this line read "16 pages / 2 hboxes"; corrected 2026-05-30 14:09 MST after a clean reverify.)
- Citation graph: all 20 cited keys resolve; no key cited-but-undefined.
- Byline unchanged (Brian Mendonca and Vijay K. Madisetti); `bmendonca3` governs
  GitHub/commit authorship, not the manuscript byline.

---

## NOT done here (needs co-author decision; not auto-fixable)

- **R3's experimental head-to-head vs. Aardvark / KubeIntellect.** Aardvark is a
  closed beta with no public interface; KubeIntellect would require a real
  execution run on our corpora. This is scaffolded as a concrete future-work axis
  and positioned honestly in Related Work + Limitations, but no comparison numbers
  were invented. Running KubeIntellect (or an agent stand-in) on the corpora is a
  real-experiment decision for the authors.
- **R3's deeper "novelty is just a combination of existing tools" rebuttal.** The
  contribution/positioning text is sharpened, but the substantive argument that the
  closed loop is more than a tool chain is an intellectual call for the authors.
- **Procedural:** resubmission as a major revision depends on the EIC's reply to
  V. Madisetti's request; the decision of record is still Reject.

---

## Update — agent-baseline evidence (item 3), no fabrication

Attempted a real LLM agent run to produce a head-to-head vs. an agent-style
remediation regime. Blocked by external state:
- Aardvark: closed beta, no public interface/API — not runnable.
- XAI/Grok endpoint returned **HTTP 403 "used all available credits"**; no other
  LLM endpoint (OpenAI, etc.) is configured. A fresh corpus-scale agent run is not
  fundable in this session.

Instead of fabricating named-tool numbers (the exact failure R1 flagged), I added a
real, no-new-API analysis in the evaluation (after the patch-escape case study):

- Reframed the existing **no-policy ablation** (`data/ablation/verifier_gate_metrics.json`)
  as the experiment R3 asked for: an agent-style acceptance regime that takes a
  syntactically valid, scanner-clean LLM patch without re-checking domain invariants.
- Real measured result: acceptance 78.9% (15/19) -> 100% (19/19) when the
  domain-specific policy re-check is removed, but no-new-violations stays at 78.9%,
  so **4 patches escape** (real ids 007/012/013/016) spanning distinct invariant
  families: incomplete `SYS_ADMIN` capability hardening, two incomplete
  cpu/memory-requirement fixes, and a `hostPath`->`emptyDir` rewrite that still
  violates the host-mount policy.
- Stated the proxy limitation explicitly: these counts are NOT attributed to a named
  competing agent; a like-for-like run against a named agent on identical manifests
  remains the Section "Discussion and Future Work" item.

Compiles: **17 pages, 0 undefined references**.

### Still requires a co-author decision / external change
- A literal named experimental head-to-head vs. Aardvark/KubeIntellect needs either
  funded API access (to run an agent over the corpus) or KubeIntellect's runnable
  code, plus the authors' sign-off on the experimental protocol. Not auto-fixable.
