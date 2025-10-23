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
    """Create dual-axis bar chart for A/B study results."""
    fig, ax1 = plt.subplots(figsize=(8, 5))
    
    # Prepare data
    schedulers = df["scheduler"].tolist()
    acceptance = (df["acceptance_rate"] * 100).tolist()
    wait_hours = df["mean_wait_hours"].tolist()
    
    # X positions
    x = range(len(schedulers))
    width = 0.35
    
    # Bar 1: Acceptance rate (primary y-axis)
    bars1 = ax1.bar(
        [i - width/2 for i in x],
        acceptance,
        width,
        label="Acceptance Rate",
        color="#2E7D32",
        alpha=0.8,
    )
    ax1.set_ylabel("Acceptance Rate (%)", fontsize=11)
    ax1.set_ylim([0, 100])
    ax1.tick_params(axis='y')
    
    # Secondary y-axis: Mean wait time
    ax2 = ax1.twinx()
    bars2 = ax2.bar(
        [i + width/2 for i in x],
        wait_hours,
        width,
        label="Mean Wait Time",
        color="#1976D2",
        alpha=0.8,
    )
    ax2.set_ylabel("Mean Wait Time (hours)", fontsize=11)
    ax2.tick_params(axis='y')
    
    # Labels
    ax1.set_xlabel("Scheduler Mode", fontsize=11)
    ax1.set_title(
        "Operator A/B Study: Scheduler Comparison\n"
        "Acceptance Rate and Mean Wait Time",
        fontsize=12,
        fontweight="bold",
    )
    ax1.set_xticks(x)
    
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
    
    ax1.set_xticklabels(labels, fontsize=10)
    
    # Add value labels on bars
    for bars, values in [(bars1, acceptance), (bars2, wait_hours)]:
        for bar, value in zip(bars, values):
            height = bar.get_height()
            axis = ax1 if bars == bars1 else ax2
            if bars == bars1:
                label = f"{value:.1f}%"
            else:
                label = f"{value:.2f}h"
            axis.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                label,
                ha='center',
                va='bottom',
                fontsize=9,
            )
    
    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)
    
    # Grid
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
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






