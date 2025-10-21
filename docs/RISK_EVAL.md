# Risk Evaluation

We evaluate the scheduler on risk-weighted throughput rather than acceptance alone.

Metrics
- KEV-closed per hour: number of KEV-flagged issues eliminated per wall-clock hour
- Risk-closed per hour: sum of weighted policy risk closed per hour

Inputs
- Base policy weights (transparent mapping per policy id), plus optional KEV boost; EPSS may be incorporated as a percentile multiplier
- Verified results with per-item latencies (or estimated durations) to model time

Methodology
- Compare FIFO vs. risk-aware ordering on the same verified workload
- Sensitivity analysis: run at least two alternate weight maps (severity-tilted, flat) and report improvement factors that persist across maps

How to run
```
python scripts/eval_risk_throughput.py \
  --verified data/verified.json \
  --detections data/detections.json \
  --risk data/risk.json \
  --out data/metrics_risk_throughput.json
```

Interpretation
- Improvements >1.0 on both KEV/hour and risk/hour indicate better prioritization than FIFO
- Report mean with confidence intervals when multiple runs/weight maps are available

Notes
- KEV and EPSS are inputs to prioritization; they are not themselves evidence of risk reduction. We measure impact empirically via throughput metrics.

