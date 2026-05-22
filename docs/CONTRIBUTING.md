# Contributing

Thanks for helping improve `k8s-auto-fix`. This repository is both a research
artifact and an operator-facing automation pipeline, so small, reproducible
changes are easier to review than broad rewrites.

## Local setup

Use a virtual environment and install the checked-in requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make setup
make doctor
```

The Makefile uses `.venv/bin/python` when that virtual environment exists, and
falls back to `python3` otherwise. Override it when needed, for example when
you want to use a specific interpreter:

```bash
make doctor PYTHON=python3.11
make setup PYTHON=python3.11
```

## Test tiers

Run the fastest relevant tier before opening a PR:

- `make test` runs the unit suite with `python -m pytest -q`.
  This is the default CI check and should not require a Kubernetes cluster or API
  keys.
- `make artifact-test` runs generated-artifact consistency checks such as patch
  minimality. These checks are opt-in because they depend on checked-in or
  freshly generated evaluation outputs.
- `make e2e` runs the bundled detector -> proposer -> verifier -> risk ->
  scheduler -> queue smoke path in rules mode. It writes generated files such as
  `data/detections.json`, `data/patches.json`, `data/verified.json`,
  `data/risk.json`, `data/schedule.json`, and `data/queue.db`; review or clean
  those changes before committing.
- Cluster, live-evaluation, benchmark, and LLM-backed commands are optional
  heavyweight checks. Use them when touching verifier dry-run behavior,
  reproducibility scripts, benchmark paths, or model-backed proposer logic.

## Data and artifacts

Keep source inputs and generated outputs separate. Canonical manifests, policies,
schemas, and fixtures live under the legacy `data/` paths and are surfaced by
the curated `data/corpora/` view. Generated experiment outputs are surfaced by
`data/outputs/`.

Do not add large logs, scratch files, local databases, binary packages, or one-off
experiment dumps unless the PR intentionally refreshes a documented artifact.
Use `tmp/` for local scratch work and leave ignored virtualenv, cache, coverage,
and build outputs out of commits.

When an artifact refresh is intentional, document the producer command, relevant
inputs, and any expected metric movement in the PR description.

## Secrets and credentials

Never commit API keys, kubeconfigs, bearer tokens, literal passwords, or private
cluster details. Use environment variables for remote modes:

- `XAI_API_KEY` for Grok/xAI proposer runs.
- `OPENAI_API_KEY` for OpenAI-compatible vendor runs and LLMSecConfig slices.
- `RUNPOD_API_KEY` for vLLM/RunPod experiments.

Keep local `.env` files private. Redact secrets from logs, screenshots, terminal
output, and generated artifacts before sharing them. Patches that remediate
Kubernetes environment-variable secrets should preserve the existing
`valueFrom.secretKeyRef` behavior instead of writing secret values into manifests
or JSON patches.
