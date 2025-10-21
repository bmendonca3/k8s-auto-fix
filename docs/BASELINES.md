# Baseline Experiments

This document describes how to reproduce head-to-head baselines alongside k8s-auto-fix.

Baselines covered
- Kyverno mutate (CLI): `scripts/run_kyverno_baseline.py`
- Fairwinds Polaris (CLI fix/mutating): `scripts/run_polaris_baseline.py`
- MutatingAdmissionPolicy (MAP): `scripts/run_mutatingadmission_baseline.py`
- LLMSecConfig-style slice: `scripts/run_llmsecconfig_slice.py`

Quick start (simulation mode)
```
make baselines
```

Real runs
- Kyverno:
  - Prereq: `kyverno` CLI, `policies/kyverno-mutating.yaml` applied as needed
  - Run: `python scripts/run_kyverno_baseline.py --detections data/detections.json --output data/baselines/kyverno_baseline.csv`
- Polaris:
  - Prereq: `polaris` CLI
  - Run (CLI fix mode): `python scripts/run_polaris_baseline.py --detections data/detections.json --output data/baselines/polaris_baseline.csv`
  - Run (mutating webhook mode): `python scripts/run_polaris_baseline.py --detections tmp/detections_polaris_500.json --output data/baselines/polaris_baseline_webhook.csv --webhook --kubectl kubectl --keep-temp`
- Kyverno mutate (webhook):
  - Prereq: Kyverno Helm chart installed and `policies/kyverno-mutating.yaml` applied
  - Run: `python scripts/run_kyverno_webhook_baseline.py --detections tmp/detections_polaris_500.json --output data/baselines/kyverno_baseline_webhook.csv --kubectl kubectl --keep-temp`
- MAP:
  - Status: the v1beta1 MutatingAdmissionPolicy API cannot yet express the per-container security context and resources required for triad verification. We therefore ship only the simulated acceptance (`python scripts/run_mutatingadmission_baseline.py --simulate`).
  - If Kubernetes expands the CEL surface (loop helpers or richer apply support), regenerate `data/baselines/map_policies.yaml`, apply it on a MAP-enabled cluster, and re-run detection/verification to capture real acceptance.
- LLMSecConfig slice:
  - Prereq: `OPENAI_API_KEY`
  - Run: `python scripts/run_llmsecconfig_slice.py --detections data/detections.json --out data/baselines/llmsecconfig_slice.csv --limit 500`

Unified comparison table
```
python scripts/compare_baselines.py \
  --detections data/detections.json \
  --verified data/verified.json \
  --out-csv data/baselines/baseline_summary.csv \
  --out-md docs/reproducibility/baselines.md \
  --out-tex docs/reproducibility/baselines.tex
```

Notes
- “No-new-violations” rates require triad verification of mutated outputs. The Polaris runner includes triad re-check in real mode; Kyverno/MAP runners provide acceptance from their own outputs unless you wrap them through the triad.
- Simulation outputs provide deterministic placeholders for artifact regeneration without external dependencies.
- Polaris webhook mode requires cert-manager (or another issuer) to populate the webhook `caBundle`, and we recommend setting `webhook.failurePolicy=Ignore` in `configs/polaris_webhook_values.yaml` so TLS hiccups do not block the apiserver.
- Kyverno webhook runs often surface missing volume/service-account fixtures; the 500-manifest slice currently reports zero acceptances because those manifests fail admission before mutation. Seed the required namespaces and volumes if you need higher coverage.
