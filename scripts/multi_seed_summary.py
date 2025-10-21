#!/usr/bin/env python3
"""
Aggregate multi-seed runs to mean ± sd (task C13).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-seed metrics aggregation.")
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path("data/eval/multi_seed_metrics.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/eval/multi_seed_summary.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.metrics.read_text())
    rows = []
    for corpus, seeds in data.items():
        raw_values = []
        for value in seeds.values():
            if isinstance(value, dict) and "acceptance" in value:
                raw_values.append(float(value["acceptance"]))
            else:
                raw_values.append(float(value))
        values = raw_values
        series = pd.Series(values)
        rows.append(
            {
                "corpus": corpus,
                "mean_acceptance": series.mean(),
                "std_acceptance": series.std(ddof=1) if len(series) > 1 else 0.0,
                "samples": len(series),
            }
        )
    df = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
