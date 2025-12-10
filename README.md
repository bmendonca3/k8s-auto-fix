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
- `archives/` – historical exports and large bundles kept out of the active workspace.
- `configs/` – pipeline presets (`run.yaml`, `run_grok.yaml`, `run_rules.yaml`).
- `data/` – retains the canonical folders (`data/manifests`, `data/batch_runs`, etc.) and now exposes curated views via `data/corpora/` (inputs) and `data/outputs/` (generated artefacts). See `data/README.md` for details.
- `docs/` – research notes, policy guidance, reproducibility appendices, future work plans.
- `infra/fixtures/` – RBAC, NetworkPolicies, and manifest samples (CronJob scanner, Bitnami PostgreSQL) for reproducing edge cases.
- `logs/` – proposer/verifier transcripts, Grok sweep summaries, and root-level logs (e.g. `logs/access.log`).
- `notes/` – working notes and backlog items formerly at the repository root.
- `paper/` – IEEE Access manuscript sources; appendices live in `paper/appendices.tex` (no zip bundle checked in), and Overleaf-ready sources sit under `paper/overleaf/`.
- `scripts/` – maintenance and evaluation helpers; see `scripts/README.md` for an index by pipeline stage.
- `src/` – core packages (`common`, `detector`, `proposer`, `risk`, `scheduler`, `verifier`).
- `tests/` – pytest suite validating detectors, proposer guardrails, verifier gates, scheduler scoring, CLI tooling.
- `tmp/` – scratch workspace (ignored by git). Historic large exports remain under `archives/` if needed.

## Paper and appendices
- Main manuscript: `paper/access.tex` (title: “Closed-Loop Threat-Guided Auto-Fixing of Kubernetes Container Security Misconfigurations”).
- Supplemental appendices: `paper/appendices.tex` (plain-English reading guide, risk worked example, glossary, artifact index). Legacy appendix zip bundles have been removed from the repo.
- To push to Overleaf, use the contents of `paper/` (or the mirror under `paper/overleaf/`); no zip archives are tracked here.

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

## Metrics aligned to the paper (traceable in-repo)
- **Full rules + guardrails replay** – 13,589 / 13,656 accepted (auto-fix rate 0.9951; median patch ops 8) from `data/metrics_rules_full.json` (`patches_rules_full.json.gz`, `verified_rules_full.json.gz`).
- **Rules on the 5k extended corpus** – 4,677 / 5,000 accepted (93.54%; median ops 6) from `data/metrics_rules_5000.json` (`patches_rules_5000.json`, `verified_rules_5000.json`).
- **Grok/xAI 5k proposer** – 4,439 / 5,000 accepted (88.78%; median ops 9) per the `current_state` row in `data/batch_runs/grok_5k/metrics_history.json` (raw run summary in `data/outputs/batch_runs/grok_5k/metrics_grok5k.json`).
- **Supported corpus (rules)** – 1,264 / 1,264 accepted (median ops 8) captured in `data/outputs/batch_runs/secondary_supported/summary.json` and `metrics_rules.json`.
- **Live-cluster replay** – 1,000 / 1,000 dry-run and live-apply success on the stratified slice (`data/live_cluster/summary_1k.csv`).
- **Scheduler fairness** – `data/metrics_schedule_compare.json` shows top-50 high-risk items at median rank 25.5 (P95 48) for the bandit vs median 422.5 (P95 620) under FIFO; wait-time sweeps live in `data/metrics_schedule_sweep.json`.

Policy-level success probabilities and runtimes regenerate via `scripts/compute_policy_metrics.py` into `data/policy_metrics.json`. Scheduler sweeps and fairness telemetry are viewable at `data/outputs/scheduler/metrics_schedule_sweep.json`.

Large corpus artefacts now live under `data/outputs/` and are stored as compressed `.json.gz` files to keep the repository lean. Gunzip the patches/verified/metrics files there before using tooling that expects plain `.json` inputs.

## Related work
| System | Scope in paper | Evidence / guardrails | Scheduling |
| ------ | -------------- | --------------------- | ---------- |
| **k8s-auto-fix (this work)** | Closed-loop detect → propose → verify → schedule | JSON Patch rules + optional LLMs behind policy/schema/`kubectl --dry-run` gates; secret sanitisation; CRD/fixture seeding | Risk-aware bandit with aging + KEV boost (`data/metrics_schedule_compare.json`) |
| GenKubeSec (2024) | LLM-based detection/localization/remediation; authors report precision 0.990, recall 0.999 on a ~277k KCF corpus with 30-sample expert validation | Human review; no automated guardrails | None (FIFO human review) |
| Kyverno (mutation engine) | Admission-time mutation/validation; depends on cluster fixtures | Policy-driven mutate/validate; CLI baseline scripted in `scripts/run_kyverno_baseline.py` with results in `data/baselines/kyverno_baseline.csv` | FIFO admission queue |
| Borg/SRE playbooks | Production auto-remediation for infra fleets | Health checks, rollbacks, throttling; no public acceptance % | Priority queues / toil budgets |
| LLMSecConfig (2025) | LLM remediation prompts with scanner checks | Scanner re-checks; no server-side dry-run | None |

## Baselines and Reproducibility

- Kyverno mutate baseline (simulate or real): `scripts/run_kyverno_baseline.py`
- Polaris mutate/CLI fix baseline (simulate or real): `scripts/run_polaris_baseline.py`
- MutatingAdmissionPolicy baseline (simulate or YAML generation): `scripts/run_mutatingadmission_baseline.py`
- LLMSecConfig-style slice: `scripts/run_llmsecconfig_slice.py` (requires `OPENAI_API_KEY`)
- Risk throughput (KEV-weighted): `scripts/eval_risk_throughput.py`
- Unified baseline comparison: `scripts/compare_baselines.py` (writes CSV/MD/TeX)

Quick start to regenerate bundles and baselines (simulation mode):
```
scripts/reproduce_all.sh
```

See `ARTIFACTS.md` for artifact map, `docs/VERIFIER.md` for guardrails, `docs/BASELINES.md` to run baselines, `docs/RISK_EVAL.md` for prioritization metrics, and `docs/LIVE_EVAL.md` for live-cluster methodology.
