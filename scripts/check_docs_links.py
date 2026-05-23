#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import unquote, urlsplit


SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SETEXT_HEADING_RE = re.compile(r"^(=+|-+)\s*$")
REFERENCE_LINK_RE = re.compile(r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(.+?)\s*$")
HTML_LINK_RE = re.compile(r"""\b(?:href|src)=["']([^"']+)["']""", re.IGNORECASE)


@dataclass(frozen=True)
class MarkdownLink:
    source: Path
    line: int
    target: str


@dataclass(frozen=True)
class LinkIssue:
    source: Path
    line: int
    target: str
    message: str


@dataclass(frozen=True)
class CheckResult:
    files_checked: int
    links_checked: int
    issues: Sequence[LinkIssue]

    @property
    def ok(self) -> bool:
        return not self.issues


def discover_markdown_files(paths: Sequence[Path]) -> List[Path]:
    files: List[Path] = []
    seen: Set[Path] = set()

    for path in paths:
        if path.is_file():
            if path.suffix.lower() == ".md" and path not in seen:
                files.append(path)
                seen.add(path)
            continue
        if path.is_dir():
            for candidate in path.rglob("*.md"):
                if any(part in SKIPPED_DIRS for part in candidate.parts):
                    continue
                if candidate.is_file() and candidate not in seen:
                    files.append(candidate)
                    seen.add(candidate)

    return sorted(files)


def iter_content_lines(text: str) -> Iterable[tuple[int, str]]:
    fence_marker: Optional[str] = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if fence_marker:
            if stripped.startswith(fence_marker):
                fence_marker = None
            continue

        if stripped.startswith("```"):
            fence_marker = "```"
            continue
        if stripped.startswith("~~~"):
            fence_marker = "~~~"
            continue

        yield line_number, re.sub(r"`[^`]*`", "", line)


def parse_destination(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""

    if raw.startswith("<"):
        end = raw.find(">")
        destination = raw[1:end] if end != -1 else raw[1:]
    else:
        chars: List[str] = []
        escaped = False
        for char in raw:
            if escaped:
                chars.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char.isspace():
                break
            chars.append(char)
        destination = "".join(chars)

    return html.unescape(destination.strip())


def extract_inline_destinations(line: str) -> Iterable[str]:
    index = 0
    while True:
        start = line.find("](", index)
        if start == -1:
            return

        cursor = start + 2
        depth = 1
        escaped = False
        raw_chars: List[str] = []
        while cursor < len(line):
            char = line[cursor]
            if escaped:
                raw_chars.append(char)
                escaped = False
            elif char == "\\":
                raw_chars.append(char)
                escaped = True
            elif char == "(":
                depth += 1
                raw_chars.append(char)
            elif char == ")":
                depth -= 1
                if depth == 0:
                    yield parse_destination("".join(raw_chars))
                    break
                raw_chars.append(char)
            else:
                raw_chars.append(char)
            cursor += 1

        index = max(cursor + 1, start + 2)


def iter_links(path: Path) -> Iterable[MarkdownLink]:
    text = path.read_text(encoding="utf-8")
    for line_number, line in iter_content_lines(text):
        for destination in extract_inline_destinations(line):
            yield MarkdownLink(source=path, line=line_number, target=destination)

        reference_match = REFERENCE_LINK_RE.match(line)
        if reference_match:
            yield MarkdownLink(
                source=path,
                line=line_number,
                target=parse_destination(reference_match.group(1)),
            )

        for html_match in HTML_LINK_RE.finditer(line):
            yield MarkdownLink(source=path, line=line_number, target=html_match.group(1))


def normalize_heading(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"[*_~]", "", text)
    text = re.sub(r"\\(.)", r"\1", text)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def add_heading_anchor(anchors: Set[str], counts: Dict[str, int], heading: str) -> None:
    base = normalize_heading(heading)
    if not base:
        return

    count = counts.get(base, 0)
    counts[base] = count + 1
    anchors.add(base if count == 0 else f"{base}-{count}")


def collect_heading_anchors(path: Path) -> Set[str]:
    anchors: Set[str] = set()
    counts: Dict[str, int] = {}
    text = path.read_text(encoding="utf-8")
    pending_setext: Optional[str] = None

    for _, line in iter_content_lines(text):
        match = HEADING_RE.match(line)
        if match:
            add_heading_anchor(anchors, counts, match.group(2))
            pending_setext = None
            continue

        stripped = line.strip()
        if pending_setext and SETEXT_HEADING_RE.match(stripped):
            add_heading_anchor(anchors, counts, pending_setext)
            pending_setext = None
            continue

        pending_setext = stripped or None

    return anchors


def is_skipped_target(target: str) -> bool:
    parsed = urlsplit(target)
    if parsed.scheme.lower() in {"http", "https", "mailto"}:
        return True
    if parsed.scheme or parsed.netloc:
        return True
    if parsed.path.startswith("/"):
        return True
    return False


def case_sensitive_exists(path: Path) -> bool:
    if not path.exists():
        return False

    current = path.anchor
    parts = path.parts[1:] if path.anchor else path.parts
    probe = Path(current) if current else Path(".")

    for part in parts:
        try:
            names = {child.name for child in probe.iterdir()}
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            return False
        if part not in names:
            return False
        probe = probe / part

    return True


def resolve_local_path(source: Path, target_path: str, root: Path) -> Path:
    decoded_path = unquote(target_path)
    if decoded_path.startswith("/"):
        return (root / decoded_path.lstrip("/")).resolve()
    return (source.parent / decoded_path).resolve()


def check_link(link: MarkdownLink, root: Path, anchor_cache: Dict[Path, Set[str]]) -> Optional[LinkIssue]:
    target = link.target.strip()
    if not target:
        return LinkIssue(link.source, link.line, link.target, "empty link target")

    if is_skipped_target(target):
        return None

    parsed = urlsplit(target)
    target_path = parsed.path
    fragment = unquote(parsed.fragment)
    target_file = link.source.resolve() if not target_path else resolve_local_path(link.source.resolve(), target_path, root)

    if target_path and not case_sensitive_exists(target_file):
        return LinkIssue(link.source, link.line, link.target, f"missing target {target_path}")

    if not fragment or not target_file.is_file() or target_file.suffix.lower() != ".md":
        return None

    if fragment not in anchor_cache.setdefault(target_file, collect_heading_anchors(target_file)):
        return LinkIssue(link.source, link.line, link.target, f"missing anchor #{fragment}")

    return None


def check_paths(paths: Sequence[Path], root: Optional[Path] = None) -> CheckResult:
    if not paths:
        paths = [Path(".")]

    missing_paths = [path for path in paths if not path.exists()]
    issues = [
        LinkIssue(path, 0, str(path), "path does not exist")
        for path in missing_paths
    ]
    existing_paths = [path for path in paths if path.exists()]
    root = (root or Path.cwd()).resolve()
    files = discover_markdown_files(existing_paths)
    anchor_cache: Dict[Path, Set[str]] = {}
    links_checked = 0

    for file_path in files:
        for link in iter_links(file_path):
            if is_skipped_target(link.target.strip()):
                continue
            links_checked += 1
            issue = check_link(link, root, anchor_cache)
            if issue:
                issues.append(issue)

    return CheckResult(files_checked=len(files), links_checked=links_checked, issues=issues)


def format_report(result: CheckResult, cwd: Optional[Path] = None) -> str:
    cwd = (cwd or Path.cwd()).resolve()
    lines: List[str] = []

    if result.issues:
        lines.append("Broken local Markdown links:")
        for issue in result.issues:
            source = issue.source
            try:
                source_text = source.resolve().relative_to(cwd).as_posix()
            except ValueError:
                source_text = source.as_posix()
            location = source_text if issue.line <= 0 else f"{source_text}:{issue.line}"
            lines.append(f"  {location}: {issue.target} -> {issue.message}")

    summary = (
        f"Checked {result.files_checked} Markdown file(s), "
        f"{result.links_checked} local link(s), {len(result.issues)} broken."
    )
    if not result.issues:
        summary = (
            f"Checked {result.files_checked} Markdown file(s), "
            f"{result.links_checked} local link(s); no broken local links."
        )
    lines.append(summary)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local links in Markdown documentation.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".")],
        help="Markdown files or directories to scan (default: current directory).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = check_paths(args.paths)
    print(format_report(result))
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
