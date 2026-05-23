# Configuration Reference

The checked-in YAML files are intentionally small presets for proposer runs,
Polaris baselines, and live-cluster replay. Keep secrets out of these files:
the proposer configs name environment variables with `api_key_env`; the API key
values are read from the shell at runtime.

## Checked-In Files

| File | Purpose | Safe local mode |
| --- | --- | --- |
| `configs/run.yaml` | Default proposer preset. Currently selects Grok mode and also includes vendor and vLLM backend blocks for easy switching. | Use only after exporting `XAI_API_KEY`; for credential-free local runs prefer `configs/run_rules.yaml`. |
| `configs/run_grok.yaml` | Explicit Grok/xAI proposer preset. It is equivalent to the current default preset and is useful for benchmark labels. | Requires `XAI_API_KEY`; keep `--jobs 1` while debugging retries or latency. |
| `configs/run_rules.yaml` | Deterministic rules proposer preset with the same common knobs as the remote presets. | Best default for local smoke tests and CI because it needs no API key. |
| `configs/polaris.yaml` | Polaris CLI baseline config used by `scripts/run_polaris_baseline.py` when staging manifests for `polaris fix`. | Use `scripts/run_polaris_baseline.py --simulate` to avoid invoking Polaris or touching a cluster. |
| `configs/polaris_webhook_values.yaml` | Helm values for the Polaris mutating webhook baseline. The webhook mutates but does not validate, and `failurePolicy: Ignore` avoids blocking the apiserver during TLS or webhook startup issues. | Treat as cluster-facing; use only in an isolated test cluster with cert-manager or another issuer available. |
| `configs/live_cluster_filters.yaml` | Optional custom skip rules for `scripts/run_live_cluster_eval.py`. The checked-in file is an empty list, so only built-in static filters apply. | Use `--simulate` for local path checks; add local filter entries only when a manifest is incompatible with the fixture cluster. |

## Proposer Presets

Proposer configs are consumed by:

```sh
python -m src.proposer.cli --detections data/detections_sampled.json --out data/patches.json --config configs/run_rules.yaml
```

Common knobs:

| Key | Meaning |
| --- | --- |
| `seed` | Seeds deterministic ordering and retry behavior where the proposer uses randomness. |
| `max_attempts` | Upper bound for patch-generation attempts per detection. |
| `retry_budgets.default` | Optional per-detection attempt budget that overrides `max_attempts` when present. |
| `retry_budgets.<policy_id>` | Optional policy-specific attempt budget. Policy-specific values win over `retry_budgets.default`. |
| `proposer.retry_budgets.<policy_id>` | Optional nested override for teams that want retry budgets grouped with proposer settings. Nested values win over top-level values with the same key. |
| `proposer.mode` | Selects `rules`, `grok`, `vendor`, or `vllm`. |
| `proposer.retries` | HTTP retry count inside the model client for remote modes. |
| `proposer.timeout_seconds` | Per-request timeout for remote model calls. |
| `proposer.cache_dir` | Optional model-response cache directory for non-rules modes. Relative paths resolve from the config file directory; `--cache-dir` overrides this value. Cache records include input and config hashes and are written only after response validation succeeds. |
| `<backend>.endpoint` | Chat-completions-compatible API endpoint for `grok`, `vendor`, or `vllm`. |
| `<backend>.model` | Model name sent to the selected endpoint. |
| `<backend>.api_key_env` | Name of the environment variable that must contain the API key. |
| `<backend>.auth_header` / `<backend>.auth_scheme` | Optional authorization header customization. Grok uses `Authorization: Bearer <key>`. |
| `rules.enabled` | Marker for the rules baseline. The CLI switches behavior from `proposer.mode`. |

Required environment variables by mode:

| Mode | Config files | Required environment variable |
| --- | --- | --- |
| `rules` | `configs/run_rules.yaml` | None |
| `grok` | `configs/run.yaml`, `configs/run_grok.yaml` | `XAI_API_KEY` |
| `vendor` | Any proposer config after changing `proposer.mode` to `vendor` | `OPENAI_API_KEY` |
| `vllm` | Any proposer config after changing `proposer.mode` to `vllm` | `RUNPOD_API_KEY` |

For vLLM/RunPod runs, replace the placeholder in `vllm.endpoint` in a local
copy or alternate config before running. The literal `<RUNPOD_ENDPOINT>` value is
not expanded automatically.

## Polaris Baselines

`configs/polaris.yaml` declares the Polaris checks to treat as `danger` or
`warning`, the subset Polaris may mutate, and an empty `exemptions` list. The
baseline runner looks for this file at `configs/polaris.yaml` when using real
Polaris CLI mode.

`configs/polaris_webhook_values.yaml` is for the webhook baseline. Important
knobs are:

| Key | Meaning |
| --- | --- |
| `mergeConfig` | Merge the embedded config with chart defaults. |
| `config` | Inline Polaris checks, mutations, and exemptions passed to the chart. |
| `dashboard.enable` | Keeps the dashboard disabled for benchmark runs. |
| `webhook.enable` | Installs the webhook path. |
| `webhook.mutate` | Enables mutation. |
| `webhook.validate` | Leaves validation disabled so the baseline records mutation behavior rather than admission rejection. |
| `webhook.failurePolicy` | `Ignore` keeps transient webhook failures from blocking test applies. |
| `webhook.timeoutSeconds` | Admission webhook timeout. |
| `certManager.apiVersion` | cert-manager API version expected by the chart values. |

## Live-Cluster Filters

`configs/live_cluster_filters.yaml` appends custom rules to the built-in static
skip list in `scripts/run_live_cluster_eval.py`. Each rule may match:

- `path_substring`
- `apiVersion`
- `kind`
- `metadata.name`
- `metadata.namespace`
- `metadata.name_substring`
- `reason`

Keep the file as `[]` when no extra skips are needed. When adding a rule, include
`reason` so filtered manifests explain why they were skipped in logs and results.

## Safe Local Defaults

- Use `configs/run_rules.yaml` for quick proposer checks without network access
  or credentials.
- Keep `proposer.cache_dir` under an ignored path such as `tmp/` for remote
  experiments; rules mode does not use the model-response cache.
- Use `scripts/run_polaris_baseline.py --simulate` before trying real Polaris CLI
  or webhook modes.
- Use `scripts/run_live_cluster_eval.py --simulate --manifests <dir>` before
  running against a Kubernetes cluster.
- Keep remote API keys in environment variables, not in YAML.
