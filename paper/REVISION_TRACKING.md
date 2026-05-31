# Revision Tracking Ledger — TCC-2025-12-0666

Single source of truth for revision work on `paper/access.tex`
("Closed-Loop Threat-Guided Auto-Fixing of Kubernetes Container Security
Misconfigurations"). Every row is verified against the current source/compile, not
against prior chat or changelog prose. Authorship/commit identity: `bmendonca3`;
manuscript byline left unchanged.

## Authoritative compile facts (reverified 2026-05-30 14:10 MST)

- Engine: bundled `./tectonic` 0.15.0, `-X compile access.tex --outdir /tmp/k8s_verify`.
- Result: **17 pages**, **0 undefined references/citations**, exit 0.
- Hbox warnings: **118 total (2 overfull, 116 underfull)** — all cosmetic
  line-breaking; none affect correctness or references.
- Citation graph: 21 keys cited, 29 `\bibitem` defined, **0 cited-but-undefined**.
- Byline: `\author{Brian Mendonca and Vijay K. Madisetti, ...}` — byte-identical to
  HEAD (verified by content diff of the `\author` block).

## Work-item ledger

| # | Date/time (America/Phoenix) | Reviewer | Item | Status | Authoritative evidence | Verification gap |
|---|---|---|---|---|---|---|
| 1 | 2026-05-30 14:09 MST | R1 | Replace fabricated refs [26]/[27]/[28] | done | `b1/b2/b3` keys absent (grep count 0); `shamim2020`/`xia2023`/`shu2017` bibitems at access.tex:1013/1015/1017; DOIs listed in REFERENCE_FIX_CHANGES.md | DOIs not re-fetched online this pass (no network verification re-run) |
| 2 | 2026-05-30 14:09 MST | R3/R2 | Section 1 -> standard Introduction; no anticipated results | done | `\section{Introduction}` access.tex:111, `\label{sec:introduction}` :112; grep for result numbers in lines 111-135 returns NONE | none |
| 3 | 2026-05-30 14:09 MST | R1/R3 | Explicit contribution + threat-guided tie-in | done | itemized Contributions + "threat-guided" at access.tex:119,125 | none |
| 4 | 2026-05-30 14:09 MST | R3 | Related Work made systematic (5 labeled categories) | done | `\label{sec:related-work}` :187; five numbered category headings in Related Work | none |
| 5 | 2026-05-30 14:09 MST | R3 | Add Polaris + LLMSecConfig | done | `\cite{polaris}` :191 + `\bibitem{polaris}` :947; `\cite{llmsecconfig}` :197 + `\bibitem{llmsecconfig}` :983 | Polaris cited as GitHub repo (not peer-reviewed); acceptable but note for editor |
| 6 | 2026-05-30 14:09 MST | R3 | Tighten Section 3 (notation, false-positives, "attempts", RQ rationale) | done | formal notation + false-positive + attempts paragraphs in System Design; 4x `Rationale:` and 4x `Finding:` in RQ block | none |
| 7 | 2026-05-30 14:09 MST | R3 | Condense manual-style Section 5 | done | merged `\subsection{Detection Records and Test Evidence}` access.tex:428; old "Sample Detection Record"/"Test Evidence" headings absent | subjective ("manual-style" is a judgment call); reviewer may still want more cuts |
| 8 | 2026-05-30 14:09 MST | R2 | Architecture figure with component versions | done | "Evaluated component versions" in fig caption access.tex:383 (kube-linter 0.7.6, kubectl 1.34.1, kind 0.30.0, k8s 1.34.0, grok-4.3) | versions in caption text, not redrawn into the figure boxes |
| 9 | 2026-05-30 14:09 MST | R2 | Expanded LLM/experiment limitations | done | LLM-technology + experimental-validity additions in Limitations section | none |
| 10 | 2026-05-30 14:09 MST | R3 | Figure/table placement; orphaned floats referenced | done | `tab:denominators` and `fig:bandit-pseudocode` now have in-text refs; 0 undefined refs in compile | float page-placement not hand-optimized; LaTeX auto-places |
| 11 | 2026-05-30 14:09 MST | R3 | Agent-baseline experimental evidence (reframe of no-policy ablation) | **mitigated / OPEN** | "Domain-invariant enforcement vs. an agent-style acceptance regime" access.tex:821; numbers match `data/ablation/verifier_gate_metrics.json` exactly (no_policy: acc 1.0, nnv 0.789474, escapes 007/012/013/016) | NOT a head-to-head vs a named agent; it is a guardrail-ablation proxy |
| 12 | 2026-05-30 14:09 MST | R3 | Literal experimental head-to-head vs Aardvark / KubeIntellect | **OPEN (blocked)** | Aardvark = closed beta, no public interface; XAI/Grok API returned HTTP 403 "used all available credits"; no other LLM endpoint configured | needs funded API access or KubeIntellect runnable code + author sign-off on protocol |
| 13 | 2026-05-30 14:09 MST | R3 | "Novelty is just a tool-combination" rebuttal | **OPEN** | positioning text sharpened in Related Work/Introduction | substantive scientific argument requires author (Madisetti) decision; not auto-fixable |
| 14 | 2026-05-30 14:09 MST | procedural | Resubmission allowed as major revision? | **OPEN (external)** | decision of record = Reject (TCC email); co-author asked EIC whether major-revision resubmission is permitted | awaiting EIC reply |

## Notes / corrections to prior logs

- REVISION_CHANGES_2026-05-30.md originally stated "16 pages / 2 cosmetic hboxes" in
  its verification block. Corrected 2026-05-30 14:10 MST to the reverified "17 pages / 118 hbox
  (2 overfull, 116 underfull)". The later "Compiles: 17 pages" line in that same
  file was already correct.
- No fabricated experiment numbers, results, or citations were introduced. The
  agent-comparison evidence (row 11) is the real no-policy ablation, not invented.
- An earlier exploratory harness (`scripts/run_agent_baseline.py`) and its outputs
  were removed in-session because they duplicated `scripts/run_verifier_gate_ablation.py`
  and produced a 24-record number that did not match the paper's cited 19-record
  ablation. Confirmed absent: `ls scripts | grep agent_baseline` -> none.
