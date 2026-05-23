# Possible Improvements

This list captures practical next improvements for `k8s-auto-fix` after reviewing
the current repository layout, README, canonical TODO tracker, existing roadmap
docs, scripts, source modules, tests, and tracked artifacts.

## Implemented On `improvmenets`

This branch has already converted several backlog items into concrete changes:

1. CI and contributor baseline: GitHub Actions, `pyproject.toml`, pytest-based
   `make test`, `make doctor`, contributor docs, and entry-point tests.
2. Config discoverability and validation: `configs/README.md`,
   `scripts/validate_configs.py`, and config docs tests.
3. Repository hygiene: broader ignore rules, artifact retention policy,
   artifact indexer, docs link checker, and safe generated-output cleanup helper.
4. Pipeline ergonomics: dry-run `scripts/run_pipeline.py`, `make pipeline-plan`,
   optional reproducibility manifest output, and a rules-mode command plan that
   avoids cluster/API-key requirements.
5. Proposer modularization and quality: JSON Patch safety helpers moved to
   `src/proposer/patch_safety.py`, redundant patch ops are minimized, and the
   tracked smoke patch fixture was regenerated with max patch length reduced
   from 15 operations to 5.
6. Operator-facing documentation: troubleshooting guide, security model, roadmap,
   and artifact policy.
7. Operator review and verifier triage: `scripts/render_patch_diff.py` renders
   before/after YAML diffs, and `scripts/verifier_report.py` groups verifier
   rejects by failing gate, policy, and error with next-action hints.
8. Scheduler, queue, and artifact explainability: `scripts/scheduler_explain.py`
   explains priority scores, `scripts/queue_report.py` audits queue health
   without mutating SQLite state, and `scripts/artifact_traceability.py` emits
   per-artifact SHA-256/producer records.
9. Tiny regression fixture pack: `data/samples/tiny_regression/` and
   `scripts/run_tiny_regression.py` provide CI-safe coverage across builtin
   detector checks, rule-based proposer/verifier accept/reject behavior,
   scheduler priority, queue enqueue/pick, and a benign negative manifest.
10. Review packet and batch scheduling foundations: `scripts/build_review_packet.py`
    composes bounded operator review packets with full and concise Markdown
    modes, and `src/scheduler/batches.py` groups scheduled fixes by policy,
    namespace, owner/team, or root cause.
11. CLI contracts and operator smoke paths: documented console scripts and helper
    scripts now have help-output contract tests, and CI runs lightweight
    pipeline, scheduler-batch, and review-packet smoke checks.
12. Architecture, rollout, and prompt modularity: `docs/ARCHITECTURE.md`
    documents the end-to-end flow and review invariants,
    `src/scheduler/rollout.py` annotates batch summaries with change-window and
    blast-radius metadata, and `src/proposer/prompts.py` owns LLM prompt and
    guidance assembly.
13. Pipeline resumability and secret hygiene: `scripts/run_pipeline.py` can emit
    deterministic per-stage status and resume completed matching stages, and
    `scripts/scan_secrets.py` provides a CI-safe secret pattern scanner.
14. Evidence manifests and documentation drift checks: pipeline status now
    records output hashes when artifacts exist, `scripts/build_evidence_manifest.py`
    links selected artifacts to producer commands and claim labels, and README
    command-drift tests keep documented targets and helper scripts anchored.
15. Pipeline provenance, rollout review, and retry budgets: pipeline status and
    manifests now include declared stage inputs with file hashes, review packets
    can include rollout-annotated scheduler batches, evidence manifests summarize
    claim coverage plus expected claim-table and pipeline stage metadata, and
    proposer retry budgets can be tuned and measured by policy.
16. Model-response caching and GitOps plan safety: non-rules proposer runs can
    opt into validated response caching keyed by input/config hashes, and
    `scripts/gitops_writeback.py` now has dry-run/plan output with skip reasons
    plus a CI smoke target.

## Highest-Impact Candidates

