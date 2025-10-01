# k8s-auto-fix

This repo is my attempt at wiring together a full pipeline that scans Kubernetes manifests, proposes JSON patches, checks them, and then ranks the fixes. It is still very much a work-in-progress project for learning, but it already produces end-to-end artifacts when I run it in **rules** mode.

## What I built so far

- **Detector** (`src/detector`) wraps `kube-linter` and optionally Kyverno. It now writes a rigid `data/detections.json` file with the exact fields the later stages expect (`id`, `manifest_path`, optional `manifest_yaml`, `policy_id`, `violation_text`).
- **Proposer** (`src/proposer`) can run in three modes:
  1. `rules` – deterministic patches based on handcrafted heuristics (what I use for my baseline).
  2. `vendor` – assumes an OpenAI-compatible endpoint such as GPT-4o.
  3. `vllm` – same schema but intended for a self-hosted model (ex: RunPod) that speaks the OpenAI chat-completions protocol.
  It loads settings from `configs/run.yaml`, enforces that responses are valid JSON Patch arrays, and double-checks the patch paths before accepting them.
- **Verifier** (`src/verifier`) applies patches, runs simple policy rechecks (`no_latest_tag`, `no_privileged`), calls `kubectl apply --dry-run=server`, and performs some additional safety assertions. The CLI outputs `data/verified.json` with the agreed schema.
- **Scheduler** (`src/scheduler`) ranks the accepted patches with the score `S = R * p / E[t] + explore + α * wait + KEV`, then writes `data/schedule.json` containing `id`, the score, and the individual components.
- **Configs and Fixtures** – Added a single source of truth config (`configs/run.yaml`), two sample manifests (`data/manifests/001.yaml`, `002.yaml`), and two Kyverno policy examples for completeness.
- **Automation** – Replaced the old Makefile with targets that map to the new CLI entrypoints (`make detect`, `make propose`, `make verify`, `make schedule`, `make e2e`, etc.). There is also a `smoke-proposer` curl command for testing proprietary endpoints quickly.
- **Tests** – Expanded unit tests to exercise the new contracts (detector, proposer guards, verifier gates, scheduler ordering) and added a patch minimality/idempotence check. Some tests skip automatically if `data/patches.json` is missing, which is fine until I run the proposer.

## Requirements

- Python 3.10+ (I used 3.12 from conda).
- `pip install -r requirements.txt` (covered by `make setup`).
- Optional: `kube-linter`, `kyverno`, and `kubectl` available in `$PATH` if I want real detector/verifier signals. For testing, the detector stubs can be used.
- Optional: API keys set via environment variables if I want to use the `vendor` or `vllm` proposer modes.

## Repository layout (what lives where)

### configs/
- `run.yaml` – master configuration. Controls proposer mode (`rules`, `vendor`, `vllm`), retry/timeout settings, API endpoints, and which environment variables hold credentials.

### data/
- `manifests/001.yaml` – Pod running `nginx:latest`; purposely violates “no latest tag”.
- `manifests/002.yaml` – Pod with `securityContext.privileged: true`; trips the “no privileged” guard.
- `policies/kyverno/require-nonroot.yaml` – sample Kyverno rule requiring `runAsNonRoot`.
- `policies/kyverno/require-requests-limits.yaml` – sample Kyverno rule for resource requests/limits.
- `detections.json` – detector output; array of `{id, manifest_path, manifest_yaml, policy_id, violation_text}`.
- `patches.json` – proposer output; array of `{id, policy_id, source, patch}`.
- `verified.json` – verifier output; array of `{id, accepted, ok_schema, ok_policy, patched_yaml}`.
- `schedule.json` – scheduler output; array of `{id, score, R, p, Et, wait, kev}`.

### scripts/
- `kind_up.sh` – small helper to spin up a local kind cluster (control-plane only) and set the kubectl context.

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
  - `verifier.py` – three-gate verification logic (policy check, kubectl dry-run, safety assertions).
  - `jsonpatch_guard.py` – helper that checks patch paths exist before application.
  - `__init__.py` – package export.
