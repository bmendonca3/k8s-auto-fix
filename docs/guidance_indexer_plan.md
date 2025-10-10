# Guidance Indexer Automation Plan

## Current State
- Policy guidance snippets live in `docs/policy_guidance/raw/*.md` and are manually refreshed.
- `scripts/build_policy_guidance_index.py` assembles `docs/policy_guidance/index.json` for proposer retrieval.

## Automation Proposal
1. **Source discovery**
   - Track upstream sources (CNCF Pod Security Standards, CIS Benchmarks, Kyverno policy catalog).
   - Maintain a manifest file (`docs/policy_guidance/sources.yaml`) with URLs, version hints, and parsing rules.
2. **Fetcher script**
   - New script `scripts/refresh_guidance.py` that:
     - Downloads source documents (HTTP or git).
     - Extracts relevant sections via regex / markdown headings.
     - Writes normalised markdown files into `docs/policy_guidance/raw/`.
3. **Versioning & validation**
   - Store fetch metadata (source URL, commit hash, retrieved_at) inside each raw file header.
   - Extend existing tests to fail if the index is older than N days.
4. **CI hook**
   - Add make target `make guidance-refresh` and document usage.
   - Optional: integrate with scheduled CI job to raise PRs when upstream guidance changes.

## Next Steps
- Draft `sources.yaml` with priority references (Pod Security Standards v1.27, CIS Kubernetes v1.24).
- Prototype extractor for one source to validate the approach.
