#!/usr/bin/env python3
"""Emit traceability records for generated artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, TextIO, Tuple


CHUNK_SIZE = 1024 * 1024


class ArtifactTraceabilityError(Exception):
    """Raised when an artifact cannot be traced."""


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    absolute_path: str
    exists: bool
    kind: str
    producer: Optional[str]
    category: Optional[str]
    note: Optional[str]
    size_bytes: Optional[int]
    sha256: Optional[str]

    def to_dict(self) -> dict:
        return {
            "absolute_path": self.absolute_path,
            "category": self.category,
            "exists": self.exists,
            "kind": self.kind,
            "note": self.note,
            "path": self.path,
            "producer": self.producer,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report artifact size, SHA-256, and producer metadata."
    )
    parser.add_argument(
        "--artifact",
        action="append",
        dest="artifacts",
        metavar="PATH",
        required=True,
        type=Path,
        help="Artifact path to trace. May be supplied more than once.",
    )
    parser.add_argument(
        "--producer",
        default=None,
        help="Producer applied to every emitted artifact record.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Category applied to every emitted artifact record.",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="Note applied to every emitted artifact record.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Emit missing records instead of failing on absent artifacts.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format. Defaults to JSON.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Shortcut for --format markdown.",
    )
    return parser.parse_args(argv)


def digest_artifact(path: Path) -> Tuple[str, int, str]:
    if path.is_symlink():
        target = os.readlink(path)
        data = target.encode("utf-8")
        return "symlink", len(data), hashlib.sha256(data).hexdigest()

    digest = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            size_bytes += len(chunk)
            digest.update(chunk)
    return "file", size_bytes, digest.hexdigest()


def display_path(path: Path, cwd: Path) -> str:
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return str(path)


def resolve_artifact_path(path: Path, cwd: Path) -> Path:
    if path.is_absolute():
        return Path(os.path.abspath(path))
    return Path(os.path.abspath(cwd / path))


def trace_artifact(
    path: Path,
    cwd: Path,
    producer: Optional[str],
    category: Optional[str],
    note: Optional[str],
    allow_missing: bool,
) -> ArtifactRecord:
    absolute_path = resolve_artifact_path(path, cwd)
    record_path = display_path(absolute_path, cwd)

    if not absolute_path.exists() and not absolute_path.is_symlink():
        if allow_missing:
            return ArtifactRecord(
                path=record_path,
                absolute_path=str(absolute_path),
                exists=False,
                kind="missing",
                producer=producer,
                category=category,
                note=note,
                size_bytes=None,
                sha256=None,
            )
        raise ArtifactTraceabilityError(
            "artifact not found: {path} ({absolute_path})".format(
                path=path, absolute_path=absolute_path
            )
        )

    if not absolute_path.is_symlink() and not absolute_path.is_file():
        raise ArtifactTraceabilityError(
            "artifact is not a file or symlink: {path} ({absolute_path})".format(
                path=record_path, absolute_path=absolute_path
            )
        )

    kind, size_bytes, sha256 = digest_artifact(absolute_path)
    return ArtifactRecord(
        path=record_path,
        absolute_path=str(absolute_path),
        exists=True,
        kind=kind,
        producer=producer,
        category=category,
        note=note,
        size_bytes=size_bytes,
        sha256=sha256,
    )


def trace_artifacts(
    paths: Iterable[Path],
    cwd: Path,
    producer: Optional[str],
    category: Optional[str],
    note: Optional[str],
    allow_missing: bool,
) -> List[ArtifactRecord]:
    resolved_cwd = cwd.resolve(strict=False)
    return [
        trace_artifact(
            path=path,
            cwd=resolved_cwd,
            producer=producer,
            category=category,
            note=note,
            allow_missing=allow_missing,
        )
        for path in paths
    ]


def write_json(records: Iterable[ArtifactRecord], handle: TextIO) -> None:
    payload = {"artifacts": [record.to_dict() for record in records]}
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")


def markdown_cell(value: Optional[object], code: bool = False) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("|", "\\|")
    if code and text:
        return "`{}`".format(text.replace("`", "\\`"))
    return text


def write_markdown(records: Iterable[ArtifactRecord], handle: TextIO) -> None:
    handle.write("# Artifact Traceability\n\n")
    handle.write(
        "| Path | Status | Kind | Producer | Category | Size bytes | SHA-256 | Note |\n"
    )
    handle.write("| --- | --- | --- | --- | --- | ---: | --- | --- |\n")
    for record in records:
        status = "present" if record.exists else "missing"
        handle.write(
            "| {path} | {status} | {kind} | {producer} | {category} | {size} | {sha} | {note} |\n".format(
                path=markdown_cell(record.path, code=True),
                status=status,
                kind=markdown_cell(record.kind),
                producer=markdown_cell(record.producer),
                category=markdown_cell(record.category),
                size=markdown_cell(record.size_bytes),
                sha=markdown_cell(record.sha256, code=True),
                note=markdown_cell(record.note),
            )
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output_format = "markdown" if args.markdown else args.format

    try:
        records = trace_artifacts(
            paths=args.artifacts,
            cwd=Path.cwd(),
            producer=args.producer,
            category=args.category,
            note=args.note,
            allow_missing=args.allow_missing,
        )
        if output_format == "markdown":
            write_markdown(records, sys.stdout)
        else:
            write_json(records, sys.stdout)
        return 0
    except (ArtifactTraceabilityError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
