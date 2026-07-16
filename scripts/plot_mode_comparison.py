#!/usr/bin/env python3
"""Plot a matched-corpus proposer/guardrail acceptance comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


REQUIRED_COLUMNS = {
    "corpus",
    "mode",
    "manifests",
    "accepted",
    "acceptance_rate",
    "source_metrics",
}


DISPLAY_LABELS = {
    "rules+guardrails": "Rules +\nguards",
    "grok+rule-guardrails": "Grok +\nguards",
}


def load_comparison(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError(f"{path} contains no comparison rows")
    if df["corpus"].nunique() != 1 or df["manifests"].nunique() != 1:
        raise ValueError("mode comparison rows must use one shared corpus and denominator")
    if df["mode"].duplicated().any():
        raise ValueError("mode comparison rows must have unique mode labels")
    if (df["manifests"] <= 0).any() or (df["accepted"] < 0).any():
        raise ValueError("mode comparison counts must be non-negative with a positive denominator")
    if (df["accepted"] > df["manifests"]).any():
        raise ValueError("mode comparison accepted counts cannot exceed manifests")
    expected = df["accepted"] / df["manifests"]
    if ((df["acceptance_rate"] - expected).abs() > 1e-12).any():
        raise ValueError("mode comparison acceptance_rate must equal accepted/manifests")
    return df


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
    df = load_comparison(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
    })
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    labels = [DISPLAY_LABELS.get(str(mode), str(mode).replace("-", " ").title()) for mode in df["mode"]]
    colors = ["#0072B2", "#D55E00", "#009E73"][: len(df)]
    hatches = ["", "//", ".."][: len(df)]
    bars = ax.bar(labels, df["acceptance_rate"] * 100, color=colors, edgecolor="black", linewidth=0.4)
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)
    ax.set_ylabel("Accepted patches (%)")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="-", linewidth=0.5, color="0.85")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, rate, accepted, total in zip(
        bars,
        df["acceptance_rate"],
        df["accepted"],
        df["manifests"],
    ):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            rate * 100 + 1.5,
            f"{rate:.1%}\n{int(accepted):,}/{int(total):,}",
            ha="center",
            fontsize=7,
        )

    fig.tight_layout(pad=0.4)
    fig.savefig(args.output, dpi=450, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
