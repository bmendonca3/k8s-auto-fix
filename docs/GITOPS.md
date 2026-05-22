# GitOps Integration and Drift Control

Goals
- Avoid out-of-band drift: always write changes back to source control.
- Provide auditable PRs with minimal diffs and automated checks.

Proposed flow
- Generate patches and verify with the triad.
- Use `scripts/gitops_writeback.py` to apply accepted patches to the repo in a new branch.
- Open a PR with verifier checks in CI (dry-run and policy re-check on the PR artifacts).
- Merge after review; let Argo CD/Flux handle reconciliation.
- Provide rollback hooks (revert PR or `kubectl rollout undo`) in case of post-merge validation failures.

Command example
Preview the writeback first:
```
python scripts/gitops_writeback.py \
  --detections data/detections.json \
  --verified data/verified.json \
  --repo-root /path/to/your/manifest-repo \
  --plan-out tmp/gitops-writeback-plan.json
```

Apply the accepted plan to a branch:
```
python scripts/gitops_writeback.py \
  --detections data/detections.json \
  --verified data/verified.json \
  --repo-root /path/to/your/manifest-repo \
  --branch k8s-auto-fix/patches \
  --no-pr
```

Notes
- `--dry-run` prints the plan to stdout. `--plan-out` writes the same plan as JSON and exits without changing files, branches, commits, or PRs.
- The plan reports files that would be modified and skipped patches with reasons such as missing `manifest_path`, rejected patches, unsafe paths outside `--repo-root`, missing files, and invalid JSON Patch application.
- In write mode, the script modifies only files under `--repo-root` and skips detections without on-disk manifest paths.
- Add `--require-kubectl` in write mode to run `kubectl apply --dry-run=server -f <file>` for every modified manifest file before staging and committing.
- PR creation is opt-in. Add `--create-pr` only after installing the `gh` CLI and authenticating to the host used by the repo remote (`github.com` or `github.gatech.edu`).
