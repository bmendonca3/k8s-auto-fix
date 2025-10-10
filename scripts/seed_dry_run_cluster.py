#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import yaml


def collect_crds(paths: Sequence[Path]) -> List[Dict[str, object]]:
    records: Dict[str, Dict[str, object]] = {}
    for path in paths:
        if path.is_dir():
            candidates = path.rglob("*.yaml")
        else:
            candidates = [path]
        for candidate in candidates:
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                documents = yaml.safe_load_all(text)
            except yaml.YAMLError:
                continue
            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                kind = doc.get("kind")
                if kind != "CustomResourceDefinition":
                    continue
                metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                name = metadata.get("name")
                if not isinstance(name, str) or not name:
                    continue
                records[name] = doc
    return list(records.values())


def write_docs(docs: Iterable[Dict[str, object]], target: Path) -> None:
    data = list(docs)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump_all(data, sort_keys=False), encoding="utf-8")


def apply_crds(kubectl: str, docs: Iterable[Dict[str, object]]) -> None:
    payload = list(docs)
    if not payload:
        print("No CRDs discovered in the provided manifests.")
        return
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=True) as handle:
        yaml.safe_dump_all(payload, handle, sort_keys=False)
        handle.flush()
        subprocess.run([kubectl, "apply", "-f", handle.name], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect CustomResourceDefinitions from manifests and seed a dry-run cluster.")
    parser.add_argument(
        "manifests",
        nargs="+",
        type=Path,
        help="Manifest file(s) or directories to scan for CRDs.",
    )
    parser.add_argument(
        "--kubectl",
        default="kubectl",
        help="Kubectl binary to use when applying CRDs (default: kubectl).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write the collected CRDs (YAML).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call kubectl; only gather and optionally write the CRDs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    crds = collect_crds(args.manifests)
    print(f"Discovered {len(crds)} CRD(s) across {len(args.manifests)} path(s).")
    if args.out:
        write_docs(crds, args.out)
        print(f"Wrote consolidated CRDs to {args.out}")
    if args.dry_run:
        return
    try:
        apply_crds(args.kubectl, crds)
    except subprocess.CalledProcessError as exc:
        print(f"kubectl apply failed: {exc}", file=sys.stderr)
        sys.exit(exc.returncode)


if __name__ == "__main__":  # pragma: no cover
    main()
