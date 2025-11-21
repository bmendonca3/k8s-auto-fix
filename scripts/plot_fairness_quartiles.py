#!/usr/bin/env python3
"""
Plot wait-time fairness by risk tier for bandit vs FIFO schedulers.

Inputs:
  - data/scheduler/metrics_schedule_sweep.json   (bandit summary)
  - data/scheduler/metrics_sweep_live.json       (FIFO/aging sweep with starvation stats)

Output:
  - figures/fairness_waits.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np


TIERS = ["High risk", "Mid risk", "Low risk"]


def _extract_waits(entry: Dict) -> Tuple[np.ndarray, np.ndarray]:
    medians = []
    p95s = []
    for tier in ["High", "Mid", "Low"]:
        tier_stats = entry["band_wait_hours"][tier]
        medians.append(tier_stats["median"])
        p95s.append(tier_stats["p95"])
    medians_arr = np.array(medians, dtype=float)
    err = np.array(p95s, dtype=float) - medians_arr
    return medians_arr, err


def load_bandit(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    data = json.loads(path.read_text())
    for entry in data:
        if entry.get("mode") == "bandit":
            return _extract_waits(entry)
    raise ValueError("No bandit entry found in metrics file")


def load_fifo(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    data = json.loads(path.read_text())
    for entry in data:
        overall = entry.get("overall_wait_hours", {})
        if overall.get("starvation_rate", 0) > 0.5:
            return _extract_waits(entry)
    raise ValueError("No FIFO-like entry (starvation_rate > 0.5) found")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bandit-metrics",
        type=Path,
        default=Path("data/scheduler/metrics_schedule_sweep.json"),
    )
    parser.add_argument(
        "--fifo-metrics",
        type=Path,
        default=Path("data/scheduler/metrics_sweep_live.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("figures/fairness_waits.png"),
    )
    args = parser.parse_args()

    bandit_med, bandit_err = load_bandit(args.bandit_metrics)
    fifo_med, fifo_err = load_fifo(args.fifo_metrics)

    positions = np.arange(len(TIERS))
    width = 0.35

    plt.figure(figsize=(6.5, 3.5))
    plt.bar(
        positions - width / 2,
        bandit_med,
        width,
        yerr=bandit_err,
        capsize=4,
        label="Risk-bandit",
        color="#4F81BD",
    )
    plt.bar(
        positions + width / 2,
        fifo_med,
        width,
        yerr=fifo_err,
        capsize=4,
        label="FIFO",
        color="#C0504D",
        hatch="//",
    )
    plt.ylabel("Wait time (hours)", fontsize=14)
    plt.xticks(positions, TIERS, fontsize=14)
    plt.yticks(fontsize=14)
    plt.title("Wait-time fairness by risk tier", fontsize=16)
    plt.legend(fontsize=12)
    plt.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=300)
    plt.close()


if __name__ == "__main__":
    main()
