#!/usr/bin/env python3
"""
Compute a stable SHA-256 ledger of all corpus manifests under data/manifests.

Outputs:
- data/corpus_hashes.csv (path, sha256)
- data/corpus_manifest.txt (newline-separated paths)
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hash corpus manifests")
    p.add_argument("--root", type=Path, default=Path("data/manifests"))
    p.add_argument("--out-csv", type=Path, default=Path("data/corpus_hashes.csv"))
    p.add_argument("--out-list", type=Path, default=Path("data/corpus_manifest.txt"))
    return p.parse_args()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    args = parse_args()
    files = sorted([p for p in args.root.rglob("*") if p.is_file()])
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8") as f:
        f.write("path,sha256\n")
        for p in files:
            digest = sha256_file(p)
            rel = p.relative_to(Path.cwd()) if args.root.is_absolute() else p
            f.write(f"{rel.as_posix()},{digest}\n")
    args.out_list.write_text("\n".join(p.as_posix() for p in files) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

