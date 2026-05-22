#!/usr/bin/env python3
"""Scan repo text files for common committed-secret patterns."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


MAX_FILE_BYTES = 1_000_000
TEXT_CHUNK_BYTES = 8192
DOC_EXTENSIONS = {".md", ".rst", ".tex", ".txt"}
DEFAULT_SKIP_PREFIXES = (
    "archives/",
    "data/batch_runs/",
    "data/live_cluster/",
    "data/manifests/the_stack_sample/",
    "data/outputs/",
    "logs/",
    "verification/",
)
PLACEHOLDER_WORDS = {
    "changeme",
    "dummy",
    "example",
    "fake",
    "placeholder",
    "sample",
    "test",
    "your",
}


@dataclass(frozen=True)
class SecretRule:
    name: str
    pattern: re.Pattern[str]
    description: str
    doc_example_ok: bool = True


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    description: str
    evidence: str


RULES: Tuple[SecretRule, ...] = (
    SecretRule(
        "aws-access-key-id",
        re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b"),
        "AWS access key id",
    ),
    SecretRule(
        "github-token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
        "GitHub token",
    ),
    SecretRule(
        "openai-api-key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
        "OpenAI-compatible API key",
    ),
    SecretRule(
        "slack-token",
        re.compile(r"\bxox(?:b|p|o|a|r|s)-[A-Za-z0-9-]{24,}\b"),
        "Slack token",
    ),
    SecretRule(
        "private-key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        "private key block",
        doc_example_ok=False,
    ),
    SecretRule(
        "generic-secret-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|secret)\b"
            r"\s*[:=]\s*[\"'](?P<secret>[A-Za-z0-9_./+=-]{16,})[\"']"
        ),
        "high-entropy secret-like assignment",
    ),
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan tracked and unignored repo text files for common secret/token "
            "patterns. Findings are printed with redacted evidence."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to `git rev-parse --show-toplevel`.",
    )
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="Scan only tracked files instead of tracked plus untracked non-ignored files.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=MAX_FILE_BYTES,
        help=f"Skip files larger than this many bytes. Default: {MAX_FILE_BYTES}.",
    )
    parser.add_argument(
        "--include-artifacts",
        action="store_true",
        help="Also scan artifact-heavy sample/generated paths skipped by default.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON findings instead of the plain text report.",
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


def run_git(root: Path, args: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def is_default_skipped(path: str) -> bool:
    return path.startswith(DEFAULT_SKIP_PREFIXES)


def candidate_paths(root: Path, tracked_only: bool = False, include_artifacts: bool = False) -> List[str]:
    args = ["ls-files", "-z"]
    if not tracked_only:
        args.extend(["--cached", "--others", "--exclude-standard"])
    paths: List[str] = []
    for raw_path in run_git(root, args).split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if include_artifacts or not is_default_skipped(path):
            paths.append(path)
    return sorted(paths)


def is_probably_text(path: Path, max_file_bytes: int = MAX_FILE_BYTES) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    if not path.is_file() or stat.st_size > max_file_bytes:
        return False
    try:
        chunk = path.read_bytes()[:TEXT_CHUNK_BYTES]
    except OSError:
        return False
    return b"\0" not in chunk


def is_doc_example(path: str, line: str) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix not in DOC_EXTENSIONS:
        return False
    lowered = line.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def is_placeholder_secret(value: str) -> bool:
    lowered = value.lower()
    if any(word in lowered for word in PLACEHOLDER_WORDS):
        return True
    unique_chars = len(set(value))
    return unique_chars <= 4


def redact(line: str, span: Tuple[int, int]) -> str:
    start, end = span
    secret = line[start:end]
    if len(secret) <= 8:
        replacement = "<redacted>"
    else:
        replacement = f"{secret[:4]}...{secret[-4:]}"
    return f"{line[:start]}{replacement}{line[end:]}".strip()


def finding_for_match(path: str, line_number: int, line: str, rule: SecretRule, match: re.Match[str]) -> Optional[Finding]:
    secret = match.groupdict().get("secret") or match.group(0)
    if is_placeholder_secret(secret):
        return None
    if rule.doc_example_ok and is_doc_example(path, line):
        return None
    span = match.span("secret") if "secret" in match.groupdict() else match.span()
    return Finding(
        path=path,
        line=line_number,
        rule=rule.name,
        description=rule.description,
        evidence=redact(line, span),
    )


def scan_text(path: str, text: str, rules: Iterable[SecretRule] = RULES) -> List[Finding]:
    findings: List[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in rules:
            for match in rule.pattern.finditer(line):
                finding = finding_for_match(path, line_number, line, rule, match)
                if finding is not None:
                    findings.append(finding)
    return findings


def scan_repo(
    root: Path,
    tracked_only: bool = False,
    max_file_bytes: int = MAX_FILE_BYTES,
    include_artifacts: bool = False,
) -> List[Finding]:
    findings: List[Finding] = []
    for relative_path in candidate_paths(
        root,
        tracked_only=tracked_only,
        include_artifacts=include_artifacts,
    ):
        absolute_path = root / relative_path
        if not is_probably_text(absolute_path, max_file_bytes=max_file_bytes):
            continue
        try:
            text = absolute_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings.extend(scan_text(relative_path, text))
    return findings


def print_plain(findings: Sequence[Finding]) -> None:
    if not findings:
        print("No secret-like patterns found.")
        return

    print(f"Found {len(findings)} secret-like pattern(s):")
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}: {finding.rule}: "
            f"{finding.evidence}"
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = repo_root(args.repo_root)
    findings = scan_repo(
        root,
        tracked_only=args.tracked_only,
        max_file_bytes=args.max_file_bytes,
        include_artifacts=args.include_artifacts,
    )
    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        print_plain(findings)
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
