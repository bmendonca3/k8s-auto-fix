#!/usr/bin/env python3
"""Inventory tracked artifact-like files with size, category, and SHA-256."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, TextIO, Tuple


ARCHIVE_SUFFIXES = (
    ".tar",
    ".tar.gz",
    ".tgz",
    ".zip",
    ".gz",
    ".bz2",
    ".xz",
)
DATA_INPUT_PREFIXES = (
    "data/corpora/",
    "data/fixtures/",
    "data/manifests/",
    "data/manifests_live_subset/",
    "data/policies/",
    "data/schemas/",
)
DATA_OUTPUT_PREFIXES = (
    "data/ablation/",
    "data/baselines/",
    "data/batch_runs/",
    "data/cross_cluster/",
    "data/cross_version/",
    "data/eval/",
    "data/failures/",
    "data/generated/",
    "data/live_cluster/",
    "data/operator_ab/",
    "data/outputs/",
    "data/repro/",
    "data/risk/",
    "data/scheduler/",
    "data/staged/",
)
IMAGE_SUFFIXES = (".gif", ".jpeg", ".jpg", ".png", ".svg")
LOG_SUFFIXES = (".log", ".out")
PAPER_OUTPUT_SUFFIXES = (
    ".aux",
    ".bbl",
    ".blg",
    ".log",
    ".out",
    ".pdf",
    ".synctex.gz",
    ".toc",
)
RUNTIME_SUFFIXES = (".db", ".sqlite", ".sqlite3")


@dataclass(frozen=True)
class Artifact:
    path: str
    category: str
    kind: str
    size_bytes: int
    sha256: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index tracked artifact-like files with coarse categories."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to `git rev-parse --show-toplevel`.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write CSV to this path instead of stdout.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many artifact rows, useful for smoke checks.",
    )
    return parser.parse_args()


def repo_root(explicit_root: Optional[Path]) -> Path:
    if explicit_root is not None:
        return explicit_root.resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def tracked_paths(root: Path) -> List[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    raw_paths = result.stdout.decode("utf-8").split("\0")
    return [path for path in raw_paths if path]


def starts_with_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def ends_with_any(path: str, suffixes: Iterable[str]) -> bool:
    lowered = path.lower()
    return any(lowered.endswith(suffix) for suffix in suffixes)


def category_for(path: str) -> Optional[str]:
    lowered = path.lower()
    name = Path(path).name.lower()

    if name in {".ds_store", "thumbs.db"}:
        return "local-metadata"
    if lowered.startswith("data/"):
        if lowered.endswith("/readme.md") or lowered == "data/readme.md":
            return None
        if lowered.endswith(".db") or ends_with_any(lowered, RUNTIME_SUFFIXES):
            return "runtime-state"
        if starts_with_any(lowered, DATA_INPUT_PREFIXES):
            return "data-input"
        if starts_with_any(lowered, DATA_OUTPUT_PREFIXES):
            return "generated-output"
        return "data-artifact"
    if lowered.startswith("paper/"):
        if "/archives/" in lowered:
            return "archive"
        if ends_with_any(lowered, IMAGE_SUFFIXES):
            return "figure"
        if ends_with_any(lowered, PAPER_OUTPUT_SUFFIXES):
            return "paper-output"
        if name in {"artifact_manifest_insert.tex", "grok_failures_table.tex"}:
            return "paper-output"
        return None
    if lowered.startswith("logs/") or lowered.startswith("verification/"):
        return "log"
    if ends_with_any(lowered, LOG_SUFFIXES):
        return "log"
    if lowered.startswith("archives/"):
        return "archive" if not lowered.endswith(".md") else None
    if ends_with_any(lowered, ARCHIVE_SUFFIXES):
        return "archive"
    if lowered.startswith("figures/"):
        return "figure"
    if ends_with_any(lowered, RUNTIME_SUFFIXES):
        return "runtime-state"
    if lowered.endswith(".pkg"):
        return "binary-package"
    return None


def subprocess_stderr(exc: subprocess.CalledProcessError) -> str:
    if exc.stderr is None:
        return ""
    if isinstance(exc.stderr, bytes):
        return exc.stderr.decode("utf-8", errors="replace")
    return str(exc.stderr)


def digest_file(path: Path) -> Tuple[str, int, str]:
    if path.is_symlink():
        target = os.readlink(path)
        data = target.encode("utf-8")
        return hashlib.sha256(data).hexdigest(), len(data), "symlink"

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest(), path.stat().st_size, "file"


def iter_artifacts(root: Path, limit: Optional[int]) -> Iterable[Artifact]:
    emitted = 0
    for rel_path in tracked_paths(root):
        category = category_for(rel_path)
        if category is None:
            continue

        full_path = root / rel_path
        if not full_path.exists() and not full_path.is_symlink():
            continue

        sha256, size_bytes, kind = digest_file(full_path)
        yield Artifact(
            path=rel_path,
            category=category,
            kind=kind,
            size_bytes=size_bytes,
            sha256=sha256,
        )
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def write_csv(artifacts: Iterable[Artifact], handle: TextIO) -> None:
    writer = csv.DictWriter(
        handle,
        fieldnames=["path", "category", "kind", "size_bytes", "sha256"],
        lineterminator="\n",
    )
    writer.writeheader()
    for artifact in artifacts:
        writer.writerow(
            {
                "path": artifact.path,
                "category": artifact.category,
                "kind": artifact.kind,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
        )


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        print("--limit must be a positive integer", file=sys.stderr)
        return 2

    try:
        root = repo_root(args.repo_root)
        artifacts = iter_artifacts(root, args.limit)
        if args.out is None:
            write_csv(artifacts, sys.stdout)
            return 0

        out_path = args.out if args.out.is_absolute() else root / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            write_csv(artifacts, handle)
        return 0
    except subprocess.CalledProcessError as exc:
        message = subprocess_stderr(exc)
        print(message.strip() or str(exc), file=sys.stderr)
        return exc.returncode or 1
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
