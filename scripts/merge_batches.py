#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def merge(glob_pattern: str) -> list:
    paths = sorted(Path().glob(glob_pattern))
    merged = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            merged.extend(json.load(handle))
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge JSON array batches into a single file.")
    parser.add_argument("pattern", type=str, help="Glob pattern for batch files")
    parser.add_argument("out", type=Path, help="Output file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    merged = merge(args.pattern)
    args.out.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"Merged {len(merged)} records into {args.out}")


if __name__ == "__main__":
    main()
