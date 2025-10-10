#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import yaml
import subprocess


DEFAULT_RAW_DIR = Path("docs/policy_guidance/raw")
DEFAULT_INDEX_PATH = Path("docs/policy_guidance/index.json")
MAX_CHARS = 600


@dataclass
class GuidanceChunk:
    id: str
    policies: Sequence[str]
    source: str
    citation: str
    text: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "policies": list(self.policies),
            "source": self.source,
            "citation": self.citation,
            "text": self.text,
        }


def parse_front_matter(raw_text: str) -> tuple[dict, str]:
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw_text
    meta_lines: List[str] = []
    idx = 1
    while idx < len(lines) and lines[idx].strip() != "---":
        meta_lines.append(lines[idx])
        idx += 1
    if idx >= len(lines):
        return {}, raw_text
    idx += 1  # skip closing '---'
    meta_text = "\n".join(meta_lines)
    metadata = yaml.safe_load(meta_text) or {}
    body = "\n".join(lines[idx:])
    return metadata, body


def chunk_text(body: str, max_chars: int = MAX_CHARS) -> Iterable[str]:
    paragraphs = [para.strip() for para in body.split("\n\n") if para.strip()]
    for paragraph in paragraphs:
        if paragraph.lstrip().startswith("#"):
            continue
        if len(paragraph) <= max_chars:
            yield paragraph
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        current = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = f"{current} {sentence}".strip()
            if len(candidate) > max_chars and current:
                yield current
                current = sentence
            else:
                current = candidate
        if current:
            yield current


def build_index(raw_dir: Path) -> List[GuidanceChunk]:
    chunks: List[GuidanceChunk] = []
    for path in sorted(raw_dir.glob("*.md")):
        raw_text = path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(raw_text)
        policies = metadata.get("policies") or []
        if not policies:
            continue
        source = metadata.get("source") or "Unknown source"
        citation = metadata.get("citation") or ""
        base_id = metadata.get("id") or path.stem
        for idx, text in enumerate(chunk_text(body), start=1):
            chunk_id = f"{base_id}#{idx}"
            chunks.append(
                GuidanceChunk(
                    id=chunk_id,
                    policies=policies,
                    source=source,
                    citation=citation,
                    text=text,
                )
            )
    return chunks


def write_index(chunks: Sequence[GuidanceChunk], index_path: Path) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [chunk.to_dict() for chunk in chunks]
    index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fetch_remote_sources(sources: Sequence[str], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for url in sources:
        if not url:
            continue
        filename = url.rstrip("/").split("/")[-1] or "guidance.md"
        target_path = destination / filename
        try:
            result = subprocess.run(
                ["curl", "-fsSL", url],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"Warning: failed to download {url}: {exc}")
            continue
        target_path.write_text(result.stdout, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the policy guidance retrieval index.")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Directory containing raw guidance markdown with YAML front matter.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_INDEX_PATH,
        help="Output JSON file for the compiled guidance index.",
    )
    parser.add_argument(
        "--fetch",
        action="append",
        default=None,
        help="Optional URL to download and place in the raw guidance directory (can be repeated).",
    )
    parser.add_argument(
        "--fetch-destination",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Destination directory for downloaded guidance sources (default: raw dir).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.fetch:
        fetch_remote_sources(args.fetch, args.fetch_destination)
    chunks = build_index(args.raw_dir)
    write_index(chunks, args.out)
    print(f"Wrote {len(chunks)} guidance chunk(s) to {args.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
