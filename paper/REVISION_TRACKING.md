# Revision Tracking Ledger — TCC-2025-12-0666

Single source of truth for revision work on `paper/access.tex`
("Closed-Loop Threat-Guided Auto-Fixing of Kubernetes Container Security
Misconfigurations"). Every row is verified against the current source/compile, not
against prior chat or changelog prose. Authorship/commit identity: `bmendonca3`;
manuscript byline left unchanged.

## Authoritative compile facts (reverified 2026-05-30 18:39 MST)

- Engine: bundled `./tectonic` 0.15.0, `-X compile access.tex --outdir /tmp/k8s_tcc_build --keep-logs`.
- Result: **17 pages**, **0 undefined references/citations**, exit 0. Overleaf package compile also exits 0 via `../tectonic -X compile main.tex --outdir /tmp/k8s_overleaf_build --keep-logs`.
- Box warnings: **0 overfull**, 117 underfull hboxes, 2 underfull vboxes — all
  cosmetic line-breaking; none affect correctness or references.
- Citation graph: 29 keys cited, 29 `\bibitem` defined, **0 cited-but-undefined**
  and **0 uncited bibitems**.
- PDF image review: rendered 17 page PNGs to `/tmp/k8s_pdf_review_final3/pages`
  and contact sheets to `/tmp/k8s_pdf_review_final3/sheets`; visual pass and
  text-block margin scan found no margin overflow, missing figures, or incoherent
  overlaps. Main and Overleaf PDFs have identical extracted-text and rendered-page hashes.
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
| 15 | 2026-05-30 18:29 MST | panel | Cover letter venue mismatch and unsupported operator-study claim | done | `paper/cover_letter.md` rewritten for TCC resubmission gate; no `IEEE Access`, `4.3/5`, or completed live-operator claim remains | do not submit until EIC permission is received |
| 16 | 2026-05-30 18:29 MST | panel | Grok failure table latency rows used wrong source | done | `paper/grok_failures_table.tex` now reports failure causes only; latency prose now cites `grok200_latency_summary.csv` and `verified_grok200_latency_summary.csv` values | full Grok-5k latency bundle still future work, as stated in paper |
| 17 | 2026-05-30 18:29 MST | panel | Patch-minimality target appeared to conflict with full-corpus median 9 | done | Targets paragraph now scopes <=6 to curated rules-mode smoke sweeps and states full-corpus median patch length 9 separately | none |
| 18 | 2026-05-30 18:29 MST | panel | Bibliography hygiene | done | `references.bib` patch marker removed; citation graph now 29 cited / 29 bibitems / 0 uncited / 0 missing | DOI re-fetch not repeated in this pass |
| 19 | 2026-05-30 18:39 MST | panel | Source/PDF and Overleaf package synchronization | done | `paper/access.pdf` copied from `/tmp/k8s_tcc_build/access.pdf`; `paper/overleaf/main.pdf` copied from `/tmp/k8s_overleaf_build/main.pdf`; both compiles output 17 pages with no overfull/ref/citation/map-file errors | ScholarOne upload behavior still depends on portal requirements |
| 20 | 2026-05-30 18:39 MST | panel | Claim/evidence reconciliation pass after Kiro/Opus audit | done | Corrected AKS cross-cluster row to 200/200, scoped the 1k live replay to Kind/Kubernetes 1.34.0, removed unsupported Grok failure denominator, fixed risk-weight examples, scoped Kyverno webhook >98%, removed unsupported FIFO toy-queue comparison, and narrowed 78.9% vs 67.98% to directional evidence | `paper/CLAIM_EVIDENCE_AUDIT_KIRO_OPUS_2026-05-31.md` is an untracked audit artifact, not submission content |
| 21 | 2026-05-30 18:39 MST | panel | Final rendered-layout image review | done | `/tmp/k8s_pdf_review_final3/pages` and `/tmp/k8s_pdf_review_final3/sheets`; text-block margins remain within page bounds on all 17 pages; page 9 failure table and pages 13--17 reviewed visually | page 17 has large whitespace between bios but no overlap or overflow |

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
