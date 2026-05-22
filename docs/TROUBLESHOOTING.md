# Troubleshooting

Use this page when a local run, CI job, or staging verification run fails before
the patch queue is ready for review. Start with the smallest reproducible slice:
one detection, one patch, and verifier output with errors included.

## First Checks

1. Run `make doctor` and fix missing Python packages, Kubernetes tools, or repo
   paths before debugging pipeline behavior.
2. Confirm the expected artifacts exist for the stage you are running:
   `data/detections.json`, `data/patches.json`, `data/verified.json`, and
   optional `data/risk.json`.
3. Re-run the failing verifier command with `--include-errors`, and narrow with
   `--id <detection-id>` or `--limit 1` when possible.
4. Use rules mode first for setup debugging. Remote LLM modes add network,
   credential, model, and rate-limit variables.

## Setup Issues

- `make doctor` reports missing packages: run the repository setup path from the
  README, then re-run `make doctor` before starting the pipeline.
- `python -m ...` commands fail with import errors: confirm you are running from
  the repository root and using the same Python that installed
  `requirements.txt`.
- Output files are missing: run the stages in order: `make detect`, `make
  propose`, `make verify`, then `make risk` and `make schedule` if you need a
  prioritized queue.
- Generated artifacts look stale: remove or move only the specific stale output
  you are regenerating, then re-run the producing stage. Do not mix detections,
  patches, and verifier results from different input corpora.

## Tooling Issues

- Missing `kubectl`: install it or run verifier experiments with
  `--no-require-kubectl` only when you explicitly accept that schema/admission
  validation is not being checked.
- Missing `kube-linter` or `kyverno`: install the missing scanner before running
  detector jobs or verifier rescans. For Grok 4.3 benchmark runs, prefer stable
  local paths under `tmp/tool-cache/bin/` and pass those same paths to every
  rerun:
  `GROK43_KUBE_LINTER_CMD=tmp/tool-cache/bin/kube-linter GROK43_KYVERNO_CMD=tmp/tool-cache/bin/kyverno make benchmark-grok43-50`.
  Re-run with the same binary paths CI uses if local results differ.
- Kind cluster is unavailable: run `make kind-up`, wait for the cluster to be
  ready, then run `make fixtures` so RBAC and NetworkPolicy fixture assumptions
  are present.
- Kyverno policies are not found: pass the expected policy directory with
  `--policies-dir data/policies/kyverno` when using `--enable-rescan`.

## API Key Issues

- Rules mode does not require an API key. Use it to separate local setup failures
  from provider failures.
- Grok mode reads the environment variable named by `grok.api_key_env`, normally
  `XAI_API_KEY`.
- Vendor/OpenAI-compatible mode reads `vendor.api_key_env`, normally
  `OPENAI_API_KEY`.
- vLLM mode reads `vllm.api_key_env`, normally `RUNPOD_API_KEY`, and also needs
  a reachable endpoint in `configs/run.yaml`.
- For `401` or `403` responses, check that the key is exported in the shell that
  runs the command and that the configured model is enabled for the account.
- For `429` or timeout failures, reduce `--jobs`, lower retries, or run a smaller
  detection batch. Use `scripts/probe_grok_rate.py` before increasing Grok
  concurrency.
- Keep provider keys in environment variables or your secret manager. Do not
  commit keys to `configs/run.yaml`, generated JSON, logs, or issue comments.

## Kubernetes Verification Issues

- `ok_schema=false`: inspect the `kubectl dry-run failed` error. Common causes
  are the wrong Kubernetes context, missing CRDs, missing namespaces, or fixtures
  that were not applied to the verification cluster.
- `ok_policy=false`: the patch did not clear the targeted policy. Re-run with
  `--include-errors` and compare the patched YAML against the policy family.
- `ok_safety=false`: the patch violates a project safety invariant such as a
  privileged container, dangerous capability, unsafe hostPath, missing image, or
  malformed workload container list.
- `ok_rescan=false`: the patched manifest still triggers kube-linter or Kyverno
  when `--enable-rescan` is active. Confirm scanner versions and policy bundles
  match the environment you are comparing against.
- Dry-run passes locally but fails in CI: compare Kubernetes versions, admission
  plugins, CRDs, namespaces, service accounts, and policy bundles. Server-side
  dry-run uses the API server, so cluster setup matters.

## Patch Review Issues

- If `accepted=false`, do not queue or apply the patch. Use the `ok_*` flags and
  `errors` list to decide whether to regenerate, adjust fixtures, or escalate.
- If an LLM-backed patch has `attempt_errors`, treat them as review context. A
  later attempt may have passed structure checks while still deserving closer
  operator review.
- If a secret-like environment variable was rewritten to `secretKeyRef`, verify
  the referenced Secret and key exist in the target namespace before deployment.
  The tool removes inline literal values; it does not rotate or populate live
  secret data.
- If a patch affects service selectors, service accounts, host networking,
  hostPath, capabilities, probes, or resource limits for a production workload,
  require human review even when verifier gates pass.
- If a workload is managed by an operator, Helm release, Kustomize overlay, or
  external controller, make the change in the owning source rather than applying
  generated YAML out of band.

## GitOps Issues

- Prefer the GitOps flow: verify patches, write accepted patches to a branch,
  review the diff, let CI re-run verifier checks, merge, and allow Argo CD or
  Flux to reconcile.
- If `scripts/gitops_writeback.py` skips a detection, confirm the detection has
  an on-disk manifest path under the target `--repo-root`.
- If a post-merge rollout fails, use the owning Git history first: revert the PR
  or open a rollback PR, then use cluster rollback commands only as an incident
  response measure.
