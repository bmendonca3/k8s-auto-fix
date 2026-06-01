#!/usr/bin/env python3
"""
Generate operator A/B study visualization comparing scheduler modes.

Creates a dual-axis bar chart showing acceptance rate and mean wait time
for bandit vs. baseline schedulers.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot operator A/B study results.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/operator_ab/summary_simulated.csv"),
        help="Input CSV with scheduler comparison data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("figures/operator_ab.png"),
        help="Output figure path.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Figure DPI.",
    )
    return parser.parse_args()


def create_figure(df: pd.DataFrame, output_path: Path, dpi: int) -> None:
    """Create a two-panel chart for scheduler acceptance and wait time."""
    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
    })
    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(3.4, 3.5),
        sharex=True,
        constrained_layout=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.08},
    )
    
    # Prepare data
    schedulers = df["scheduler"].tolist()
    acceptance = (df["acceptance_rate"] * 100).tolist()
    wait_hours = df["mean_wait_hours"].tolist()
    
    # X positions
    x = range(len(schedulers))
    width = 0.58

    bars1 = ax1.bar(
        x,
        acceptance,
        width,
        color="#009E73",
        edgecolor="black",
        linewidth=0.4,
    )
    ax1.set_ylabel("Accepted (%)")
    ax1.set_ylim([0, 100])
    
    bars2 = ax2.bar(
        x,
        wait_hours,
        width,
        color="#0072B2",
        edgecolor="black",
        linewidth=0.4,
        hatch="//",
    )
    ax2.set_ylabel("Mean wait (h)")
    ax2.set_ylim([0, max(wait_hours) * 1.35])
    
    ax2.set_xticks(list(x))
    
    # Clean up scheduler labels
    labels = []
    for s in schedulers:
        if s == "bandit":
            labels.append("Bandit\n(R·p/E[t])")
        elif s == "risk_only":
            labels.append("Risk-Only")
        elif s == "risk_over_et_aging":
            labels.append("Risk/E[t]\n+Aging")
        else:
            labels.append(s)
    
    ax2.set_xticklabels(labels)
    
    for bars, values, axis, suffix in [
        (bars1, acceptance, ax1, "%"),
        (bars2, wait_hours, ax2, "h"),
    ]:
        for bar, value in zip(bars, values):
            height = bar.get_height()
            label = f"{value:.1f}%" if suffix == "%" else f"{value:.2f}h"
            axis.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                label,
                ha='center',
                va='bottom',
                fontsize=9,
            )
    
    for ax in (ax1, ax2):
        ax.grid(axis="y", color="0.85", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
    print(f"Saved figure to {output_path}")


def main() -> None:
    args = parse_args()
    
    if not args.input.exists():
        print(f"Error: Input file {args.input} not found")
        return
    
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} scheduler modes from {args.input}")
    print(df.to_string(index=False))
    
    create_figure(df, args.output, args.dpi)


if __name__ == "__main__":
    main()






