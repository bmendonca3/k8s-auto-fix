#!/usr/bin/env python3
"""
Compute fairness metrics (Gini coefficient and starvation rate) per scheduler.

The script operates on operator A/B replay logs that record per-assignment wait
times (e.g., data/operator_ab/assignments_staging.json) and emits a compact
JSON summary referenced by the paper's fairness discussion.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np


def gini(values: np.ndarray) -> float:
    """Return the Gini coefficient for a non-negative array."""
    if values.size == 0:
        return 0.0
    sorted_vals = np.sort(values)
    index = np.arange(1, sorted_vals.size + 1)
    return float(
        (2 * np.sum(index * sorted_vals)) / (sorted_vals.size * np.sum(sorted_vals))
        - (sorted_vals.size + 1) / sorted_vals.size
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assignments",
        type=Path,
        default=Path("data/operator_ab/assignments_staging.json"),
        help="Queue replay with per-item wait_hours.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/scheduler/fairness_metrics.json"),
    )
    parser.add_argument(
        "--starvation-threshold",
        type=float,
        default=24.0,
        help="Hours beyond which an item is counted as starved.",
    )
    args = parser.parse_args()

    payload: List[Dict] = json.loads(args.assignments.read_text())
    waits_by_scheduler: Dict[str, List[float]] = defaultdict(list)
    waits_high_risk: Dict[str, List[float]] = defaultdict(list)

    for entry in payload:
        scheduler = entry["scheduler"]
        wait = float(entry["wait_hours"])
        risk = float(entry.get("risk", 0.0))
        waits_by_scheduler[scheduler].append(wait)
        if risk >= 60.0:
            waits_high_risk[scheduler].append(wait)

    def summarize(values: List[float]) -> Dict[str, float]:
        arr = np.array(values, dtype=float)
        if arr.size == 0:
            return {
                "items": 0,
                "gini": 0.0,
                "starvation_rate": 0.0,
                "median_wait_hours": 0.0,
                "p95_wait_hours": 0.0,
            }
        starvation_rate = float(np.mean(arr > args.starvation_threshold))
        return {
            "items": len(values),
            "gini": gini(arr),
            "starvation_rate": starvation_rate,
            "median_wait_hours": float(np.median(arr)),
            "p95_wait_hours": float(np.quantile(arr, 0.95)),
        }

    report = {}
    for scheduler, waits in waits_by_scheduler.items():
        report[scheduler] = {
            "overall": summarize(waits),
            "high_risk": summarize(waits_high_risk.get(scheduler, [])),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
