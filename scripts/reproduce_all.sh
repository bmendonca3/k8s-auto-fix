#!/usr/bin/env bash
set -euo pipefail

# Rebuild key artifacts, baselines (simulated by default), and tables/figures.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[repro] Building reproducibility bundle"
python "$ROOT_DIR/scripts/build_repro_bundle.py"

echo "[repro] Kyverno mutate baseline (simulate)"
python "$ROOT_DIR/scripts/run_kyverno_baseline.py" --detections "$ROOT_DIR/data/detections.json" --output "$ROOT_DIR/data/baselines/kyverno_baseline.csv" --simulate

echo "[repro] Polaris baseline (simulate)"
python "$ROOT_DIR/scripts/run_polaris_baseline.py" --detections "$ROOT_DIR/data/detections.json" --output "$ROOT_DIR/data/baselines/polaris_baseline.csv" --simulate

echo "[repro] MAP baseline (simulate)"
python "$ROOT_DIR/scripts/run_mutatingadmission_baseline.py" --detections "$ROOT_DIR/data/detections.json" --output "$ROOT_DIR/data/baselines/map_baseline.csv" --simulate

echo "[repro] Risk throughput eval"
python "$ROOT_DIR/scripts/eval_risk_throughput.py" --verified "$ROOT_DIR/data/verified.json" --detections "$ROOT_DIR/data/detections.json" --risk "$ROOT_DIR/data/risk.json" --out "$ROOT_DIR/data/metrics_risk_throughput.json" || true

echo "[repro] LLMSecConfig slice (requires API key; skipping if unset)"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  python "$ROOT_DIR/scripts/run_llmsecconfig_slice.py" --detections "$ROOT_DIR/data/detections.json" --out "$ROOT_DIR/data/baselines/llmsecconfig_slice.csv" --limit 500
else
  echo "OPENAI_API_KEY not set; skipping LLMSecConfig slice"
fi

echo "[repro] Build unified baseline comparison tables"
python "$ROOT_DIR/scripts/compare_baselines.py" \
  --detections "$ROOT_DIR/data/detections.json" \
  --verified "$ROOT_DIR/data/verified.json" \
  --out-csv "$ROOT_DIR/data/baselines/baseline_summary.csv" \
  --out-md "$ROOT_DIR/docs/reproducibility/baselines.md" \
  --out-tex "$ROOT_DIR/docs/reproducibility/baselines.tex" || true

echo "[repro] Done. See data/baselines/ and docs/reproducibility/"
