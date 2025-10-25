# Cross-Cluster Replay Artifacts

Drop provider-specific outputs here once the managed-cluster replays complete.

Expected layout:

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
