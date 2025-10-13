# k8s-auto-fix

`k8s-auto-fix` is a closed-loop pipeline that detects Kubernetes misconfigurations, proposes JSON patches, verifies them against guardrails, and schedules accepted fixes. It supports deterministic rules as well as Grok and OpenAI-compatible LLM modes, and underpins the accompanying research paper.

## Key features
- End-to-end detector -> proposer -> verifier -> risk -> scheduler -> queue workflow with reproducible CLI entry points.
- Switchable proposer backends (rules, Grok, vendor, vLLM) with semantic regression checks and targeted policy guidance.
- Verifier integrates kube-linter, Kyverno, `kubectl apply --dry-run=server`, and bespoke safety gates before a patch is accepted.
- Metrics bundles, benchmarks, and reproducibility scripts that back the paper's evaluation.

## Getting started
```bash
pip install -r requirements.txt    # dependencies (see make setup)
make fixtures                      # seed RBAC/NetworkPolicy fixtures
make kind-up                       # optional: bring up the verification cluster
make e2e                           # run detector -> proposer -> verifier -> risk -> scheduler -> queue
```

## Workflow at a glance
| Stage | Command | Output |
| ----- | ------- | ------ |
| Detect misconfigurations | `python -m src.detector.cli --in data/manifests --out data/detections.json --policies-dir data/policies/kyverno --jobs 4` | `data/detections.json` |
| Generate patches | `python -m src.proposer.cli --detections data/detections_sampled.json --out data/patches.json --config configs/run.yaml --jobs 4` | `data/patches.json` |
| Verify patches | `python -m src.verifier.cli --patches data/patches.json --detections data/detections_sampled.json --out data/verified.json --include-errors --require-kubectl --enable-rescan --policies-dir data/policies/kyverno --jobs 4` | `data/verified.json` |
| Compute risk | `make cti && python -m src.risk.cli --detections data/detections_sampled.json --out data/risk.json --epss-csv data/epss.csv --kev-json data/kev.json` | `data/risk.json` |
| Schedule fixes | `python -m src.scheduler.cli --verified data/verified.json --detections data/detections_sampled.json --risk data/risk.json --out data/schedule.json` | `data/schedule.json` |
| Queue accepted patches | `python -m src.scheduler.queue_cli enqueue --db data/queue.db --verified data/verified.json --detections data/detections_sampled.json --risk data/risk.json` | `data/queue.db` |

Benchmark helpers (`make benchmark-grok200`, `make benchmark-full`, `make benchmark-scheduler`) and aggregation commands (`python -m src.eval.metrics`, `make summarize-failures`) mirror the evaluation in the paper.

## Components
- **Detector (`src/detector`)** wraps kube-linter and Kyverno, applies extra guards (hostPath, hostPort, CronJob traversal), and emits rigid detections.
- **Proposer (`src/proposer`)** merges rule-based fixes with LLM output, validates JSON Patch structure, and blocks destructive edits (container or volume removal, service-account regressions).
- **Verifier (`src/verifier`)** rechecks policy conformance, performs `kubectl` dry-runs, enforces custom safety assertions, and optionally rescans the targeted policy.
- **Scheduler (`src/scheduler`)** ranks accepted patches using acceptance probability, expected runtime, exploration, aging, and KEV signals; supports queue management.
- **Risk enrichment (`src/risk`)** fuses EPSS/KEV feeds and optional image scans for downstream prioritisation.
- **Automation (`Makefile`, `scripts/`)** provides repeatable entry points for experiments, telemetry refresh, and reproducibility bundles.

## Repository layout
- `archives/` - zipped paper bundles and large exports kept out of the project root.
- `configs/` - pipeline presets (`run.yaml`, `run_grok.yaml`, `run_rules.yaml`).
- `data/` - detections, patches, verification results, risk metrics, queues, evaluation corpora.
- `docs/` - research notes, policy guidance, reproducibility appendices, future work plans.
- `infra/fixtures/` - RBAC, NetworkPolicies, and `manifests/` samples (CronJob scanner, Bitnami PostgreSQL) for reproducing edge cases.
- `logs/` - proposer/verifier transcripts and Grok sweep summaries.
- `paper/` - IEEE Access manuscript sources (PDF and TeX assets).
- `scripts/` - maintenance and evaluation helpers (`compute_policy_metrics.py`, `refresh_guidance.py`, `parallel_runner.py`, etc).
- `src/` - core packages (`common`, `detector`, `proposer`, `risk`, `scheduler`, `verifier`).
- `tests/` - pytest suite validating detectors, proposer guardrails, verifier gates, scheduler scoring, CLI tooling.
- `tmp/` - scratch workspace (ignored).

