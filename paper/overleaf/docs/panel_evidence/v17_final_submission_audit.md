# V17 Final Submission Audit

## Scope

V17 is the final reviewer-risk reduction pass after the V14-V16 PDF audits. The
goal was not to restructure the manuscript, but to remove visible reviewer-risk
issues while preserving the recovered IEEEtran/TCC lineage.

## Source and PDF locations

- Source: `paper/access.tex`
- Root table include: `grok_failures_table.tex`
- Paper-local table include: `paper/grok_failures_table.tex`
- Built PDF: `main.pdf`
- Build artifact: `build/v17/main.pdf`

## Fixes carried into V17

- Narrowed detector-evaluation language so the synthetic hold-out does not imply
  real-world detector recall.
- Clarified scheduler wording from broader superiority claims to comparable
  acceptance/risk-closure language with explicitly labeled FIFO comparisons.
- Removed the misleading Kyverno `+10.92` direct-comparison framing.
- Replaced ambiguous `baseline top-risk` wording with `bandit top-risk`.
- Separated dry-run/API admissibility from the "no new violation" policy-gate
  claim.
- Removed P50/P95 latency rows from the Grok failure table and made latency
  sourcing explicit elsewhere.
- Fixed the conclusion mismatch by tying 93.54% to the extended 5k rules
  snapshot in Table 10.
- Renamed Table 14's disabled-gate ablation from `No-schema` to `No-dry-run`
  where the disabled gate is kubectl.
- Changed Table 4 from `single-operation fixes` to deterministic JSON Patch
  arrays.
- Labeled the scheduler comparison as `42.97 bandit vs. 43.40 FIFO`.
- Reconciled Figure 5 and Section 4.10 around 247 scheduler-arm assignments over
  a 152-item toy queue.
- Labeled Table 11's LLM-5k row as using a 200-trace latency sample.
- Replaced raw truncated Table 7 failures with categorical failure labels.
- Repaired the page 7/page 8 P95 sentence break.
- Removed the final visible cross-reference nit: the conclusion no longer points
  the 1,000/1,000 live-cluster claim to Table 11.

## Build verification

Command:

```sh
tectonic --keep-logs --outdir build/v17 main.tex
```

Result:

- Built successfully.
- Extracted text: `docs/panel_evidence/pdf_texts/v17_built.txt`
- Rendered page images:
  - `docs/panel_evidence/images/v17_pages/v17_page_07.png`
  - `docs/panel_evidence/images/v17_pages/v17_page_08.png`
  - `docs/panel_evidence/images/v17_pages/v17_page_13.png`
  - `docs/panel_evidence/images/v17_pages/v17_page_14.png`
- PDF length: 14 pages.
- Extracted word count: 9,623 words.

## Text and log checks

The V17 scan found zero matches for unresolved-reference and stale-risk markers:

- `Figure ??`
- `Table ??`
- `undefined citation`
- `missing file`
- `Table 11, data/live_cluster`
- `single-operation`
- `No-schema`
- `5k supported corpus`
- `42.97 vs`
- `247 simulated queue`
- `152-task toy`
- `FIFO's 0.71`
- `failure causes and latencies`
- `P50 Latency`
- `P95 Latency`
- `baseline top-risk`
- `+10.92`
- `closes slightly more risk`
- `real-world performance is validated`
- `ensuring no new violations`

Build-log check:

- LaTeX errors: 0
- Undefined control sequence: 0
- Undefined references: 0
- Undefined citations: 0
- Missing-file markers: 0
- Cross-reference rerun warning: 0

Residual build warnings are layout/font warnings only, including familiar
underfull/overfull boxes, an `algorithmic.sty` UTF-8 replacement warning, and
the known `TUppl.fd` font-substitution notice.

## External PDF audit

The final uploaded GPT audit response is saved at:

- `docs/panel_evidence/chatgpt_deep_pdf_audit_v17_response.md`

It reports:

- The live-cluster 1,000/1,000 conclusion claim no longer points to Table 11.
- All eight V16-focused items remain resolved.
- No visible PDF submission blockers.
- Final verdict: `SUBMIT`.

The audit also notes that external artifacts remain not inspectable from the PDF,
which is expected for a PDF-only review and does not contradict the local
artifact-path checks.

## Reference spot-check

The final pass also checked the citation URLs most likely to draw reviewer
scrutiny:

- Kubernetes seccomp: HTTP 200.
- CISA KEV catalog: HTTP 200.
- FIRST EPSS: HTTP 200.
- Trivy documentation: redirects and resolves to HTTP 200.
- Grype repository: HTTP 200.
- kube-linter documentation: HTTP 200 at the cited `docs.kubelinter.io` URL.
- NeurIPS fairness paper: the current NeurIPS landing page redirects and resolves
  to HTTP 200; the present bibliography entry does not include the old bad URL.
- OpenAI Codex Security: web search confirms the OpenAI page exists; scripted
  `curl -I` returns HTTP 403, so this is recorded as scripted-access friction
  rather than a broken citation.
- NVD: scripted `curl -I` returns HTTP 403; NIST's public NVD page is live in
  web search, so this is recorded as scripted-access friction rather than a
  broken citation.
