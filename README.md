# k8s-auto-fix

This repo is my attempt at wiring together a full pipeline that scans Kubernetes manifests, proposes JSON patches, checks them, and then ranks the fixes. It now runs end-to-end in both **rules** mode and **Grok LLM** mode with verifier-backed acceptance.

## What I built so far

- **Detector** (`src/detector`) wraps `kube-linter` and optionally Kyverno. It now writes a rigid `data/detections.json` file with the exact fields the later stages expect (`id`, `manifest_path`, optional `manifest_yaml`, `policy_id`, `violation_text`).
- **Proposer** (`src/proposer`) can run in four modes:
  1. `rules` – deterministic patches based on handcrafted heuristics (baseline; 100/100 accepted on the latest `data/detections_100.json` sweep).
  2. `grok` – xAI Grok-4 Fast Reasoning with injected policy/safety guidance; LLM responses are merged with the rule patch so guardrails (drop dangerous capabilities, clear `privileged`, add service accounts, rewrite dangling Services, set PodDisruptionBudget eviction policies, etc.) always land.
  3. `vendor` – assumes an OpenAI-compatible endpoint such as GPT-4o.
  4. `vllm` – intended for a self-hosted model (ex: RunPod) that speaks the OpenAI chat-completions protocol.
  It loads settings from `configs/run.yaml`, enforces strict JSON Patch parsing, validates path applicability, retries with verifier feedback, and now walks nested `jobTemplate` specs so CronJobs are patched correctly. The CLI accepts `--jobs` for parallel patch generation and loads extra policy snippets from `docs/policy_guidance/` to give Grok/vendor runs retrieval-augmented context on retries.
- **Verifier** (`src/verifier`) applies patches, runs policy rechecks across the expanded rule set (`no_latest_tag`, `no_privileged`, `no_host_path`, `no_host_ports`, `run_as_user`, `enforce_seccomp`, `drop_capabilities`, `non_existent_service_account`, `pdb_unhealthy_eviction_policy`, etc.), calls `kubectl apply --dry-run=server`, performs additional safety assertions (including CronJob traversal), and optionally rescans the targeted policy. The CLI outputs `data/verified.json`.
- **Scheduler** (`src/scheduler`) ranks the accepted patches with the score `S = R * p / E[t] + explore + α * wait + KEV`, normalises policy identifiers, and writes `data/schedule.json` containing `id`, the score, and the individual components.
- **Risk enrichment** (`src/risk`) pulls CTI feeds (EPSS/KEV), optional Trivy image scans, and policy defaults to build `data/risk.json` for downstream prioritisation.
- **Configs and Fixtures** – Added a single source of truth config (`configs/run.yaml`), three sample manifests (`data/manifests/001.yaml`, `002.yaml`, `003.yaml`), and Kyverno policy examples for parity.
- **Automation** – Replaced the old Makefile with targets that map to the new CLI entrypoints (`make detect`, `make propose`, `make verify`, `make risk`, `make schedule`, `make queue-enqueue`, `make metrics`, `make benchmark-grok200`, `make benchmark-grok5k`, `make benchmark-full`, `make benchmark-scheduler`, `make e2e`, etc.). There is also a `smoke-proposer` curl command for testing proprietary endpoints quickly.
- **Failure triage** – `make summarize-failures` aggregates verifier rejects (policy, reason, manifest) across large Grok sweeps so guardrail tuning is data-driven.
- **Tests** – Expanded unit tests to exercise the new contracts (detector, proposer guards, verifier gates, scheduler ordering) and added a patch minimality/idempotence check that now sweeps every manifest referenced in `data/detections.json`.

## Requirements

- Python 3.10+ (I used 3.12 from conda).
- `pip install -r requirements.txt` (covered by `make setup`).
- `kube-linter`, `kyverno`, and `kubectl` available in `$PATH` so the detector and verifier can exercise real binaries.
- Docker runtime (Colima on macOS works great) plus kind to host the verification API server (`make kind-up`).
- Optional API keys if you want remote proposer modes (`OPENAI_API_KEY`, `RUNPOD_API_KEY`, `XAI_API_KEY`).

