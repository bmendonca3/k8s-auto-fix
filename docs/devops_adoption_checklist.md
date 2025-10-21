# DevOps Adoption Checklist for `k8s-auto-fix`

This checklist summarizes the operational steps required to introduce the closed-loop auto-fix pipeline into a CI/CD environment. Each item links back to repository artifacts or commands so practitioners can execute the rollout incrementally.

1. **Bootstrap environment**
   - Install Python 3.11+ and run `pip install -r requirements.txt`.
   - Provision access to `kubectl`, `kube-linter`, and Kyverno/OPA binaries; verify with `make doctor`.

2. **Reproduce baseline evidence**
   - Execute `make reproducible-report` to regenerate Table~\ref{tab:eval_summary} metrics.
   - Review generated artifacts under `data/eval/` and `docs/reproducibility/`.

3. **Integrate detectors in CI**
   - Wire `make detect` into pre-merge checks; persist `data/detections.json` as a build artifact.
   - Configure policy bundles via `configs/run.yaml` to match organizational guardrails.

4. **Enable proposer and verifier gates**
   - Run `make propose` followed by `make verify`; ensure `data/patches.json` and `data/verified.json` are archived.
   - For LLM-backed mode, populate API credentials in `configs/run.yaml` and re-run `make propose-llm`.

5. **Schedule remediation work**
   - Execute `make schedule` (bandit) and `make schedule-fifo` (baseline) to compare queue orderings.
   - Export `data/scheduler/*.json` to your ticketing or work-intake system.

6. **Publish guardrail fixtures**
   - Apply the RBAC and NetworkPolicy fixtures under `infra/fixtures/` to staging clusters before live evaluation.
   - Validate fixtures via `make verify-fixtures`.

7. **Instrument telemetry and reviews**
   - Enable `LOG_LEVEL=INFO` and collect logs under `logs/` for post-run reviews.
   - Run `make operator-survey` to capture human feedback per queue sprint and store responses in `docs/operator_survey.md`.

8. **Roll out incrementally**
   - Start with deterministic rules mode; gate LLM merges behind manual approval until telemetry matches Table~\ref{tab:eval_summary}.
   - Monitor risk reduction deltas via `scripts/scheduler_sweep.py --report`.

9. **Embed in continuous delivery**
   - Add a nightly job invoking `make e2e` against representative corpora.
   - Gate production deploys on `data/verified.json` showing `accepted=true` and `errors=[]` for all targeted manifests.

10. **Document incident response hooks**
    - Capture rollback procedures and guardrail overrides in `docs/security_considerations.md`.
    - Align with SOC runbooks by linking `data/risk/calibration.json` (generated via `make risk-calibration`) to vulnerability triage workflows.

Completing the checklist ensures security, reliability, and DevOps stakeholders share a common view of the pipeline’s guarantees and intervention points.
