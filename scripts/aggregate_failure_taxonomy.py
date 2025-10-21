#!/usr/bin/env python3
"""
Aggregate verifier failure reasons across one or more datasets.

This script complements evaluation task A9 by producing the CSV inputs that
`scripts/plot_failure_taxonomy.py` expects. Usage example:

    python scripts/aggregate_failure_taxonomy.py \
        --dataset rules_full:data/verified_rules_full.json.gz \
        --dataset supported:data/verified_rules_supported.json \
        --output data/failures/taxonomy_counts.csv \
        --summary data/failures/taxonomy_summary.csv \
        --policy-output data/failures/policy_failures.csv

Each `--dataset` entry is `label:path`. Paths may point to JSON or JSON.gz
files produced by the verifier stage.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Tuple
import csv
import re


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate verifier failure taxonomy data.")
    parser.add_argument(
        "--dataset",
        action="append",
        metavar="LABEL:PATH",
        required=True,
        help="Dataset specification in the form label:path/to/verified.json[.gz]. "
        "Repeat for multiple datasets.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/failures/taxonomy_counts.csv"),
        help="CSV file for failure categories.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/failures/taxonomy_summary.csv"),
        help="CSV file for dataset-level summary (records/accepted/rejected).",
    )
    parser.add_argument(
        "--policy-output",
        type=Path,
        default=Path("data/failures/policy_failures.csv"),
        help="CSV file for failure counts grouped by policy.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Minimum count required for a failure category to appear in the CSV.",
    )
    return parser.parse_args()


def _load_verified(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Verified results not found at {path}")
    if path.suffix == ".gz":
        with gzip.open(path, mode="rt", encoding="utf-8") as fh:
            return json.load(fh)
    with path.open() as fh:
        return json.load(fh)


def _iter_datasets(specs: Iterable[str]) -> Iterator[Tuple[str, Path]]:
    for spec in specs:
        if ":" not in spec:
            raise ValueError(f"Dataset specification must be label:path, got {spec!r}")
        label, raw_path = spec.split(":", 1)
        label = label.strip()
        path = Path(raw_path.strip())
        if not label:
            raise ValueError(f"Dataset label cannot be empty (spec: {spec!r})")
        yield label, path


_WHITESPACE_RE = re.compile(r"\s+")


def _normalise_error(message: str) -> str:
    msg = message.strip()
    msg = _WHITESPACE_RE.sub(" ", msg)
    if "{" in msg and " not found" in msg:
        msg = msg.split("{", 1)[0].strip()
    if ":" in msg and msg.lower().startswith("error"):
        # Keep leading clause before verbose server echo.
        prefix, _, remainder = msg.partition(":")
        if remainder and len(remainder) > 120:
            msg = f"{prefix.strip()}: {remainder.strip().split(':', 1)[0]}"
    if len(msg) > 180:
        msg = msg[:177] + "..."
    return msg


def aggregate_failures(records: List[Dict]) -> Tuple[int, int, Counter, Counter]:
    total = len(records)
    accepted = 0
    failure_counter: Counter = Counter()
    policy_counter: Counter = Counter()
    for record in records:
        if record.get("accepted"):
            accepted += 1
            continue
        errors = record.get("errors") or []
        if not errors:
            failure_counter["<unspecified>"] += 1
        else:
            for error in errors:
                failure_counter[_normalise_error(str(error))] += 1
        policy_counter[str(record.get("policy_id", "unknown"))] += 1
    return total, accepted, failure_counter, policy_counter


def write_csv(path: Path, rows: Sequence[Sequence], headers: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()

    summary_rows: List[Tuple[str, int, int, int]] = []
    category_rows: List[Tuple[str, str, int]] = []
    policy_rows: List[Tuple[str, str, int]] = []

    for label, path in _iter_datasets(args.dataset):
        records = _load_verified(path)
        total, accepted, failure_counts, policy_counts = aggregate_failures(records)
        rejected = total - accepted
        summary_rows.append((label, total, accepted, rejected))

        for failure, count in failure_counts.most_common():
            if count < args.min_count:
                continue
            category_rows.append((label, failure.replace("\n", " "), count))
        for policy, count in policy_counts.most_common():
            if count < args.min_count:
                continue
            policy_rows.append((label, policy, count))

    if not category_rows:
        print("No failures discovered across datasets; nothing to write.", file=sys.stderr)
    else:
        write_csv(args.output, category_rows, ("dataset", "failure_category", "count"))

    if summary_rows:
        write_csv(args.summary, summary_rows, ("dataset", "total", "accepted", "rejected"))
    if policy_rows:
        write_csv(args.policy_output, policy_rows, ("dataset", "policy_id", "count"))


if __name__ == "__main__":
    main()
