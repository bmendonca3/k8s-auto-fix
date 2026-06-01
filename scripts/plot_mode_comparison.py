#!/usr/bin/env python3
"""Plot rules-only vs LLM-only vs hybrid acceptance comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mode comparison plotter")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/baselines/mode_comparison.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("figures/mode_comparison.png"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
    })
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    labels = ["Rules", "LLM", "Hybrid"]
    colors = ["#0072B2", "#D55E00", "#009E73"]
    hatches = ["", "//", ".."]
    bars = ax.bar(labels, df["acceptance_rate"] * 100, color=colors, edgecolor="black", linewidth=0.4)
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)
    ax.set_ylabel("Accepted patches (%)")
    ax.set_ylim(0, 1.05)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="-", linewidth=0.5, color="0.85")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, rate in zip(bars, df["acceptance_rate"]):
        ax.text(bar.get_x() + bar.get_width() / 2, rate * 100 + 1.5, f"{rate:.1%}", ha="center", fontsize=8)

    fig.tight_layout(pad=0.4)
    fig.savefig(args.output, dpi=450, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