## Repository layout (what lives where)

### configs/
- `run.yaml` – master configuration. Controls proposer mode (`rules`, `grok`, `vendor`, `vllm`), retry/timeout settings, API endpoints, and which environment variables hold credentials.
- `run_grok.yaml` – ready-to-run Grok preset; pins proposer mode to `grok` with the same retry/timeout defaults so API-backed sweeps only need an exported `XAI_API_KEY`.
- `run_rules.yaml` – offline preset that forces proposer mode to `rules` (keeps retries/timeouts aligned) for quick deterministic baselines without touching remote APIs.

### data/
- `manifests/001.yaml` – Pod running `nginx:latest`; purposely violates “no latest tag”.
- `manifests/002.yaml` – Pod with `securityContext.privileged: true`; trips multiple Pod Security violations.
- `manifests/003.yaml` – Pod combining `hostPath`, `hostPort`, dangerous capabilities, and missing seccomp/runAsUser to exercise the expanded policy set.
- `policies/kyverno/require-nonroot.yaml` – sample Kyverno rule requiring `runAsNonRoot`.
- `policies/kyverno/require-requests-limits.yaml` – sample Kyverno rule for resource requests/limits.
- `manifests/artifacthub/` – rendered Helm charts (currently ~1k resources across 55 popular ArtifactHub packages).
- `manifests/the_stack_sample/` – 200 curated manifests sampled from the HuggingFace `the-stack-yaml-k8s` corpus.
- `detections.json` – detector output over the full corpus (currently 1,313 findings across 1,178 manifests).
- `detections_sampled.json` – smaller subset (10 findings) used for the end-to-end Grok run.
- `patches.json` – proposer output; array of `{id, policy_id, source, patch}` (10 entries in the current Grok sample run).
- `verified.json` – verifier output; array of `{id, accepted, ok_schema, ok_policy, ok_safety, ok_rescan, patched_yaml}` (add `--include-errors` to persist verifier messages alongside the records).
- `risk.json` – risk enrichment output for each detection.
- `schedule.json` – scheduler output; array of `{id, score, R, p, Et, wait, kev}`.
- `queue.db` – SQLite-backed persistent queue populated from accepted patches.
- `metrics.json` – aggregated KPIs (`detections`, `patches`, `verified`, `accepted`, `auto_fix_rate`, `median_patch_ops`, `failed_policy`, `failed_schema`, `failed_safety`, `failed_rescan`).
- `batch_runs/` – evaluation artifacts. Notably `patches_grok200_batch_*.json`, `verified_grok200_batch_*.json`, `patches_grok200.json`, `verified_grok200.json`, `metrics_grok200.json`, and `results_grok200.json` capture a 20×10 Grok run (200 detections) with rule-merged guardrails and server-side dry-run validation. `grok_full/` mirrors the 1,313-case Grok sweep (`detections_grok_full_batch_*.json`, `patches_grok_full_batch_*.json`, `verified_grok_full_batch_*.json`, plus merged `patches_grok_full.json`, `verified_grok_full.json`, `metrics_grok_full.json`).

### scripts/
- `kind_up.sh` – small helper to spin up a local kind cluster (control-plane only) and set the kubectl context.
- `collect_artifacthub.py` – fetch the top N Helm charts from ArtifactHub, render them with `helm template`, and split the output into individual manifests under `data/manifests/artifacthub/`.
- `sample_the_stack.py` – download a parquet shard from `substratusai/the-stack-yaml-k8s` and emit a small set of valid Kubernetes manifests into `data/manifests/the_stack_sample/`.
- `parallel_runner.py` – orchestration wrapper that shards detections/patches and runs proposer or verifier across multiple processes, then merges the results.
- `probe_grok_rate.py` – lightweight Grok latency/rate-limit probe; emits JSON metrics so you can size safe concurrency before long LLM runs.
- `split_detections.py` / `merge_batches.py` – small utilities used by the `make benchmark-grok-full` target to fan out/merge JSON batches.

