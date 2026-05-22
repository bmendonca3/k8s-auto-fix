# Roadmap

This roadmap consolidates the next product, research, and repository-hardening
tracks for `k8s-auto-fix`. The detailed backlog lives in
`docs/POSSIBLE_IMPROVEMENTS.md`; this file keeps the active direction easy to
scan.

## Now

1. Keep the contributor baseline healthy.
   - `pyproject.toml`, CI, contributor docs, `make doctor`, `make test`, and
     `make validate-configs` are now in place; CI also runs `make secret-scan`
     and lightweight operator smoke checks.
   - README/Make/helper-script drift tests now guard the documented command
     surface.
   - Next maintenance step: add lint/static-analysis once the repo is ready to
     enforce formatting consistently.

2. Continue repository hygiene work.
   - Artifact policy, artifact indexing, and safer ignore rules are now in place.
   - Next maintenance step: move or externalize legacy tracked local artifacts
     only after deciding which evidence files must remain in git.

3. Continue proposer modularization.
   - JSON Patch path sanitization and redundant-op minimization now live in
     `src/proposer/patch_safety.py`, and prompt/guidance assembly now lives in
     `src/proposer/prompts.py`.
   - Rule-based policy dispatch now uses an explicit `RULE_STRATEGIES` registry.
   - Policy-aware retry budget resolution now lives in `src/proposer/retry.py`.
   - Patch records and proposer metrics now report attempt counts and retry
     budget ceilings.
   - Opt-in non-rules model-response caching now lives behind
     `src/proposer/response_cache.py` with input/config hashes recorded on patch
     records.
   - Next extraction candidate: typed patch proposal objects before JSON Patch
     serialization.

4. Keep operator review surfaces usable.
   - Patch diffs, verifier rejection summaries, scheduler explanations, queue
     health reports, and artifact traceability records are now available as
     lightweight script entry points; `scripts/build_review_packet.py` composes
     them into a bounded review packet with full and concise Markdown modes,
     and can include rollout-annotated scheduler batches.
   - The concise architecture and operator review flow are now documented in
     `docs/ARCHITECTURE.md`.
   - Next maintenance step: wire the concise packet into whichever PR or release
     workflow operators choose.

5. Keep the tiny regression pack fast and representative.
   - `data/samples/tiny_regression/`, `scripts/run_tiny_regression.py`, and
     `make tiny-regression` now provide CI-safe coverage across builtin
     detector checks, rule-based proposer/verifier behavior, scheduler priority,
     queue enqueue/pick, and a benign negative manifest.
   - Next maintenance step: expand it when new policy families or verifier gates
     become important enough for always-on coverage.

6. Start batch-aware scheduling.
   - `src/scheduler/batches.py` can group scheduled fixes by policy, namespace,
     owner/team, or root cause with deterministic ordering and max-batch
     splitting; the scheduler CLI can emit batch JSON with `--batch-group-by`,
     `--batch-max-size`, and `--batches-out`.
   - `src/scheduler/rollout.py` can annotate batch summaries with
     change-window and blast-radius metadata before they are handed to review or
     GitOps workflows.
   - Review packets can now include rollout annotations with `--batches`.
   - `scripts/gitops_writeback.py` can now produce a dry-run/JSON writeback
     plan that reports skipped patches and paths before mutating a repository.
   - Next maintenance step: connect rollout annotations to GitOps handoff
     metadata once that surface needs them.

7. Tighten reproducibility evidence.
   - `scripts/run_pipeline.py` records declared stage inputs and file hashes in
     manifests/status JSON and adds remediation hints for failed stages, while
     `scripts/build_evidence_manifest.py` rolls up claim coverage across
     selected artifacts, can ingest pipeline manifest/status stage metadata,
     and can compare artifact labels against an expected claim table.
   - Current enforcement: `make evidence-manifest-claims-enforce` now points at
     the checked-in paper claim inventory in `data/eval/paper_claims.json` and
     evidence mapping in `data/eval/paper_evidence_spec.json`.

## Next

1. Add deeper stage-specific diagnostics to pipeline failures where stderr can
   be captured without bloating status files.
2. Turn retrieval-augmented prompting into a measured experiment with acceptance,
   latency, token, and cost deltas.
3. Promote concise review-packet output into PR/release automation once
   operators agree on the preferred evidence workflow.

## Later

1. Add batch-aware and operator-aware scheduling constraints for production
   rollout windows, owner routing, and starvation limits.
2. Add dashboard and notification surfaces for detections, patch review,
   verifier results, risk, and queue state.
3. Expand live-cluster coverage across Kubernetes distributions when the cost and
   maintenance burden are justified by the research or product need.
4. Add GitOps rollback workflows with field ownership checks, sync status, and
   revert pull request generation.
5. Package policy profiles for CIS, Pod Security Standards, NSA/CISA, and
   organization-specific baselines.
