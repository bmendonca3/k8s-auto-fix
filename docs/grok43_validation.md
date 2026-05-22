# Grok 4.3 Validation Notes

## Staged Results

The safe Grok 4.3 staged validation on 2026-05-21 used namespaced artifacts and
did not update paper-facing or canonical Grok-5k metrics.

| Run namespace | Detections | Accepted | Rate | Notes |
| --- | ---: | ---: | ---: | --- |
| `data/batch_runs/grok43_20260521_50` | 50 | 50 | 100.0% | Passed the 50-detection gate. |
| `data/batch_runs/grok43_20260521_200` | 200 | 171 | 85.5% | Passed the 170/200 gate. |

The complete 5k Grok 4.3 result should be generated only after the scanner setup
is pinned and repeatable. Keep historical Grok-5k artifacts intact until a full
Grok 4.3 run is explicitly selected for publication.

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
