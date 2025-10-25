# Cross-Cluster Replay Checklist

This document tracks the outstanding IEEE Access request for replicated live-cluster replays on managed Kubernetes providers. Once the data below is collected, Table&nbsp;9 in `paper/access.tex` can be populated automatically.

## Target Artifacts

Produce the following per provider (drop them into the repository so the LaTeX build can cite their hashes):

| Provider | Results JSON | Summary CSV | Notes |
| -------- | ------------ | ----------- | ----- |
| EKS | `data/cross_cluster/eks/results.json` | `data/cross_cluster/eks/summary.csv` | ✅ 198/200 dry-run + live success; cluster created with `eksctl` (t3.medium, AL2023) |
| GKE | `data/cross_cluster/gke/results.json` | `data/cross_cluster/gke/summary.csv` | ✅ 200/200 dry-run + live success (e2-standard-4, 1.33.5-gke); default add-ons only |
| AKS | `data/cross_cluster/aks/results.json` | `data/cross_cluster/aks/summary.csv` | ✅ 197/200 dry-run + live success (Standard\_D4s\_v3, AKS 1.33.3); default add-ons |

Each summary CSV should contain the header emitted by `scripts/run_live_cluster_eval.py` (`generated,manifests,dry_run_pass,live_apply_pass,live_failures`). The JSON captures per-manifest outcomes that feed the failure taxonomy if we need to drill down.

## Prerequisites

1. `kubectl` authenticated against the target cluster.
2. The evaluation fixtures installed: `kubectl apply -f infra/fixtures/bootstrap.yaml` (see `docs/dry_run_provisioning.md` for details).
3. `python3` with the repo’s virtual environment activated (`pip install -r requirements.txt` if needed).

## Replay Steps (per provider)

```bash
# Example for EKS; adjust context and output paths per provider.
export KUBECONFIG=/path/to/eks/kubeconfig
kubectl config use-context <eks-context>

# Optional: double-check fixtures are present
kubectl get ns gitops-fixtures

# Run the live replay
PYTHONPATH=. python scripts/run_live_cluster_eval.py \
  --manifests data/live_cluster/batch \
  --namespace-prefix cross-cluster-eks \
  --output data/cross_cluster/eks/results.json \
  --summary data/cross_cluster/eks/summary.csv
```

After the run completes, record the SHA256 for both files (`shasum -a 256 …`)—those hashes are cited in the paper.

## Metrics to Surface

For each provider capture:

- `manifests`: number of manifests replayed (should be 200 for parity with the Kind run).
- `live_apply_pass / manifests`: live success rate.
- `dry_run_pass / manifests`: dry-run alignment (should stay at 100%).
- Any rollbacks or fixture-specific failures (note them in this doc or `logs/` for reviewer context).

Populate `paper/access.tex` (Table 9) by replacing the italic placeholders once the summaries are in place.

## What’s Needed From the Operator

1. Access to non-production EKS, GKE, and AKS clusters where staging fixtures can be installed.
2. Read/write permission to create and clean namespaces during the replay.
3. The generated `results.json` and `summary.csv` pairs (plus the SHA256 hashes) checked into the repository under the paths above, or shared out-of-band so we can commit them.
