#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import requests
import yaml

RAW_DIR = Path("docs/policy_guidance/raw")


@dataclass
class Source:
    id: str
    description: str
    url: Optional[str] = None
    path: Optional[Path] = None
    sections: Optional[List[str]] = None


def load_sources(manifest: Path) -> Iterable[Source]:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    entries = data.get("sources", []) if isinstance(data, dict) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        extract = entry.get("extract", {})
        sections = None
        if isinstance(extract, dict):
            sections = extract.get("sections")
            if isinstance(sections, list):
                sections = [str(item) for item in sections if isinstance(item, str)]
            else:
                sections = None
        url = entry.get("url")
        path = entry.get("path")
        yield Source(
            id=str(entry.get("id")),
            description=str(entry.get("description")),
            url=str(url) if isinstance(url, str) else None,
            path=Path(path) if isinstance(path, str) else None,
            sections=sections,
        )


def fetch_content(source: Source) -> str:
    if source.path:
        return source.path.read_text(encoding="utf-8")
    if not source.url:
        raise ValueError(f"Source {source.id} missing url or path")
    response = requests.get(source.url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_sections(text: str, sections: Optional[List[str]]) -> str:
    if not sections:
        return text
    blocks = []
    for heading in sections:
        pattern = re.compile(rf"^#+\s+{re.escape(heading)}.*?(?=^#|\Z)", re.MULTILINE | re.DOTALL)
        match = pattern.search(text)
        if match:
            blocks.append(match.group().strip())
    return "\n\n".join(blocks) if blocks else text


def write_raw(source: Source, content: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    header_dict = {
        "source": source.url or str(source.path),
        "description": source.description,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    header = "---\n" + json.dumps(header_dict, indent=2) + "\n---\n"
    path = RAW_DIR / f"{source.id}.md"
    path.write_text(header + content.strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh policy guidance snippets from upstream sources.")
    parser.add_argument("--manifest", type=Path, default=Path("docs/policy_guidance/sources.yaml"))
    args = parser.parse_args()

    for source in load_sources(args.manifest):
        text = fetch_content(source)
        extracted = extract_sections(text, source.sections)
        write_raw(source, extracted)
        print(f"Refreshed {source.id} from {source.url}")


if __name__ == "__main__":  # pragma: no cover
    main()
