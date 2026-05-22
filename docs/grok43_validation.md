# Grok 4.3 Validation Notes

## Staged Results

The safe Grok 4.3 staged validation on 2026-05-21 used namespaced artifacts and
did not update paper-facing or canonical Grok-5k metrics.

| Run namespace | Detections | Accepted | Rate | Notes |
| --- | ---: | ---: | ---: | --- |
| `data/batch_runs/grok43_20260521_50` | 50 | 50 | 100.0% | Passed the 50-detection gate. |
| `data/batch_runs/grok43_20260521_200` | 200 | 171 | 85.5% | Passed the 170/200 gate. |
| `data/batch_runs/grok43_20260522_smoke50` | 50 | 50 | 100.0% | Stable scanner-path smoke gate before 5k. |
| `data/batch_runs/grok43_20260522_5000` | 5,000 | 4,473 | 89.46% | Full Grok 4.3 run; not promoted to paper-facing metrics. |

The complete 5k Grok 4.3 result now exists under a fresh namespace with stable
scanner paths and run-manifest scanner metadata. Keep historical Grok-5k
artifacts intact until this result is explicitly selected for publication.
Pre-run probes are retained under `data/batch_runs/grok43_20260522_probe_c1`,
`data/batch_runs/grok43_20260522_probe_c2`, and
`data/batch_runs/grok43_20260522_probe_c4`.

## Failure Triage

The 200-run rejected 29 records. Twenty-eight rejects are expected full-profile
safety blocks for Cilium-style privileged infrastructure. The patches clear the
targeted policy, schema, and rescan gates, but retain CNI hostPath mounts such as
`/var/run/cilium`, `/var/run/netns`, and `/sys/fs/bpf` that are outside the
verifier hostPath allowlist. These should remain rejected unless an operator
approves a narrow Cilium exception.

Record `00120` is the one non-Cilium miss. It is a PostgreSQL StatefulSet
`run_as_non_root` finding where an init container combines `runAsNonRoot: true`
with `runAsUser: 0`. The verifier now rejects that contradiction directly instead
of relying on the rescan gate to catch it.

The 5k run rejected 527 records: 519 included safety failures, 13 included policy
failures, and 2 included rescan failures. The most common failure family remains
hostPath safety blocks for privileged infrastructure paths outside the verifier
allowlist. The 5k run also exposed an optional patch-minimization crash on an
invalid JSON Pointer; the minimizer now keeps the original patch instead of
crashing a Grok batch.

## Reproducible Scanner Setup

Future Grok 4.3 benchmark runs should use stable scanner paths under the ignored
tool cache:

```sh
mkdir -p tmp/tool-cache/bin
cp /path/to/kube-linter tmp/tool-cache/bin/kube-linter
cp /path/to/kyverno tmp/tool-cache/bin/kyverno
chmod +x tmp/tool-cache/bin/kube-linter tmp/tool-cache/bin/kyverno
```

The benchmark Make targets default to:

```sh
GROK43_KUBE_LINTER_CMD=tmp/tool-cache/bin/kube-linter
GROK43_KYVERNO_CMD=tmp/tool-cache/bin/kyverno
```

`scripts/run_grok43_benchmark.py` records the requested command, resolved path,
binary SHA-256, file metadata, version output, and Kyverno policy bundle hash in
future run manifests before live Grok calls begin.
