#!/usr/bin/env python3
"""List or delete ignored generated outputs from the repository."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Optional, Sequence


SAFE_TOP_LEVEL_DIRS = {"tmp", ".pytest_cache", "htmlcov", "build", "dist"}
SAFE_TOP_LEVEL_FILES = {".coverage"}


class CleanupRefused(RuntimeError):
    """Raised when a candidate is not safe to delete."""


@dataclass(frozen=True)
class CleanupCandidate:
    path: str
    safe: bool
    reason: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List ignored generated outputs. Pass --delete to remove only the "
            "ignored paths that match the built-in safe generated-output allowlist."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to `git rev-parse --show-toplevel`.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete safe ignored generated outputs instead of listing them.",
    )
    parser.add_argument(
        "--show-skipped",
        action="store_true",
        help="Also print ignored paths that were skipped as unsafe.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after printing or deleting this many safe candidates.",
    )
    return parser.parse_args(argv)


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


def run_git(root: Path, args: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def normalize_git_path(path: str) -> str:
    trimmed = path
    while trimmed.startswith("./"):
        trimmed = trimmed[2:]
    trimmed = trimmed.rstrip("/")
    return trimmed


def parse_ignored_status(output: bytes) -> List[str]:
    paths: List[str] = []
    for raw_entry in output.split(b"\0"):
        if not raw_entry or raw_entry[:2] != b"!!":
            continue
        raw_path = (
            raw_entry[3:]
            if len(raw_entry) > 2 and raw_entry[2:3] == b" "
            else raw_entry[2:]
        )
        path = normalize_git_path(raw_path.decode("utf-8", errors="surrogateescape"))
        if path:
            paths.append(path)
    return paths


def ignored_paths(root: Path) -> List[str]:
    result = run_git(
        root,
        ["status", "--ignored", "--short", "-z"],
    )
    return parse_ignored_status(result.stdout)


def safety_reason(path: str) -> Optional[str]:
    normalized = normalize_git_path(path)
    if not normalized:
        return None

    pure_path = PurePosixPath(normalized)
    parts = pure_path.parts
    if (
        not parts
        or normalized in {".", "/"}
        or pure_path.is_absolute()
        or ".." in parts
    ):
        return None

    if len(parts) == 1 and parts[0] in SAFE_TOP_LEVEL_FILES:
        return "coverage output"
    if parts[0] in SAFE_TOP_LEVEL_DIRS:
        return f"safe generated prefix {parts[0]}/"
    if "__pycache__" in parts:
        return "Python bytecode cache"
    if any(part.endswith(".egg-info") for part in parts):
        return "Python egg-info metadata"
    return None


def cleanup_candidates(paths: Iterable[str]) -> List[CleanupCandidate]:
    candidates: List[CleanupCandidate] = []
    seen: set[str] = set()
    for path in paths:
        normalized = normalize_git_path(path)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        reason = safety_reason(normalized)
        if reason is None:
            candidates.append(
                CleanupCandidate(
                    normalized,
                    False,
                    "outside safe generated-output allowlist",
                )
            )
        else:
            candidates.append(CleanupCandidate(normalized, True, reason))
    return candidates


def discover_candidates(root: Path) -> List[CleanupCandidate]:
    return cleanup_candidates(ignored_paths(root))


def is_ignored(root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", path],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    raise CleanupRefused(f"could not verify ignore status for {path!r}: {stderr}")


def tracked_entries(root: Path, path: str) -> List[str]:
    result = run_git(root, ["ls-files", "-z", "--", path])
    return [
        entry.decode("utf-8", errors="surrogateescape")
        for entry in result.stdout.split(b"\0")
        if entry
    ]


def validate_delete_candidate(root: Path, candidate: CleanupCandidate) -> Path:
    path = normalize_git_path(candidate.path)
    reason = safety_reason(path)
    if reason is None:
        raise CleanupRefused(f"refusing {candidate.path!r}: outside safe generated-output allowlist")
    if not candidate.safe:
        raise CleanupRefused(f"refusing {candidate.path!r}: {candidate.reason}")

    tracked = tracked_entries(root, path)
    if tracked:
        raise CleanupRefused(
            f"refusing {path!r}: path contains tracked entries: {', '.join(tracked[:3])}"
        )
    if not is_ignored(root, path):
        raise CleanupRefused(f"refusing {path!r}: path is not ignored by git")

    root_resolved = root.resolve()
    target = root / path
    parent = target.parent.resolve()
    try:
        parent.relative_to(root_resolved)
    except ValueError as exc:
        raise CleanupRefused(f"refusing {path!r}: path escapes repository root") from exc
    if target.resolve() == root_resolved:
        raise CleanupRefused(f"refusing {path!r}: path resolves to repository root")
    return target


def delete_candidate(root: Path, candidate: CleanupCandidate) -> None:
    target = validate_delete_candidate(root, candidate)
    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    else:
        raise CleanupRefused(f"refusing {candidate.path!r}: unsupported file type")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        print("--limit must be a positive integer", file=sys.stderr)
        return 2
    root = repo_root(args.repo_root)
    candidates = discover_candidates(root)
    safe_candidates = [candidate for candidate in candidates if candidate.safe]
    if args.limit is not None:
        safe_candidates = safe_candidates[: args.limit]
    skipped_candidates = [candidate for candidate in candidates if not candidate.safe]

    if args.delete:
        for candidate in safe_candidates:
            try:
                delete_candidate(root, candidate)
            except CleanupRefused as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"deleted {candidate.path}")
    else:
        for candidate in safe_candidates:
            print(candidate.path)

    if args.show_skipped:
        for candidate in skipped_candidates:
            print(f"skipped {candidate.path}: {candidate.reason}", file=sys.stderr)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
