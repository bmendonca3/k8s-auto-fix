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

    plt.rcParams.update({"font.size": 10})
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(df["mode"], df["acceptance_rate"], color=["#355C7D", "#F67280", "#6C5B7B"])
    ax.set_ylabel("Acceptance rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Acceptance Comparison Across Remediation Modes")
    ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.7)

    for bar, rate in zip(bars, df["acceptance_rate"]):
        ax.text(bar.get_x() + bar.get_width() / 2, rate + 0.02, f"{rate:.2%}", ha="center")

    plt.tight_layout()
    fig.savefig(args.output, dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