- `scheduler/`
  - `cli.py` – reads verified results, filters accepted ones, computes metrics, writes `data/schedule.json`.
  - `schedule.py` – scoring heuristic + dataclass used by CLI.
- `eval/` – currently empty placeholder for future evaluation/reporting scripts.

### tests/
- `test_detector.py` – stubs out detector command calls and asserts the new detections schema.
- `test_proposer.py` – exercises the JSON Patch guards and path validator.
- `test_verifier.py` – covers policy gate, schema failure, safety checks, and invalid patches.
- `test_scheduler.py` – ensures the scoring heuristic orders candidates correctly and enforces required fields.
- `test_patch_minimality.py` – optional smoke test that confirms generated patches are short and idempotent (skips unless `data/patches.json` exists).

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
   - Rules mode (no API keys needed):
     ```yaml
     # configs/run.yaml
     proposer:
       mode: rules
     ```
     ```bash
     make propose
     # writes data/patches.json
     ```
   - Vendor / vLLM modes: update `configs/run.yaml` with your endpoint/model and ensure the referenced `api_key_env` variables are exported (`OPENAI_API_KEY`, `RUNPOD_API_KEY`, etc.). Then run the same `make propose`. The CLI will fail fast if the service returns anything other than pure JSON Patch.

4. **Verify patches**
   ```bash
   make verify
   # outputs data/verified.json (fields: id, accepted, ok_schema, ok_policy, patched_yaml)
   ```
   Note: if `kubectl` is not available the schema gate will fail. For quick iteration I sometimes stub it in tests.

5. **Schedule accepted patches**
   ```bash
   make schedule
   # outputs data/schedule.json listing id + score + breakdown
   ```

6. **Run the whole thing**
   ```bash
   make e2e
   ```

## Configuration knobs

`configs/run.yaml` is the single place I edit when switching backends:

```yaml
seed: 1337                  # used by proposer retries
max_attempts: 3             # proposer will retry this many times per detection

proposer:
  mode: rules               # or vendor / vllm
  retries: 2                # request retries for API-based modes
  timeout_seconds: 60

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
export OPENAI_API_KEY="..."
# or
export RUNPOD_API_KEY="..."
```

## Tests

I run the test suite with:

```bash
make test
```

`tests/test_patch_minimality.py` skips automatically if `data/patches.json` is missing (which is the case until I generate patches). Once I run `make propose` the extra checks kick in and ensure patches are short and idempotent.

## Known gaps / TODOs

- Detector currently serializes `manifest_yaml` by reading directly from disk. For very large manifests I may want to limit that or switch to embedding only the relevant document.
- Verifier relies on `kubectl`. On systems without it the schema gate fails and marks proposals as rejected. I might add a fallback dry-run using the Kubernetes Python client.
- Scheduler currently uses hard-coded risk and probability numbers (just enough to demonstrate the formula). I plan to hook it to real metrics when I have them.
- There is no actual patch application or evaluation stage yet. `src/eval/` is empty.
- I have not added CLI commands to regenerate policy fixtures or to download external datasets.

## Quick troubleshooting notes

- **Detector finds nothing** – double-check `data/manifests/` has the sample YAMLs or pass `--in` with explicit file paths.
- **Proposer complains about missing manifest YAML** – ensure detections were generated with the new schema (run `make detect` after changing anything) so each detection has `manifest_yaml` populated.
- **Proposer guard failures** – the log will mention `no top-level JSON array`, `invalid op`, etc. That means the upstream model returned text that isn’t valid JSON Patch. Clean up the prompt or switch to rules mode.
- **Verifier fails on schema** – make sure the kind cluster is up (`make kind-up`) and `kubectl` can talk to it, or toggle to a fake dry-run for local testing.
- **Scheduler outputs empty list** – usually means all patches were rejected. Inspect `data/verified.json` to confirm.

## Final thoughts

I tried to keep everything in plain Python with Typer CLIs so the stages can be run independently or chained. The baseline rule mode is perfect for demos because it shows the full flow without any external dependencies. When I’m ready to experiment with LLMs, all I have to do is point the config at an OpenAI-style endpoint and supply the right API key.
