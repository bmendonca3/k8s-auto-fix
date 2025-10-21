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
```
python scripts/gitops_writeback.py \
  --detections data/detections.json \
  --verified data/verified.json \
  --repo-root /path/to/your/manifest-repo \
  --branch k8s-auto-fix/patches
```

Notes
- The script modifies only files under `--repo-root` and skips detections without on-disk manifest paths.
- To automatically open a GitHub PR, install the `gh` CLI and stay authenticated.