1. Add CI for unit tests, smoke tests, and artifact checks.
   - Status: first pass implemented with `.github/workflows/ci.yml`, pytest,
     docs link checks, config validation, and smoke targets.
   - Next pass: add lint/static analysis once formatting expectations are stable.

2. Add Python project metadata and reproducible dependency locking.
   - Status: first pass implemented with `pyproject.toml`, console scripts,
     pytest config, and dependencies aligned with `requirements.txt`.
   - Next pass: decide whether the project wants a committed lockfile and
     optional dependency groups.

3. Split the proposer CLI into smaller modules.
   - Status: first pass implemented for patch path sanitization and redundant-op
     minimization in `src/proposer/patch_safety.py`; prompt assembly and
     policy guidance now live in `src/proposer/prompts.py`; rule dispatch now
     uses an explicit `RULE_STRATEGIES` registry; policy-aware retry budget
     resolution now lives in `src/proposer/retry.py`; patch records and proposer
     metrics now report attempt counts and retry budget ceilings; opt-in
     non-rules response caching now lives in `src/proposer/response_cache.py`.
   - Next pass: introduce typed patch proposal objects before JSON Patch
     serialization.

4. Clean tracked generated artifacts, logs, binaries, and local state.
   - Status: artifact policy, ignore rules, artifact indexing, and safe cleanup
     helpers are now in place.
   - Next pass: decide which legacy tracked artifacts should remain as evidence
     and which should move to releases, object storage, or Git LFS.

5. Turn the current research pipeline into an installable CLI.
   - Status: `pyproject.toml` now defines console entry points for the main
     package commands.
   - Next pass: expand packaging checks once the scripts graduate from
     repository helpers to installed commands.

6. Add a single pipeline orchestrator command.
   - Status: first pass implemented as `scripts/run_pipeline.py`, with dry-run,
     rules-mode defaults, reproducibility manifest output, per-stage status
     JSON, resume-from-status support, input/output path metadata,
     existing-file hashes, concise failure summaries, and stage remediation
     hints for failed runs.
   - Next pass: add deeper stage-specific diagnostics when real command stderr
     is intentionally captured.

7. Improve configuration validation.
   - Status: `scripts/validate_configs.py` and `configs/README.md` now validate
     and document the checked-in YAML presets.
   - Next pass: add stricter typed config models if the config surface expands.

8. Add low-cost continuous regression fixtures.
   - Status: first pass implemented with `data/samples/tiny_regression/`,
     `scripts/run_tiny_regression.py`, tests, and a `make tiny-regression`
     target that avoids external scanner, cluster, and API-key dependencies.
   - Next pass: expand the pack across more policy families, verifier gates,
     and README-command drift checks.

9. Harden reproducibility with manifest indexes.
   - Status: first pass implemented with tracked-artifact indexing and selected
     artifact traceability records; `scripts/build_evidence_manifest.py` now
     links selected artifacts to producer commands, claim labels, sizes, output
     hashes, claim-coverage summaries, optional expected claim-table coverage,
     and optional pipeline manifest/status stage metadata; pipeline manifests
     now expose stage input hashes for downstream evidence bundles.
   - Latest pass: `data/eval/paper_claims.json` and
     `data/eval/paper_evidence_spec.json` now provide a checked-in paper claim
     inventory, and `make evidence-manifest-claims-enforce` fails if any listed
     claim lacks evidence.

10. Refresh the public-facing product story.
    - Status: first pass implemented with operator docs, troubleshooting,
      security model, patch diff rendering, verifier triage, scheduler
      explanations, queue reports, full review-packet assembly, and concise
      PR/release summaries; `docs/ARCHITECTURE.md` now includes the pipeline
      diagram, operator review flow, trust boundaries, and review invariants.
    - Next pass: add a curated before/after walkthrough.

Most of the first-pass developer-experience and hygiene items above now have a
working implementation on this branch. Remaining high-leverage candidates are
deeper proposer modularization, richer batch-aware scheduling constraints, and
GitOps rollback/writeback hardening beyond the first dry-run plan.

## Detector Improvements

