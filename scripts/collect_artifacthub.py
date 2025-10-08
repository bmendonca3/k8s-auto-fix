from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

import requests
import yaml

ARTIFACTHUB_SEARCH_URL = "https://artifacthub.io/api/v1/packages/search"
DEFAULT_LIMIT = 25


def fetch_chart_metadata(limit: int, offset: int = 0) -> Iterable[dict]:
    remaining = limit
    page_size = min(100, remaining)
    current_offset = offset
    session = requests.Session()
    while remaining > 0:
        params = {
            "kind": 0,  # Helm charts
            "limit": min(page_size, remaining),
            "offset": current_offset,
        }
        response = session.get(ARTIFACTHUB_SEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        packages = payload.get("packages") or []
        if not packages:
            break
        for pkg in packages:
            yield pkg
            remaining -= 1
            if remaining <= 0:
                break
        current_offset += len(packages)


def run_helm_template(
    chart_name: str,
    repo_url: str,
    version: Optional[str],
) -> str:
    command = [
        "helm",
        "template",
        chart_name,
        "--repo",
        repo_url,
    ]
    if version:
        command.extend(["--version", version])
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise RuntimeError(
            f"helm template failed for chart={chart_name} repo={repo_url} version={version or 'latest'}: {stderr}"
        ) from exc


def split_manifests(rendered_yaml: str) -> list[dict]:
    manifests: list[dict] = []
    sanitized = rendered_yaml.replace("\t", "    ")
    for document in yaml.safe_load_all(sanitized):
        if isinstance(document, dict):
            manifests.append(document)
    return manifests


def format_manifest_filename(index: int, manifest: dict) -> str:
    kind = manifest.get("kind") or "unknown"
    metadata = manifest.get("metadata") or {}
    name = metadata.get("name") or f"resource-{index:03d}"
    safe_kind = "".join(ch for ch in str(kind) if ch.isalnum() or ch in ("-", "_")).lower() or "unknown"
    safe_name = "".join(ch for ch in str(name) if ch.isalnum() or ch in ("-", "_")).lower() or f"resource-{index:03d}"
    return f"{index:03d}_{safe_kind}_{safe_name}.yaml"


def write_manifest(directory: Path, filename: str, manifest: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False)


def collect_from_artifacthub(limit: int, output_dir: Path, offset: int = 0) -> dict:
    output_dir = output_dir.resolve()
    charts_processed = 0
    rendered_count = 0
    failures: list[dict] = []

    for package in fetch_chart_metadata(limit=limit, offset=offset):
        charts_processed += 1
        chart_name = package.get("name")
        repository = package.get("repository") or {}
        repo_name = repository.get("name") or "unknown_repo"
        repo_url = repository.get("url")
        latest_version = package.get("latest_version") or {}
        version = latest_version.get("version") or package.get("version")

        if not chart_name or not repo_url:
            failures.append(
                {
                    "chart": chart_name,
                    "repo": repo_url,
                    "reason": "missing chart name or repository URL",
                }
            )
            continue

        chart_dir = output_dir / repo_name / chart_name
        try:
            rendered_yaml = run_helm_template(chart_name, repo_url, version)
        except Exception as exc:  # pylint: disable=broad-except
            failures.append(
                {
                    "chart": chart_name,
                    "repo": repo_url,
                    "version": version,
                    "reason": str(exc),
                }
            )
            continue

        manifests = split_manifests(rendered_yaml)
        if not manifests:
            failures.append(
                {
                    "chart": chart_name,
                    "repo": repo_url,
                    "version": version,
                    "reason": "no manifests produced by helm template",
                }
            )
            continue

        for idx, manifest in enumerate(manifests, start=1):
            filename = format_manifest_filename(idx, manifest)
            write_manifest(chart_dir, filename, manifest)
            rendered_count += 1

    summary = {
        "charts_requested": limit,
        "charts_processed": charts_processed,
        "manifests_written": rendered_count,
        "failures": failures,
    }
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render and split Kubernetes manifests from popular ArtifactHub Helm charts."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of charts to fetch (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Offset into the ArtifactHub chart catalog (default: 0)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/manifests/artifacthub"),
        help="Directory where rendered manifests will be stored.",
    )
    args = parser.parse_args(argv)

    try:
        summary = collect_from_artifacthub(
            limit=args.limit,
            output_dir=args.output_dir,
            offset=args.offset,
        )
    except requests.HTTPError as exc:
        print(f"[artifacthub] API request failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[artifacthub] unexpected error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    if summary["failures"]:
        print(
            f"[artifacthub] Completed with {len(summary['failures'])} failures. See summary above.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
