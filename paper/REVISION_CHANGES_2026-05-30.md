# Major-Revision Change Summary

Date: 2026-05-30.
Author: `bmendonca3`.
Manuscript: TCC-2025-12-0666.

This is a local historical summary only. Do not upload it with the TCC packet.
For the current source of truth, use `paper/REVISION_TRACKING.md`.

## Main Changes Made

- Reworked Section 1 into a standard `Introduction` with problem, approach,
  contributions, and organization.
- Removed anticipated result numbers from the introduction and left headline
  numbers in the evaluation.
- Sharpened the threat-guided novelty claim around verification as the
  acceptance boundary and risk-aware scheduling as the prioritization boundary.
- Reorganized Related Work into systematic categories and added/retained real
  Kubernetes, LLM-repair, SRE, and agent references.
- Tightened System Design with notation, false-positive handling, attempt
  definition, and retry-budget prose.
- Rewrote research questions so each has rationale and finding text.
- Condensed implementation/evidence prose that read like a product manual.
- Added evaluated component versions to the architecture figure caption.
- Expanded limitations around LLM drift, single-vendor evidence, replay limits,
  and missing named-agent head-to-head experiments.
- Added/verified in-text references for previously orphaned floats and labels.

## Later Updates That Supersede This Snapshot

- Citation graph later grew from the old 20/29-key state to the current 38-key
  hardened bibliography.
- The original agent-baseline note remains only a guardrail-ablation proxy; it is
  not a literal Aardvark/KubeIntellect comparison.
- Current build/source/source-verification status is recorded in
  `paper/REVISION_TRACKING.md` and
  `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`.

## Current Hard Gates

- Do not submit until TCC/EIC permission is confirmed.
- Re-run the portal checklist and response-letter claim check after any future
  edit.
- Keep this file local-only; it is not part of the upload packet.
