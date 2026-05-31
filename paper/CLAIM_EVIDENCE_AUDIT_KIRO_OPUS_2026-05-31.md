# Superseded Claim/Evidence Audit

Audit date: 2026-05-31.
Auditor: Kiro (`claude-opus-4.8`), local static pass.
Scope: `paper/access.tex` claims against in-repo evidence.

This is a local audit artifact only. Do not upload it with the TCC packet.

## Current Status

This file is retained only to preserve the historical Kiro audit trail. Its
original long-form findings are superseded by the fixes and later verification
recorded in:

- `paper/REVISION_TRACKING.md` rows 20, 56, 57, 58, and 59.
- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`.
- `paper/RESPONSE_LETTER_CLAIM_CHECK.md`.
- `paper/SUBMISSION_GAP_REGISTER.md`.

The old P0 contradictions in the original audit are no longer the current
manuscript state.

## Issues From The Original Audit That Were Closed

- Grok latency prose was reconciled with the released latency summaries.
- The AKS cross-cluster row was corrected to match the released artifact.
- The 1,000-manifest live replay was scoped to Kind/Kubernetes 1.34.0 instead of
  conflating it with the cross-cluster AKS replay.
- The stale Grok failure denominator was removed.
- The risk-weight example was aligned with the released risk map.
- Kyverno comparison wording was narrowed to the supported fixture-compatible
  slices.
- The agent-baseline claim was framed as a guardrail/no-policy ablation proxy,
  not a named-agent head-to-head.

## Still-Open Gaps

These are not local evidence contradictions:

- TCC/EIC permission to resubmit or reopen TCC-2025-12-0666.
- Final portal-bound review after any future edit.
- Literal named-agent head-to-head only if the authors approve and fund a new
  experiment.
- Final author/scientific judgment on the novelty framing.

Use `paper/SUBMISSION_GAP_REGISTER.md` as the current risk-ranked list.
