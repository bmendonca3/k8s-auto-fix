#!/usr/bin/env python3
"""
Compute patch size statistics (median ops, max ops, distribution).

Outputs JSON and CSV artefacts under data/eval/ for task A8.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch statistics utility.")
    parser.add_argument(
        "--patches",
        type=Path,
        default=Path("data/patches.json"),
        help="JSON file containing proposer output.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path("data/eval/patch_stats.json"),
        help="Summary JSON output.",
    )
    parser.add_argument(
        "--histogram-csv",
        type=Path,
        default=Path("data/eval/patch_histogram.csv"),
        help="Histogram CSV output.",
    )
    return parser.parse_args()


def load_patches(path: Path) -> List[Dict]:
    return json.loads(path.read_text())


def main() -> None:
    args = parse_args()
    patches = load_patches(args.patches)

    lengths = [len(entry.get("patch", [])) for entry in patches if isinstance(entry, dict)]
    if not lengths:
        raise ValueError("No patch data available.")
    arr = np.array(lengths)

    summary = {
        "count": int(len(arr)),
        "median": float(np.median(arr)),
        "p95": float(np.percentile(arr, 95)),
        "max": int(arr.max()),
    }

    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    hist = pd.Series(arr).value_counts().sort_index().reset_index()
    hist.columns = ["operations", "count"]
    args.histogram_csv.parent.mkdir(parents=True, exist_ok=True)
    hist.to_csv(args.histogram_csv, index=False)


if __name__ == "__main__":
    main()
