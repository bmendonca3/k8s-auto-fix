# k8s-auto-fix

`k8s-auto-fix` stitches together detection, patch generation, verification, and scheduling so Kubernetes misconfigurations can be triaged automatically. The pipeline can run completely offline with deterministic rules or leverage LLM-backed modes with safety guardrails.

## Highlights
- End-to-end workflow: detector -> proposer -> verifier -> risk enrichment -> scheduler -> queue.
- Switchable proposer backends (rules, Grok, vendor OpenAI-compatible, vLLM) with semantic regression checks and policy-guided prompts.
- Verifier enforces kube-linter and Kyverno policies, `kubectl apply --dry-run=server`, and custom safety guards before patches are accepted.
- Tests, benchmarks, and metrics bundles keep every release reproducible and auditable.

## Requirements
- Python 3.10+ (tested with 3.12).
- `pip install -r requirements.txt` (`make setup` wraps this).
- `kube-linter`, `kyverno`, and `kubectl` binaries on `PATH`.
- Docker runtime with kind (for example Colima) for verifier dry-runs.
- Optional `XAI_API_KEY`, `OPENAI_API_KEY`, or `RUNPOD_API_KEY` for remote proposer modes.

## Quick start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Seed fixtures and bring up the kind cluster when running verifier checks:
   ```bash
   make fixtures
   make kind-up
   ```
3. Execute the sample end-to-end pipeline:
   ```bash
   make e2e
   ```
   This run detects issues in the bundled manifests, generates patches, verifies them, enriches risk data, schedules fixes, and enqueues the highest priority item.

## Standard workflow
1. **Detect misconfigurations**
   ```bash
   python -m src.detector.cli \
     --in data/manifests \
     --out data/detections.json \
     --policies-dir data/policies/kyverno \
     --jobs 4
   ```
2. **Generate patches**
   ```bash
   python -m src.proposer.cli \
     --detections data/detections_sampled.json \
     --out data/patches.json \
     --config configs/run.yaml \
     --jobs 4
   ```
   Use the presets in `configs/` to pin `rules` or `grok` modes.
3. **Verify patches**
   ```bash
   python -m src.verifier.cli \
     --patches data/patches.json \
     --detections data/detections_sampled.json \
     --out data/verified.json \
     --include-errors --require-kubectl \
     --enable-rescan --policies-dir data/policies/kyverno \
     --jobs 4
   ```
4. **Measure detector hold-out performance**
   ```bash
   python -m src.detector.cli --in data/eval/holdout \
     --out data/eval/holdout_detections.json \
     --jobs 4 --policies-dir data/policies/kyverno
   python scripts/eval_detector.py \
     --detections data/eval/holdout_detections.json \
     --labels data/eval/holdout_labels.json \
     --out data/eval/detector_metrics.json
   ```
5. **Capture latency snapshots**
   ```bash
   python scripts/measure_runtime.py \
     --detections data/detections_sampled.json \
     --config configs/run_rules.yaml \
     --patches-out tmp/patches_measure.json \
     --verified-out tmp/verified_measure.json \
     --no-require-kubectl > data/eval/runtime_metrics_rules.json
   ```
6. **Compute risk**
   ```bash
   make cti
   python -m src.risk.cli \
     --detections data/detections_sampled.json \
     --out data/risk.json \
     --epss-csv data/epss.csv \
     --kev-json data/kev.json
   ```
7. **Schedule accepted patches**
   ```bash
   python -m src.scheduler.cli \
     --verified data/verified.json \
     --detections data/detections_sampled.json \
     --risk data/risk.json \
     --out data/schedule.json
   ```
8. **Queue fixes**
   ```bash
   make queue-init
   python -m src.scheduler.queue_cli enqueue \
     --db data/queue.db \
     --verified data/verified.json \
     --detections data/detections_sampled.json \
     --risk data/risk.json
   make queue-next
   ```
9. **Aggregate metrics**
   ```bash
   python -m src.eval.metrics \
     --detections data/detections_sampled.json \
     --patches data/patches.json \
     --verified data/verified.json \
     --out data/metrics.json
   ```
10. **Benchmarks**
    ```bash
    make benchmark-grok200
    make benchmark-full
    make benchmark-scheduler
    ```

## Parallel runs
Large corpora benefit from process-level parallelism:

```bash
python scripts/parallel_runner.py propose \
  --detections data/detections_supported.json \
  --config configs/run_rules.yaml \
  --out data/patches_rules_parallel.json \
  --jobs 4

python scripts/parallel_runner.py verify \
  --patches data/patches_rules_parallel.json \
  --detections data/detections_supported.json \
  --out data/verified_rules_parallel.json \
  --jobs 4 \
  --extra-args --include-errors --no-require-kubectl
```

