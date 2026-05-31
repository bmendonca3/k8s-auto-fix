# Cross-Cluster Replay Artifacts

Provider-labeled replay outputs live in the layout below. Each provider directory
contains the raw `results.json` and a compact `summary.csv` used by the paper's
cross-cluster replication table.

Current summaries:

| Provider | Manifests | Dry-run pass | Live/apply pass | Failures |
|---|---:|---:|---:|---:|
| EKS | 200 | 198 | 198 | 0 |
| GKE | 200 | 200 | 200 | 0 |
| AKS | 200 | 200 | 200 | 0 |

Layout:

```
data/cross_cluster/
├── eks/
│   ├── results.json
│   └── summary.csv
├── gke/
│   ├── results.json
│   └── summary.csv
└── aks/
    ├── results.json
    └── summary.csv
```

Refer to `docs/cross_cluster_replay.md` for the collection steps.