### docs/
- `policy_guidance/` – Markdown snippets (per policy) that the proposer in Grok/vendor modes injects into the prompt when retrying with verifier feedback (lightweight RAG).

### src/
- `detector/`
  - `cli.py` – Typer CLI (`python -m src.detector.cli`) that walks manifests and writes `data/detections.json`.
  - `detector.py` – orchestration around `kube-linter` / Kyverno plus JSON serializer.
  - `__init__.py`, `__main__.py` – package exports + module entry point.
- `proposer/`
  - `cli.py` – batch proposer CLI that reads detections, loads config, calls rules or API-backed generator, validates output, and writes `data/patches.json`.
  - `model_client.py` – OpenAI-style HTTP client with retries/backoff.
  - `guards.py` – strict JSON Patch parsing guard (fenced code block removal, op validation, etc.).
  - `server.py` – FastAPI service version of the proposer (shares guards, still uses OpenAI payload).
  - `__init__.py` – package export.
- `verifier/`
  - `cli.py` – loads patches + detections, applies verifier logic, writes `data/verified.json`.
  - `verifier.py` – three-gate verification logic (policy check, kubectl dry-run, safety assertions, optional targeted rescan).
  - `jsonpatch_guard.py` – helper that checks patch paths exist before application.
  - `__init__.py` – package export.
- `scheduler/`
  - `cli.py` – reads verified results, filters accepted ones, computes metrics, writes `data/schedule.json`.
  - `schedule.py` – scoring heuristic + dataclass used by CLI.
  - `queue.py` / `queue_cli.py` – persistent SQLite-backed queue and Typer CLI (`queue-init`, `queue-enqueue`, `queue-next`).
- `risk/`
  - `cli.py` – composes risk metrics from detections, CTI feeds, and optional Trivy.
  - `fetch_cti.py` – downloads EPSS/KEV feeds.
- `eval/`
  - `metrics.py` – CLI that summarises core KPIs into `data/metrics.json`.

### tests/
- `test_detector.py` – stubs out detector command calls and asserts the new detections schema.
- `test_proposer.py` – exercises the JSON Patch guards and path validator.
- `test_verifier.py` – covers policy gates across the broader rule set, schema failure, safety checks, and invalid patches.
- `test_scheduler.py` – ensures the scoring heuristic orders candidates correctly and enforces required fields.
- `test_patch_minimality.py` – ensures generated patches remain short and idempotent across every manifest in `data/detections.json`.

## Dataset snapshot (Oct 2025)

- **Rendered manifests** – 1,178 YAML resources: ~975 from top ArtifactHub Helm charts (`scripts/collect_artifacthub.py --limit 55`) plus 200 curated samples from HuggingFace (`scripts/sample_the_stack.py --limit 200`) and the three original toy manifests. A larger pull adds 5,000 manifests from the Stack dataset (`scripts/sample_the_stack.py --limit 5000`) under `data/manifests/the_stack_sample/` when we need scale.
- **Detector coverage** – `make detect` across the expanded corpus now reports 13,444 findings. Filtering to the policies backed by rule patches yields a 5,000-item supported slice (`data/detections_supported_5000.json`) that drives the larger-scale rules benchmark.
- **LLM evaluation slices** –  
  - `data/detections_sampled.json` (10 items) – tiny smoke-test set.  
  - `data/batch_runs/detections_grok200_batch_*.json` (20×10 items) – 200-case slice used for the hardened Grok benchmark.  
  Both cover the policies we actively remediate (`no_latest_tag`, `read_only_root_fs`, `run_as_non_root`, `set_requests_limits`, `dangling-service`, `non-existent-service-account`, `pdb-unhealthy-pod-eviction-policy`, etc.).
