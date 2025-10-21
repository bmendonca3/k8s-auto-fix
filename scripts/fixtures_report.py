#!/usr/bin/env python3
"""Generate a simple report of published RBAC/NetworkPolicy fixtures (task D20)."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fixture report generator")
    parser.add_argument("--fixtures", type=Path, default=Path("infra/fixtures"))
    parser.add_argument("--output", type=Path, default=Path("data/fixtures/report.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = []
    for path in sorted(args.fixtures.glob("**/*.yaml")):
        rows.append((path, sha256(path)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        fh.write("fixture,sha256\n")
        for path, digest in rows:
            fh.write(f"{path},{digest}\n")


if __name__ == "__main__":
    main()
