#!/usr/bin/env python3
"""Augment evaluation counts with Wilson score intervals."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add confidence intervals to evaluation counts.")
    parser.add_argument(
        "--counts",
        type=Path,
        default=Path("data/eval/table4_counts.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/eval/table4_with_ci.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.counts)
    z = 1.96  # ~95%
    p_hat = df["accepted"] / df["total"]
    denominator = 1 + (z**2 / df["total"])
    centre = p_hat + (z**2) / (2 * df["total"])
    margin = z * np.sqrt((p_hat * (1 - p_hat) + (z**2) / (4 * df["total"])) / df["total"])
    df["acceptance_rate"] = p_hat
    df["ci_lower"] = (centre - margin) / denominator
    df["ci_upper"] = (centre + margin) / denominator
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