Use `scripts/probe_grok_rate.py` to pick a safe concurrency level for Grok or vendor APIs.

## Component overview
- **Detector (`src/detector`)** wraps kube-linter and optional Kyverno checks, emits structured detections, and patches gaps such as `hostPath` or `hostPort`.
- **Proposer (`src/proposer`)** supports `rules`, `grok`, `vendor`, and `vllm` modes; merges rule patches with LLM output, enforces JSON Patch parsing, and blocks semantic regressions (no container or volume deletions, safe service-account handling).
- **Verifier (`src/verifier`)** applies patches, rechecks policies including `no_privileged` and `drop_capabilities`, runs `kubectl apply --dry-run=server`, and can rescan the targeted policy.
- **Scheduler (`src/scheduler`)** ranks fixes using acceptance probability, expected runtime, exploration, aging, and KEV signals, and can enqueue work into `data/queue.db`.
- **Risk (`src/risk`)** enriches detections with EPSS or KEV context plus optional image-scan data for prioritisation.
- **Automation** via the `Makefile` mirrors CLI entry points (detect, propose, verify, risk, schedule, metrics, queue, benchmarks, e2e).
- **Policy guidance** under `docs/policy_guidance/` feeds the LLM retrieval flow.

## Repository layout
- `archives/` - zipped paper bundles and other large exports moved out of the project root.
- `configs/` - pipeline presets (`run.yaml`, `run_grok.yaml`, `run_rules.yaml`).
- `data/` - detections, patches, verification results, risk metrics, queues, and evaluation corpora.
- `docs/` - research notes, policy guidance, and reproducibility artifacts.
- `infra/fixtures/` - RBAC, NetworkPolicies, and `manifests/` samples (CronJob scanner, Bitnami PostgreSQL) for reproducing edge cases.
- `logs/` - consolidated pipeline logs including Grok sweeps (`logs/grok5k/`) and top-level proposer or verifier summaries.
- `paper/` - IEEE Access manuscript sources; build outputs land in `paper/build/` (ignored).
- `scripts/` - maintenance and evaluation helpers (`compute_policy_metrics.py`, `refresh_guidance.py`, and more).
- `src/` - core Python packages (`common`, `detector`, `proposer`, `risk`, `scheduler`, `verifier`).
- `tests/` - pytest suite covering detectors, proposer guards, verifier gates, scheduler scoring, and documentation tooling.
- `tmp/` - scratch area for generated intermediates (ignored and created on demand).

## Configuration knobs
`configs/run.yaml` controls proposer backends and retry behavior:

```yaml
seed: 1337
max_attempts: 3

proposer:
  mode: grok
  retries: 2
  timeout_seconds: 60

grok:
  endpoint: "https://api.x.ai/v1/chat/completions"
  model: "grok-4-fast-reasoning"
  api_key_env: "XAI_API_KEY"
  auth_header: "Authorization"
  auth_scheme: "Bearer"

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

Export API keys before invoking LLM-backed modes:

```bash
export XAI_API_KEY="..."
export OPENAI_API_KEY="..."
export RUNPOD_API_KEY="..."
```

## Testing and QA
- `make test` runs the full pytest suite.
- `make e2e` exercises the detector -> proposer -> verifier -> risk -> scheduler -> queue pipeline against sample workloads.
- `make summarize-failures` aggregates verifier rejects by policy and manifest; raw proposer and verifier transcripts live in `logs/`.
- `make reproducible-report` rebuilds the research appendix with the latest metrics.

`tests/test_patch_minimality.py` relies on generated `data/patches.json` to confirm idempotence and minimality.

## Metrics and evaluations (Oct 2025)
- **Rules baseline (full corpus)** - `make benchmark-full` yields 13,589 of 13,656 fixes (99.5 percent) with median JSON Patch length 8 (`data/patches_rules_full.json`, `data/verified_rules_full.json`, `data/metrics_rules_full.json`).
- **Grok full corpus** - `make benchmark-grok-full` covers the 1,313-case corpus with 1,313 of 1,313 accepted patches (100.0 percent) and median JSON Patch length 6 (`data/batch_runs/grok_full/metrics_grok_full.json`).

## Secondary supported corpus (instrumented)
- **Acceptance:** `data/batch_runs/secondary_supported/summary.json` tracks the seed-locked rerun with 1,264 of 1,264 accepted (100.00 percent) in rules mode across curated Helm and Operator manifests.
- **Artifacts:** Generated patches, verifier records, run metrics, and telemetry live under `data/batch_runs/secondary_supported/`.
- **Telemetry:** `scripts/compute_policy_metrics.py` refreshes policy-level success probabilities and expected runtimes (`data/policy_metrics.json`).
- **Evaluation notes:** `docs/secondary_dataset_evaluation.md` summarises both the 200-item pilot and the full supported run.

## Risk-aware scheduling impact
- **Bandit vs FIFO:** `docs/scheduler_visualisation.md` charts ranking quality and wait-time telemetry. Bandit and risk-aware variants keep high-risk fixes in the top 50 (mean rank 25.5, P95 48.0) versus FIFO with mean 365.18.
- **Latency benefit:** For the supported corpus, bandit scheduling limits top-risk P95 wait to about 13 hours compared with FIFO at 102.3 hours.
- **Fairness sweep:** Adjusting the aging or exploration weights (alpha in [0, 2]) maintains predictable wait-time tiers; `data/metrics_schedule_sweep.json` captures the sweep.
- **Inputs:** Scheduler scoring consumes `data/policy_metrics.json`, EPSS or KEV feeds, and queue state; implementation lives in `src/scheduler/cli.py` and `src/scheduler/schedule.py`.

## Limitations and future enhancements
- **Infrastructure dependencies:** Remaining Grok-5k failures are tied to missing namespaces, controllers, or RBAC. `logs/grok5k/failure_summary_latest.txt` lists the root causes. Planned mitigation: broaden CRD seeding via `infra/crds/manual_overrides.yaml` and expand fixtures.
- **Guard updates:** `_patch_ephemeral_metadata` removes stale `clusterName` annotations from ephemeral volumes, and `_patch_pod_security_context` deletes invalid pod-level `allowPrivilegeEscalation` fields. Requests are clamped to their limits to avoid `requests.cpu` violations.
- **Fixtures:** Minimal RBAC and NetworkPolicy helpers live in `infra/fixtures/` to seed namespaces with the ServiceAccounts and policies referenced by CNI or CSI add-ons.
- **Threat mitigation:** Semantic regression checks prevent LLM patches from deleting containers or volumes, and the reproducibility bundle (`make reproducible-report`) ties every metric to its artifact for auditability.
- **Operator feedback:** Field notes and survey templates live in `docs/qualitative_feedback.md` and `docs/operator_survey.md`.
- **Guidance freshness:** `scripts/refresh_guidance.py` syncs `docs/policy_guidance/` excerpts with upstream standards.
- **Cost and latency telemetry:** `docs/telemetry_instrumentation_plan.md` outlines plans to emit per-run latency, token, and cost metrics for integration into `policy_metrics.json`.

## Roadmap
- **Q4 2025 - Reproducibility bundle:** `make reproducible-report` regenerates evaluation tables; next step is a Docker image for one-command replay.
- **Q1 2026 - Grok reruns with live telemetry:** rerun the 1,313 and 5,000 corpora under the latest guards while capturing proposer latency and token metrics.
- **Q1 2026 - External validation:** stage the pipeline against a second public corpus (CNCF sandbox manifests) to demonstrate generality.
- **Q2 2026 - Operator study expansion:** repeat surveys quarterly, including rules versus Grok comparisons and anonymised quotes.
- **Q2 2026 - Hardening:** fold threat-mitigation checks into CI and publish guard metadata alongside queue entries.

## Related work snapshot

| System | Acceptance or fix rate | Corpus size | Guardrail highlights | Scheduling |
| ------ | --------------------- | ----------- | -------------------- | ---------- |
| **k8s-auto-fix (this work)** | 88.78% (Grok-5k), 93.54% / 100.00% (supported rules), 100.00% (Grok 1.313k) | 5k + 1.3k manifests | Placeholder or secret sanitisation, privileged DaemonSet hardening, CRD seeding, triad verification | Bandit scheduler with policy metrics |
| GenKubeSec (2024) | approx 85-92% (curated 200) | 200 manifests | LLM reasoning with manual review | None (future work) |
| Kyverno (2023+) | 80-95% (policy mutation) | Thousands (admission enforced) | Policy-driven mutation or generation | Admission queue only |
| Borg/SRE automation | approx 90-95% (internal clusters) | Millions of workloads | Rollbacks, health checks, throttling | Priority queues |
| Magpie (2024) | about 84% dry-run acceptance | 9.5k manifests | RBAC and PSP static analysis | None |
