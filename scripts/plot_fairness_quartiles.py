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

    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
    })
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    ax.bar(
        positions - width / 2,
        bandit_med,
        width,
        yerr=bandit_err,
        capsize=4,
        label="Risk-bandit",
        color="#0072B2",
    )
    ax.bar(
        positions + width / 2,
        fifo_med,
        width,
        yerr=fifo_err,
        capsize=4,
        label="FIFO",
        color="#D55E00",
        hatch="//",
    )
    ax.set_ylabel("Wait time (hours)")
    ax.set_xticks(positions, TIERS)
    ax.legend(frameon=False, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="0.85", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=0.4)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=450, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
