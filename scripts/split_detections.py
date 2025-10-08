#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List


def split(input_path: Path, out_dir: Path, prefix: str, batch_size: int) -> int:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for idx in range(0, len(data), batch_size):
        chunk = data[idx : idx + batch_size]
        out_file = out_dir / f"{prefix}_{idx // batch_size:03d}.json"
        out_file.write_text(json.dumps(chunk, indent=2), encoding="utf-8")
        count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split detections JSON into fixed-size batches.")
    parser.add_argument("input", type=Path, help="Path to detections JSON file")
    parser.add_argument("out_dir", type=Path, help="Directory to write batches")
    parser.add_argument("prefix", type=str, help="Filename prefix for batches")
    parser.add_argument("batch_size", type=int, help="Number of items per batch")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total = split(args.input, args.out_dir, args.prefix, args.batch_size)
    print(f"Wrote {total} batches to {args.out_dir}")


if __name__ == "__main__":
    main()
