# Scheduler Visualisation Snapshot

## Ranking Quality (Top-50 Window)

| Strategy | Mean Rank | Median Rank | P95 Rank |
| --- | --- | --- | --- |
| Threat-guided (bandit) | 25.50 | 25.50 | 48.00 |
| Risk-only | 25.50 | 25.50 | 48.00 |
| FIFO | 326.58 | 308.50 | 880.00 |

## Telemetry (Hours)

| Strategy | Throughput/hr | Risk Reduction/hr | Top-risk Wait Mean | Top-risk Wait Median | Top-risk Wait P95 |
| --- | --- | --- | --- | --- | --- |
| Threat-guided (bandit) | 6.00 | 242.56 | 10.83 | 10.83 | 20.67 |
| Risk-only | 6.00 | 242.56 | 10.83 | 10.83 | 20.67 |
| FIFO | 6.00 | 242.56 | 102.11 | 105.83 | 174.00 |

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
