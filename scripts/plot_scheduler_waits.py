#!/usr/bin/env python3
"""Plot top-risk wait statistics from the deterministic scheduler comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_waits(path: Path) -> tuple[int, dict[str, dict[str, float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    configuration = payload.get("configuration")
    telemetry = payload.get("telemetry")
    if not isinstance(configuration, dict) or not isinstance(telemetry, dict):
        raise ValueError("scheduler comparison must contain configuration and telemetry objects")
    if configuration.get("replay_kind") != "deterministic static queue snapshot":
        raise ValueError("scheduler comparison is not the expected deterministic static queue snapshot")
    if int(configuration.get("nonzero_wait_inputs", -1)) != 0:
        raise ValueError("this figure requires a zero-initial-age snapshot")
    cohort_size = int(configuration.get("top_risk_cohort_size", 0))
    if cohort_size <= 0:
        raise ValueError("scheduler comparison must define a positive top-risk cohort")

    result: dict[str, dict[str, float]] = {}
    for key in ("risk_priority", "fifo"):
        entry = telemetry.get(key)
        waits = entry.get("top_risk_wait_hours") if isinstance(entry, dict) else None
        if not isinstance(waits, dict):
            raise ValueError(f"scheduler comparison is missing {key} top-risk waits")
        result[key] = {
            "median": float(waits["median"]),
            "p95": float(waits["p95"]),
        }
    return cohort_size, result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot top-risk scheduler wait comparison.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/metrics_schedule_compare.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("figures/fairness_waits.png"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cohort_size, waits = load_waits(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    labels = ["Risk priority", "FIFO"]
    keys = ["risk_priority", "fifo"]
    x = np.arange(len(labels))
    width = 0.34
    medians = [waits[key]["median"] for key in keys]
    p95s = [waits[key]["p95"] for key in keys]

    plt.rcParams.update({"font.size": 9, "axes.labelsize": 9, "xtick.labelsize": 9, "ytick.labelsize": 9})
    fig, ax = plt.subplots(figsize=(3.4, 2.45))
    median_bars = ax.bar(x - width / 2, medians, width, label="Median", color="#0072B2", edgecolor="black", linewidth=0.4)
    p95_bars = ax.bar(x + width / 2, p95s, width, label="P95", color="#D55E00", hatch="//", edgecolor="black", linewidth=0.4)
    ax.set_ylabel("Wait (hours)")
    ax.set_xticks(x, labels)
    ax.set_title(f"Top-{cohort_size} high-risk queue items")
    ax.grid(axis="y", color="0.85", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=True, fontsize=8)
    ax.bar_label(median_bars, fmt="%.1f", padding=2, fontsize=7)
    ax.bar_label(p95_bars, fmt="%.1f", padding=2, fontsize=7)
    fig.tight_layout(pad=0.5)
    fig.savefig(args.output, dpi=450, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