- **Evidence artifacts** – `data/patches.json`, `data/verified.json`, `data/risk.json`, `data/schedule.json`, `data/metrics.json`, and `data/queue.db` mirror the most recent local run. Batch evaluations live under `data/batch_runs/` (see `results_grok200.json` for the 200-case summary). The 5k rules sweep emits `data/patches_rules_5000.json`, `data/verified_rules_5000.json`, and `data/metrics_rules_5000.json` (93.5 % acceptance, median patch length 6); the 1.3k legacy artifacts remain available as `*_rules_full.json`.
- **Unsupported detections** – Rule coverage now spans the full corpus, including the previous outliers (`env-var-secret`, `liveness-port`, `readiness-port`, `startup-port`) and the `latest-tag` manifests that lacked explicit image strings.

## How I run everything

1. **Install dependencies**
   ```bash
   make setup
   ```

2. **Generate detections** (I default to the bundled sample manifests.)
   ```bash
   make detect
   # writes data/detections.json
   ```

3. **Produce patches**
   - Pick a proposer mode in `configs/run.yaml` (`rules`, `grok`, `vendor`, `vllm`).
   - Export the matching API key if needed (`XAI_API_KEY`, `OPENAI_API_KEY`, or `RUNPOD_API_KEY`).
   - For the 10-item smoke test:
   ```bash
    export XAI_API_KEY="..."
    python -m src.proposer.cli \
      --detections data/detections_sampled.json \
      --out data/patches.json \
      --config configs/run.yaml \
      --jobs 4
    ```
    (Drop `--jobs` or tune the worker count to match Grok/vendor rate limits.)
   - For the 200-case Grok benchmark (already split into batches under `data/batch_runs/`):
     ```bash
     export XAI_API_KEY="..."
     for f in data/batch_runs/detections_grok200_batch_*.json; do
       idx=$(basename "$f" .json | sed 's/[^0-9]//g')
       python -m src.proposer.cli \
         --detections "$f" \
         --out "data/batch_runs/patches_grok200_batch_${idx}.json" \
         --config configs/run.yaml
     done
     ```

4. **Verify patches**
   ```bash
   make kind-up   # one-time per session; starts the local kind cluster via Colima/Docker
   ```
   ```bash
   python -m src.verifier.cli \
     --patches data/patches.json \
     --detections data/detections_sampled.json \
     --out data/verified.json \
     --include-errors --require-kubectl --enable-rescan \
     --policies-dir data/policies/kyverno \
     --jobs 4
   # outputs data/verified.json (fields: id, accepted, ok_schema, ok_policy, ok_safety, ok_rescan, patched_yaml, errors)
   ```
  If `kubectl` is not available the schema gate will fail; the unit tests stub `_kubectl_dry_run` for quick iteration.
  - Batch variant (200-case Grok benchmark; requires `XAI_API_KEY` and a running kind cluster): `make benchmark-grok200 GROK_VERIFY_FLAGS="--include-errors --require-kubectl --enable-rescan --policies-dir data/policies/kyverno"`

5. **Compute risk (optional but recommended)**
   ```bash
   make cti      # downloads EPSS + KEV (idempotent)
   python -m src.risk.cli \
     --detections data/detections_sampled.json \
     --out data/risk.json \
     --epss-csv data/epss.csv \
     --kev-json data/kev.json
   ```

6. **Schedule accepted patches**
   ```bash
   python -m src.scheduler.cli \
     --verified data/verified.json \
     --detections data/detections_sampled.json \
     --risk data/risk.json \
     --out data/schedule.json
   # outputs data/schedule.json listing id + score + breakdown
   ```

7. **Queue accepted patches**
   ```bash
   make queue-init
   python -m src.scheduler.queue_cli enqueue \
     --db data/queue.db \
     --verified data/verified.json \
     --detections data/detections_sampled.json \
     --risk data/risk.json
   make queue-next   # prints the highest priority item
   ```

