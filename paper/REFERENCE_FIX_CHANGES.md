# Reference Integrity Change Summary

Date: 2026-05-30.
Author: `bmendonca3`.
Manuscript: TCC-2025-12-0666.

This is a local historical summary only. Do not upload it with the TCC packet.
For the current source-verification state, use
`paper/SOURCE_VERIFICATION_MCP_2026-05-31.md` and
`paper/source_verification_mcp_2026-05-31.json`.

## Fabricated References Removed

Reviewer 1 flagged references that could not be found. The hallucinated entries
were removed and replaced with real sources:

| Old key | Current key | Replacement source |
|---|---|---|
| `b1` | `shamim2020` | Islam Shamim, Bhuiyan, and Rahman, "XI Commandments of Kubernetes Security," SecDev 2020, DOI `10.1109/SecDev45635.2020.00025`. |
| `b2` | `xia2023` | Xia, Wei, and Zhang, "Automated Program Repair in the Era of Large Pre-trained Language Models," ICSE 2023, DOI `10.1109/ICSE48619.2023.00129`. |
| `b3` | `shu2017` | Shu, Gu, and Enck, "A Study of Security Vulnerabilities on Docker Hub," CODASPY 2017, DOI `10.1145/3029806.3029832`. |

The generic `b1`/`b2`/`b3` keys were renamed to descriptive keys and the in-text
citations were updated with the bibliography definitions.

## Additional Reference Hardening

- The OpenAI agent citation was moved from a generic homepage to the specific
  Codex Security / former Aardvark source now tracked as `aardvark`.
- `kubeintellect` author metadata was corrected.
- Later precision passes added or corrected metadata for KubeLLM, GLITCH,
  RepairAgent, and Minna et al.
- The current active bibliography is 38 cited keys / 38 `\bibitem`s with 0
  cited-but-undefined keys and 0 uncited bibitems.

## Current Source Verification

All active sources are now covered by the current local verification record.
The authoritative current summary is:

- `paper/SOURCE_VERIFICATION_MCP_2026-05-31.md`
- `paper/source_verification_mcp_2026-05-31.json`
- `paper/REVISION_TRACKING.md` rows 56-59

Keep this file only as the historical record of the original reference-integrity
fix.
