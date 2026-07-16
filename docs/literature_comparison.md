# Literature Comparison Notes

**Date:** 2026-05-30
**Context:** Internal scratchpad for aligning the manuscript's comparison language with the current artifacts.

This file is not submission prose. Overleaf is the authoritative manuscript source; keep denominators separate when discussing baselines.

## Current Framing

| Topic | Current artifact-backed statement | Notes |
|---|---:|---|
| Deterministic full run | 13,589/13,656 patched items accepted (99.51%); auto-fix rate 0.8646 over 15,718 detections; median patch size 8 | `data/metrics_latest.json`, current raw `.json.gz` inputs |
| Supported rules corpus | 1,264/1,264 accepted (100.00%) | `data/eval/unified_eval_summary.json` |
| Grok-5k | 4,426/5,000 accepted (88.52%) | `data/batch_runs/grok_5k/metrics_grok5k.json` |
| Live replay | 1,000/1,000 dry-run/apply accepted in the fixture-seeded Kind/Kubernetes 1.34.0 evaluation environment | `data/live_cluster/summary_1k.csv` |
| Kyverno CLI live aggregate | 364/381 detections accepted (95.54%) once patched manifests pass our verifier | `data/baselines/kyverno_baseline_live.json` |
| Kyverno simulated mean | 67.98% unweighted mean across 17 simulated policy rows | `data/baselines/kyverno_baseline_simulated.csv` |
| Verifier gate ablation | 78.9% full-verifier acceptance on 19 patched samples; no-policy reaches 100% but has 4 escapes | `data/ablation/verifier_gate_metrics.json` |

Do not present the 67.98% Kyverno simulated mean and the 78.9% verifier-ablation result as a like-for-like percentage-point win. They use different denominators and answer different questions. The safe language is:

> The Kyverno CLI simulated baseline reports a 67.98% unweighted mean across 17 policy rows, whereas the 78.9% verifier-ablation value is a separate 19-sample gate study. We treat this as directional evidence about the cost and value of adding schema validation and dry-run guarantees, not as a like-for-like aggregate win.

## Positioning By System

### GenKubeSec

GenKubeSec reports strong detection precision/recall on a large labeled corpus and provides LLM-based explanations/remediation suggestions. Our comparison should emphasize that we did not reproduce their pipeline; the difference is that `k8s-auto-fix` verifies patches with policy re-check, schema validation, and server-side dry-run before acceptance.

### Kyverno

Kyverno is a strong admission-time mutation and validation engine when policies and admission fixtures are present. Our role is different: post-hoc repair of existing manifests plus standalone verifier evidence. Cite raw counts and denominators rather than using a single blended "Kyverno baseline" number.

### Borg / SRE Automation

Borg and SRE automation literature informs safety principles such as health checks, staged changes, and rollback readiness. Avoid numeric auto-remediation comparisons unless the cited source reports a directly comparable manifest-remediation acceptance rate.

### KubeDoctor

If mentioned, keep the comparison qualitative unless a reproducible public benchmark is added to this repo. The current paper does not depend on a KubeDoctor head-to-head.

## Language To Use

- "Our verifier treats the generator as untrusted; acceptance is defined by policy re-check, schema validation, server-side dry-run, and universal safety invariants."
- "Kyverno and our pipeline operate at different stages: Kyverno mutates on admission, while this work repairs stored manifests and emits verifier evidence."
- "The no-policy ablation is a guardrail study, not a named-agent benchmark."
- "The Aardvark and KubeIntellect head-to-head remains future work until a public/runnable interface and author-approved protocol are available."

## Language To Avoid

- "Our system beats Kyverno by 10.92 percentage points."
- "Our 78.9% is directly comparable to Kyverno's 67.98%."
- "Kyverno baseline is 81.22%."
- "Live apply is 73.5%" unless explicitly referring to the older 200-manifest historical run and not the current manuscript result.