8. **Emit aggregate metrics**
   ```bash
   python -m src.eval.metrics \
     --detections data/detections_sampled.json \
     --patches data/patches.json \
     --verified data/verified.json \
     --out data/metrics.json
   ```

9. **Run the whole thing**
   ```bash
   make e2e
   ```

10. **Benchmarks**
   ```bash
   make benchmark-grok200      # 20×10 Grok batches; override GROK_VERIFY_FLAGS to enforce kubectl dry-run
   make benchmark-full         # full corpus rules benchmark (defaults to $(JOBS)=4 workers)
   make benchmark-scheduler    # compare heuristic vs FIFO/risk-only ordering (writes data/metrics_schedule_compare.json)
   ```

### Parallel runs (optional)

Large corpora are CPU-bound in rules mode and latency-bound with Grok. Use `scripts/parallel_runner.py` to fan out work across multiple processes:

```bash
# 4-way rules-mode proposer (≈4s for 1,222 detections; down from ~30s)
python scripts/parallel_runner.py propose \
  --detections data/detections_supported.json \
  --config configs/run_rules.yaml \
  --out data/patches_rules_parallel.json \
  --jobs 4

# 4-way verifier (no kubectl, ≈30s vs ~4m42s sequential)
python scripts/parallel_runner.py verify \
  --patches data/patches_rules_parallel.json \
  --detections data/detections_supported.json \
  --out data/verified_rules_parallel.json \
  --jobs 4 \
  --extra-args --include-errors --no-require-kubectl
```

For Grok/vendor modes, pick a `--jobs` value that stays within the API rate limit. `scripts/probe_grok_rate.py` helps size safe concurrency (see “Current metrics”).

## Configuration knobs

`configs/run.yaml` is the single place I edit when switching backends:

