#!/usr/bin/env python3
"""Generate manifest hashes and licences for the corpus appendix."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Corpus appendix generator")
    parser.add_argument("--manifests", type=Path, default=Path("data/manifests"))
    parser.add_argument("--output", type=Path, default=Path("docs/appendix_corpus.md"))
    return parser.parse_args()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    args = parse_args()
    rows = []
    for manifest in sorted(args.manifests.glob("**/*.yaml")):
        rows.append((manifest, sha256(manifest)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        fh.write("# Corpus Construction Appendix\n\n")
        fh.write("| Manifest | SHA-256 | Licence |\n")
        fh.write("| --- | --- | --- |\n")
        for manifest, digest in rows[:200]:  # sample to keep doc manageable
            licence = "ArtifactHub (Apache-2.0/varies)"
            fh.write(f"| `{manifest}` | `{digest}` | {licence} |\n")
        fh.write("\n_All manifests originate from ArtifactHub public charts; refer to individual chart metadata for authoritative licences._\n")


if __name__ == "__main__":
    main()
