# Operator Feedback Instrument

This appendix documents the survey and interview prompts used to gather qualitative feedback from SRE, platform, security, and network operators.

## Survey Structure

1. **Role & team** (checkbox; multiple selections allowed).
2. **Pipeline mode evaluated** (`rules`, `grok`, `both`).
3. **Time-to-accept** (numeric hours; respondents asked to estimate mean across reviewed manifests).
4. **Rollback incidence** (integer count of rollbacks triggered by the auto-fix).
5. **Confidence rating** (Likert 1–5 where 5 == "very confident").
6. **Perceived risk reduction** (free-form text).
7. **Guardrail usefulness** (Likert 1–5).
8. **Open feedback** (free-form text capturing requests, concerns, or anecdotal stories).

Interviews followed the same flow with additional probing on:

- Situational context (incident retro, routine queue triage, emergency fix).
- Comparison between deterministic rules vs Grok runs for similar manifests.
- Requirements for wider deployment (audit logging, approval workflows, rollback hooks).

## Collection Protocol

- Survey distributed after each weekly batch review via the on-call Slack channel (Forms link).
- Interviews scheduled within 24 hours of the survey for volunteers (15-minute slot).
- Responses anonymised; only role and pipeline mode are reported publicly.
- Aggregated metrics (time-to-accept, rollback incidence, satisfaction) appear in `docs/qualitative_feedback.md` and paper/access.tex.

Please append new questions or notes here before sending the survey to operators so the record stays current.