```yaml
seed: 1337                  # used by proposer retries
max_attempts: 3             # proposer will retry this many times per detection

proposer:
  mode: grok                # or rules / vendor / vllm
  retries: 2                # request retries for API-based modes
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

The proposer CLI reads the file, determines the mode, and either calls out to the configured endpoint or falls back to the rule-based helpers. When using API modes I also export the keys:

```bash
export XAI_API_KEY="..."      # grok
export OPENAI_API_KEY="..."   # vendor
export RUNPOD_API_KEY="..."   # vllm
```

## Tests

I run the test suite with:

```bash
make test
```

`tests/test_patch_minimality.py` reads the generated detections to validate that every patch is idempotent and short once `data/patches.json` exists (so run `make propose` first).

- **End-to-end smoke** – `make e2e` runs the detector → proposer → verifier → risk → scheduler → queue pipeline over the three sample manifests and exits once it confirms accepted patches and a queue head item.

## Current metrics (Oct 2025)

<!-- METRICS_SECTION_START -->
- **Rules baseline (full corpus)** – `make benchmark-full` produces 1313/1313 fixes (100.0%) with median JSON Patch length 6 (`data/patches_rules_full.json`, `data/verified_rules_full.json`, `data/metrics_rules_full.json`).
- **Grok full corpus** – `make benchmark-grok-full` covers the 1,313-case corpus with 1313/1313 accepted patches (100.0%) and median JSON Patch length 6 (`data/batch_runs/grok_full/metrics_grok_full.json`).
- **Grok 5k corpus** – `make benchmark-grok5k` currently lands 3137/5000 accepted patches (62.74%) with median JSON Patch length 6. Failures break down as 1,846 schema rejects (kubectl dry-run) caused by missing CRDs/controllers in the kind cluster, 312 safety rejects, 11 policy rejects, and 9 rescan failures (`data/batch_runs/grok_5k/metrics_grok5k.json`).
- **Grok benchmark (first 200 detections)** – `make benchmark-grok200` runs 20 batches totalling 200 detections with 200/200 accepted (100.0%); artifacts live under `data/batch_runs/`.
- **Scheduler comparison** – `make benchmark-scheduler` ranks the top 50 high-risk items at mean rank 25.5 (median 25.5, P95 48.0) for both bandit and risk-only modes, while FIFO slips to mean 326.58 (P95 880.0).
- **Scheduler telemetry** – the baseline bandit completes 1,313 patches in 218.8h at ~6.0 patches/hour with top-risk P95 wait 20.7h; FIFO stretches the same P95 wait to 174.0h (`telemetry` in `data/metrics_schedule_compare.json`).
- **Parallel rules baseline** – `scripts/parallel_runner.py` can propose and verify the corpus with configurable `--jobs` (see `make benchmark-full JOBS=8` for an example run).
- **Latency probes (`scripts/probe_grok_rate.py`)** – keep Grok/API concurrency under observed limits before launching full-corpus batches.
<!-- METRICS_SECTION_END -->

## Known gaps / TODOs

- Provision the verification cluster (kind) with the CRDs/controllers referenced by the 5k corpus so kubectl dry-run stops rejecting Grok batches.
- Eliminate the 312 safety rejects in the rules 5k sweep by embedding global safety invariants into rule patches and adding regression tests.
- Unify policy ID normalisation across proposer/verifier and expand verifier coverage for `read_only_root_fs`, `set_requests_limits`, and `run_as_non_root` (including initContainers/ephemeralContainers).
- Instrument proposer prompt token counts and latency so we can quantify the manifest compaction gains in `metrics.json` and budget reports.
- Teach the guidance indexer to periodically pull the latest Pod Security and CIS revisions instead of relying on manually curated snippets.
- Generate visual dashboards (plots or tables) from the scheduler telemetry to surface fairness gains in the paper and README.

## Quick troubleshooting notes

- **Detector finds nothing** – double-check `data/manifests/` has the sample YAMLs or pass `--in` with explicit file paths.
- **Proposer complains about missing manifest YAML** – ensure detections were generated with the new schema (run `make detect` after changing anything) so each detection has `manifest_yaml` populated.
- **Proposer guard failures** – the log will mention `no top-level JSON array`, `invalid op`, etc. That means the upstream model returned text that isn’t valid JSON Patch. Clean up the prompt or switch to rules mode.
- **Verifier fails on schema** – make sure the kind cluster is up (`make kind-up`) and `kubectl` can talk to it, or toggle to a fake dry-run for local testing.
- **Scheduler outputs empty list** – usually means all patches were rejected. Inspect `data/verified.json` to confirm.

## Final thoughts

I tried to keep everything in plain Python with Typer CLIs so the stages can be run independently or chained. The baseline rule mode is perfect for demos because it shows the full flow without external dependencies. When I’m ready to experiment with LLMs, I flip `configs/run.yaml` to `mode: grok` (or another OpenAI-style endpoint), export the API key, and rerun the pipeline—global prompt guidance keeps the model outputs verifier-safe.
- **Reproducing the pull** – to refresh the corpus:
  ```bash
  python scripts/collect_artifacthub.py --limit 55
  python scripts/sample_the_stack.py --limit 200
  make detect
  ```
- **Hardened Grok evaluation (200 detections)** – Running the Grok proposer with rule-merge guardrails over the first 200 detector findings (20×10 batches) delivered **200/200 accepted** patches, with per-policy rates listed in `data/batch_runs/results_grok200.json` (e.g., `unset-{cpu,memory}-requirements` 44/44, `dangling-service` 22/22, `pdb-unhealthy-pod-eviction-policy` 3/3). Every patch also passes `kubectl apply --dry-run=server` against the bundled kind cluster (`data/batch_runs/verified_grok200_dryrun_batch_*.json`). Reproduce with `make benchmark-grok200`.
- **Next milestone** – Run the full detection corpus in both rules and Grok modes, publish auto-fix/no-new-violations/latency metrics, and update the Access.tex comparison table accordingly.
