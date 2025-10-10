# Retrieval-Augmented Prompting (RAG) Roadmap

## Objective
Outline post-release exploration for augmenting proposer prompts with dynamic context drawn from policy repositories, historical failures, and infrastructure inventories.

## Phases
1. **Scoping**
   - Inventory candidate corpora (Kyverno policies, failure summaries, cluster inventory snapshots).
   - Define evaluation metrics (retry reduction, acceptance uplift, token overhead).
2. **Prototype**
   - Build lightweight retriever (faiss / sqlite full-text) keyed by policy ID + manifest features.
   - Inject retrieved snippets into proposer retries; track impact on Grok and vendor modes.
3. **Hardening**
   - Add guardrails to prevent stale or conflicting guidance.
   - Measure latency impact and amortise retrieval across batch runs.
4. **Doc & Handoff**
   - Summarise findings for paper/presentation; decide whether to productionise.

## Dependencies
- Telemetry instrumentation (tokens + latency) to quantify ROI.
- Guidance indexer automation to keep corpus fresh.

## Status
- Not in scope for current release; document and revisit after telemetry work.
