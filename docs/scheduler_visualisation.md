# Scheduler Visualisation Snapshot

## Ranking Quality (Top-50 Window)

| Strategy | Mean Rank | Median Rank | P95 Rank |
| --- | --- | --- | --- |
| Threat-guided (bandit) | 25.50 | 25.50 | 48.00 |
| Risk-only | 25.50 | 25.50 | 48.00 |
| Risk/Et+aging | 42.22 | 25.50 | 124.00 |
| FIFO | 365.18 | 422.50 | 620.00 |

## Telemetry (Hours)

| Strategy | Throughput/hr | Risk Reduction/hr | Top-risk Wait Mean | Top-risk Wait Median | Top-risk Wait P95 |
| --- | --- | --- | --- | --- | --- |
| Threat-guided (bandit) | 6.00 | 247.16 | 6.83 | 6.83 | 13.00 |
| Risk-only | 6.00 | 247.16 | 6.83 | 6.83 | 13.00 |
| Risk/Et+aging | 6.00 | 247.16 | 6.83 | 6.83 | 13.00 |
| FIFO | 6.00 | 247.16 | 64.66 | 70.50 | 102.33 |

## Representative Rank Deltas (Top-risk Detections)

| Detection ID | Policy | Risk | Bandit Rank | FIFO Rank | Rank Delta |
| --- | --- | --- | --- | --- | --- |
| 007 | no_privileged | 85.00 | 18 | 7 | -11 |
| 008 | no_privileged | 85.00 | 19 | 8 | -11 |
| 016 | no_privileged | 85.00 | 1 | 16 | 15 |
| 301 | no_privileged | 85.00 | 2 | 301 | 299 |
| 302 | no_privileged | 85.00 | 3 | 302 | 299 |
| 303 | no_privileged | 85.00 | 4 | 303 | 299 |
| 304 | no_privileged | 85.00 | 5 | 304 | 299 |
| 305 | no_privileged | 85.00 | 6 | 305 | 299 |
| 306 | no_privileged | 85.00 | 7 | 306 | 299 |
| 335 | no_privileged | 85.00 | 8 | 335 | 327 |

## Risk-band wait percentiles (α sweep)

A sweep across $\alpha \in \{0.0, 0.5, 1.0, 2.0\}$ and exploration weights $\in \{0.0, 0.5, 1.0\}$ yields consistent fairness profiles:

- High-risk quartile: median wait 17.25 h (P95 32.78 h)
- Mid-risk band: median wait 69.08 h (P95 100.06 h)
- Low-risk band: median wait 120.92 h (P95 136.44 h)

The raw measurements live in `data/metrics_schedule_sweep.json`.
