# Proposer & Verifier Telemetry Plan

## Goals
- Capture prompt/completion token counts per proposer request.
- Record proposer and verifier latency (wall clock + CPU) per detection.
- Persist aggregates in `data/metrics.json` and `data/risk.json` for scheduler inputs.

## Proposed Changes
1. **Proposer (`src/proposer/cli.py`)**
   - Wrap model invocations with a stopwatch; append per-attempt metrics to the patch record (`model_usage`, `latency_ms`).
   - When running in rules mode, record synthetic latency (time spent in guardrails) for parity.
   - Aggregate stats into `data/metrics_usage.json` via a new optional `--metrics-out` flag.
2. **Verifier (`src/verifier/cli.py`)**
   - Time policy checks + kubectl dry-run separately; include `latency_ms` and `kubectl_ms` fields in verification results.
   - Emit acceptance probability estimates by policy (rolling window) into `data/risk.json`.
3. **Scheduler (`src/scheduler/cli.py`)**
   - Consume measured `expected_time` and `p_accept` from `data/risk.json` instead of static priors.

## Implementation Notes
- Leverage `time.perf_counter()` for timing; store values as integers (milliseconds).
- Token counts already available in Grok responses; ensure proposer merges them into the new telemetry structure.
- Add unit tests covering metrics file emission and scheduler consumption.

## Open Questions
- Where to persist telemetry for large batch runs (SQLite vs JSON)?
- How to anonymise manifests before sharing latency/token data externally?