1. Add richer policy taxonomy metadata for every detection.
2. Normalize policy IDs across kube-linter, Kyverno, custom guards, and paper
   tables.
3. Add deterministic deduplication when multiple scanners flag the same root
   cause.
4. Add confidence and severity fields that are separate from downstream risk.
5. Add manifest provenance fields: source corpus, file hash, resource path, and
   scanner version.
6. Expand coverage for CRDs and operator-managed resources with safe fallbacks
   when schemas are missing.
7. Add negative fixtures for benign patterns that should not trigger findings.
8. Capture scanner stderr and version metadata in structured output.

## Proposer Improvements

1. Extract the rule-based proposer into policy-specific strategy modules.
2. Add typed patch proposal objects before serializing to RFC 6902 JSON Patch.
3. Add patch minimization as a reusable post-processing pass.
4. Add patch explanation generation for operator review.
5. Add a patch diff renderer that shows Kubernetes YAML before/after snippets.
6. Add retry budgets that adapt by policy family and historical success rate.
7. Cache model responses with input/config hashes to make LLM experiments cheaper.
   - Status: first pass implemented in `src/proposer/response_cache.py` for
     non-rules modes; cache writes happen only after response validation and
     patch records carry cache hit/key/path/input/config hash metadata.
8. Add explicit cost telemetry for each LLM-backed run.
9. Add model comparison harnesses for accuracy, latency, cost, and failure modes.
10. Promote retrieval-augmented prompting from roadmap/status note to a measurable
    experiment with acceptance uplift and token overhead.

## Verifier Improvements

1. Split policy checks, Kubernetes dry-run checks, JSON Patch guards, and semantic
   regression checks into independently testable modules.
2. Add structured failure codes for every rejection path.
3. Add a verifier report command that groups rejects by root cause and suggested
   next fix.
4. Add snapshot fixtures for accepted and rejected patch examples.
   - Status: the Grok 4.3 `00120` triage added a regression fixture for the
     `runAsNonRoot: true` plus `runAsUser: 0` contradiction on init containers.
5. Add Kubernetes version compatibility tests for gate behavior.
6. Add optional Open Policy Agent or Pod Security Admission checks as another
   verifier profile.
7. Add stronger idempotence checks across repeated patch application.
8. Add field ownership and server-side apply conflict detection for GitOps flows.

## Risk and Scheduling Improvements

1. Add CVSS and exploit maturity signals alongside EPSS and KEV.
2. Add image-specific vulnerability enrichment when container image metadata is
   available.
3. Add organization-specific asset criticality as an optional scheduling input.
4. Add batch-aware scheduling that groups fixes by namespace, team, policy, or
   root cause.
   - Status: first pass implemented in `src/scheduler/batches.py` as a pure
     grouping helper with metadata merging, deterministic ordering, and
     max-batch splitting; `src.scheduler.cli` can now emit batch JSON with
     `--batch-group-by`, `--batch-max-size`, and `--batches-out`.
   - Next pass: connect batches to change-window and GitOps workflow metadata.
5. Add "change window" and "blast radius" constraints for production rollout.
   - Status: first pass implemented in `src/scheduler/rollout.py` as a pure
     helper that annotates batch summaries with selected windows, blast-radius
     counts, and allow/block reasons without mutating queue state; review
     packets can now include the rollout annotations when `--batches` is
     supplied.
   - Next pass: wire rollout annotations into GitOps handoff metadata.
6. Add an explainability report for why a fix was prioritized.
7. Add simulations for operator overrides and rejected maintenance windows.
8. Add fairness guardrails that cap starvation by severity and owner/team.

## Queue and GitOps Improvements

1. Move queue state out of a tracked root `queue.db` into ignored runtime state.
2. Add migrations or schema versioning for the queue database.
3. Add queue locking and concurrency controls for multi-worker operation.
4. Add GitOps writeback tests that cover branch naming, commit messages, PR body
   generation, and rollback metadata.