## Configuration
`configs/run.yaml` centralises proposer configuration:
```yaml
seed: 1337
max_attempts: 3
proposer:
  mode: grok          # rules | grok | vendor | vllm
  retries: 2
  timeout_seconds: 60
grok:
  endpoint: "https://api.x.ai/v1/chat/completions"
  model: "grok-4-fast-reasoning"
  api_key_env: "XAI_API_KEY"
vendor:
  endpoint: "https://api.openai.com/v1/chat/completions"
  model: "gpt-4o-mini"
  api_key_env: "OPENAI_API_KEY"
vllm:
  endpoint: "https://<RUNPOD_ENDPOINT>/v1/chat/completions"
  model: "meta-llama/Meta-Llama-3-8B-Instruct"
  api_key_env: "RUNPOD_API_KEY"
rules:
  enabled: true
```
Export the appropriate API key (`XAI_API_KEY`, `OPENAI_API_KEY`, `RUNPOD_API_KEY`) before invoking remote modes.

## Testing and QA
- `make test` - run the full pytest suite (includes patch minimality/idempotence checks once `data/patches.json` exists).
- `make e2e` - exercises the full pipeline on bundled manifests.
- `make summarize-failures` - aggregates verifier rejects by policy/manifest.
- `make reproducible-report` - rebuilds the research appendix with current artifacts.
- `scripts/parallel_runner.py` - parallelise proposer/verifier workloads; `scripts/probe_grok_rate.py` sizes safe LLM concurrency.

## Datasets and metrics (Oct 2025 snapshot)
- **Rules baseline (full corpus)** - 13,589 / 13,656 fixes (99.5 percent) with median JSON Patch length 8 (`data/patches_rules_full.json.gz`, `data/verified_rules_full.json.gz`, `data/metrics_rules_full.json`; decompress the `.json.gz` files before consuming them).
- **Grok full corpus** - 1,313 / 1,313 accepted (100 percent) with median JSON Patch length 6 (`data/batch_runs/grok_full/metrics_grok_full.json`).
- **Secondary supported corpus** - 1,264 / 1,264 accepted in rules mode; artifacts and telemetry under `data/batch_runs/secondary_supported/`.
- Policy-level success probabilities and runtimes are regenerated via `scripts/compute_policy_metrics.py` into `data/policy_metrics.json`.
- Scheduler evaluation (`docs/scheduler_visualisation.md`, `data/metrics_schedule_sweep.json`) compares bandit, risk-only, and FIFO strategies.

Large corpus artifacts are stored as compressed `.json.gz` files to keep the repository lean. Run `gunzip data/patches_rules_full.json.gz` (and the verified counterpart) before tooling that expects the plain `.json` filenames.

## Roadmap
- Q4 2025 - publish a containerised reproducibility bundle for one-command replays.
- Q1 2026 - rerun Grok corpora with live latency/token telemetry.
- Q1 2026 - validate against an external CNCF corpus.
- Q2 2026 - expand operator studies and incorporate threat-mitigation guard metadata into CI.

## Related work
| System | Acceptance / fix rate | Corpus | Guardrail highlights | Scheduling |
| ------ | -------------------- | ------ | ------------------- | ---------- |
| **k8s-auto-fix** | 88.78% (Grok-5k), 93.54% / 100% (supported rules), 100% (Grok 1.313k) | 5k + 1.3k manifests | Secret sanitisation, privileged DaemonSet hardening, CRD seeding, triad verification | Bandit scheduler with policy metrics |
| GenKubeSec (2024) | ~85-92% (curated 200) | 200 manifests | LLM reasoning with human review | None |
| Kyverno (2023+) | 80-95% (policy mutation) | Thousands | Policy-driven mutation/generation | Admission queue |
| Borg/SRE automation | ~90-95% (internal) | Millions | Rollbacks, health checks, throttling | Priority queues |
| Magpie (2024) | ~84% dry-run acceptance | 9.5k manifests | RBAC and PSP static analysis | None |
