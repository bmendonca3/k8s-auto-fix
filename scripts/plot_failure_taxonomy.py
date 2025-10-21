"""
Generate failure taxonomy visualisations for verifier rejections.

Supports evaluation task A9 by aggregating failure logs before and after
fixture updates, then producing a bar chart of the dominant failure classes.

Example usage (placeholder):
    python scripts/plot_failure_taxonomy.py \
        --input data/failures/taxonomy_counts.csv \
        --output figures/failure_taxonomy.png

Actual plotting logic will be filled in once refreshed failure datasets are
available.
"""

from __future__ import annotations

import argparse
import pathlib
from typing import Sequence

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot verifier failure taxonomy.")
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        default=pathlib.Path("data/failures/taxonomy_counts.csv"),
        help="CSV file containing failure categories and counts.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("figures/failure_taxonomy.png"),
        help="Path to save the generated plot.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Verifier Failure Taxonomy",
        help="Plot title.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=12,
        help="Show the top-N failure categories across all datasets (default: 12). "
        "Set to 0 to include every category.",
    )
    parser.add_argument(
        "--stacked",
        action="store_true",
        help="Render stacked bars instead of side-by-side bars.",
    )
    parser.add_argument(
        "--figsize",
        type=float,
        nargs=2,
        default=(10.0, 6.0),
        metavar=("WIDTH", "HEIGHT"),
        help="Matplotlib figure size in inches (width height).",
    )
    parser.add_argument(
        "--wrap-at",
        type=int,
        default=60,
        help="Wrap failure category labels at the specified character width.",
    )
    return parser.parse_args()


def _wrap_labels(labels: Sequence[str], width: int) -> list[str]:
    if width <= 0:
        return list(labels)
    wrapped = []
    for label in labels:
        words = label.split()
        if not words:
            wrapped.append(label)
            continue
        current: list[str] = []
        lines: list[str] = []
        current_len = 0
        for word in words:
            extended = len(word) if not current else current_len + 1 + len(word)
            if extended > width and current:
                lines.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len = extended
        if current:
            lines.append(" ".join(current))
        wrapped.append("\n".join(lines))
    return wrapped


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Expected taxonomy counts at {args.input}. Populate the CSV before plotting."
        )

    df = pd.read_csv(args.input)
    if df.empty:
        raise ValueError(f"{args.input} contains no failure data.")

    if {"dataset", "failure_category", "count"} - set(df.columns):
        missing = {"dataset", "failure_category", "count"} - set(df.columns)
        raise ValueError(f"Missing required columns in {args.input}: {missing}")

    agg = df.groupby("failure_category", as_index=False)["count"].sum()
    if args.top_n > 0:
        top_categories = (
            agg.sort_values("count", ascending=False).head(args.top_n)["failure_category"].tolist()
        )
        df = df[df["failure_category"].isin(top_categories)]
    else:
        top_categories = agg.sort_values("count", ascending=False)["failure_category"].tolist()

    if df.empty:
        raise ValueError("After filtering, no failure categories remain to plot.")

    pivot = (
        df.pivot_table(
            index="failure_category",
            columns="dataset",
            values="count",
            aggfunc="sum",
            fill_value=0,
        )
        .loc[top_categories]
        .fillna(0)
    )

    pivot = pivot.sort_values(by=list(pivot.columns), ascending=True)
    pivot.index = _wrap_labels(pivot.index.tolist(), args.wrap_at)

    plt.rcParams.update({"font.size": 10})
    fig, ax = plt.subplots(figsize=tuple(args.figsize))
    if args.stacked:
        pivot.plot(kind="barh", stacked=True, ax=ax)
    else:
        pivot.plot(kind="barh", stacked=False, ax=ax)
    ax.set_xlabel("Failure count")
    ax.set_ylabel("Failure category")
    ax.set_title(args.title)
    ax.legend(title="Dataset", bbox_to_anchor=(1.04, 1), loc="upper left")
    ax.grid(axis="x", linestyle="--", linewidth=0.5, alpha=0.6)
    plt.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