5. Add dry-run PR generation for repositories that should not be mutated.
   - Status: first pass implemented for pre-mutation planning with `--dry-run`,
     `--plan-out`, skip reasons, and `make gitops-plan-smoke`.
6. Add integration with Argo CD or Flux sync status.
7. Add rollback playbooks and automatic revert PR generation when a fix fails.
8. Add owner/team routing metadata for queued fixes.

## Live-Cluster and Evaluation Improvements

1. Add a scheduled simulation replay in CI to catch fixture drift.
2. Add a periodic live replay workflow outside normal PR CI.
3. Add explicit Kubernetes distribution coverage: Kind, AKS, EKS, GKE, and
   OpenShift where feasible.
4. Add CRD/controller readiness checks before replaying CRD-heavy manifests.
5. Add resource usage telemetry for verifier and live replay runs.
6. Add failure minimization that extracts the smallest manifest reproducing a
   live-cluster failure.
7. Add a reproducible "tiny live replay" for contributors without cloud access.
8. Add clear guardrails for when full-corpus replay is not worth the cost.

## Testing and Quality Improvements

1. Add ruff or equivalent linting.
2. Add static typing with mypy or pyright for core modules.
3. Add property-based tests for JSON Patch safety beyond current guard cases.
4. Add CLI contract tests for every documented command.
   - Status: first pass implemented for console-script help and representative
     helper-script help surfaces.
5. Add fixture freshness checks so README commands do not drift.
   - Status: first pass implemented with README/Make/helper-script drift tests.
6. Add dependency vulnerability scanning.
7. Add secret scanning before publishing artifacts.
   - Status: first pass implemented with `scripts/scan_secrets.py`,
     `make secret-scan`, tests, and CI wiring.
8. Add tests that prove generated docs/tables match source metrics.

## Documentation Improvements

1. Consolidate roadmap material from `notes/`, `docs/polish_todo.md`,
   `docs/future_work_rag.md`, and paper future-work notes into one active roadmap.
2. Add a "repository hygiene" page explaining which artifacts are canonical,
   generated, archived, or external.
3. Add a contributor guide with environment setup, test tiers, data policy, and
   evaluation cost expectations.
4. Add a troubleshooting guide for kube-linter, Kyverno, Kind, API keys, and
   live-cluster failures.
5. Add a security model page that explains what the tool will and will not patch.
6. Add examples of accepted, rejected, and manually escalated patches.
7. Add a paper reproduction walkthrough that starts from a clean clone.
8. Add a changelog for research artifact updates and metric refreshes.

## Packaging and Repository Hygiene Improvements

1. Remove committed `.DS_Store` files and broaden ignore rules for local metadata.
2. Remove or externalize `AWSCLIV2.pkg`.
3. Move logs out of git unless they are small, curated evidence artifacts.
4. Move large generated data to compressed release artifacts or Git LFS.
5. Add a `data/samples/` directory for tiny fixtures that are safe to keep in git.
6. Add `make clean-generated` for ignored outputs only.
7. Add `make doctor` to check local prerequisites and tool versions.
8. Add a license file if the project is intended to be reusable by others.

## Productization Improvements

1. Add a read-only dashboard for detections, proposed patches, verifier results,
   risk, and queue state.
2. Add RBAC-aware operator workflows: reviewer, approver, deployer, auditor.
3. Add notification integrations for Slack, Teams, or email.
4. Add Kubernetes admission webhook mode as an optional deployment path.
5. Add a controller/operator mode that watches namespaces and proposes fixes.
6. Add policy-pack profiles for CIS, Pod Security Standards, NSA/CISA, and
   organization-specific baselines.
7. Add multi-cluster inventory support.
8. Add audit exports for compliance teams.

## Suggested First Sprint

1. Continue low-risk proposer extraction toward typed patch proposal objects.
2. Decide retention for legacy tracked binaries, local metadata, logs, and
   runtime databases using the new artifact index.
3. Expand the review packet into PR/release templates once operators agree on
   the preferred evidence format.
4. Add lint/static-analysis only after agreeing on formatting and typing scope.
