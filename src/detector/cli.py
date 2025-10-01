from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

from .detector import Detector

app = typer.Typer(help="Detect Kubernetes manifest violations using kube-linter and Kyverno.")


def _collect_manifest_files(files: List[Path], directories: List[Path]) -> List[Path]:
    collected: List[Path] = []
    for path in files:
        if path.is_dir():
            collected.extend(_collect_from_directory(path))
        else:
            collected.append(path)
    for directory in directories:
        collected.extend(_collect_from_directory(directory))
    unique = []
    seen = set()
    for path in collected:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _collect_from_directory(directory: Path) -> List[Path]:
    patterns = ("*.yml", "*.yaml")
    results: List[Path] = []
    for pattern in patterns:
        results.extend(directory.glob(pattern))
    return results


@app.command()
def detect(
    manifest: List[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Path to a manifest file. Repeat for multiple manifests.",
    ),
    manifest_dir: List[Path] = typer.Option(
        None,
        "--manifest-dir",
        help="Directory containing manifest files. Scans *.yml and *.yaml.",
    ),
    policies_dir: Optional[Path] = typer.Option(
        None,
        "--policies-dir",
        help="Directory containing Kyverno policies.",
    ),
    output: Path = typer.Option(
        Path("detector-output.json"),
        "--output",
        "-o",
        help="Where to write the JSON violations report.",
    ),
    kube_linter_cmd: str = typer.Option(
        "kube-linter",
        help="Command used to invoke kube-linter.",
    ),
    kyverno_cmd: str = typer.Option(
        "kyverno",
        help="Command used to invoke Kyverno.",
    ),
) -> None:
    if not manifest and not manifest_dir:
        raise typer.BadParameter("Provide at least one --manifest or --manifest-dir.")

    manifests = _collect_manifest_files(manifest or [], manifest_dir or [])
    if not manifests:
        raise typer.BadParameter("No manifest files found to analyse.")

    if policies_dir is not None:
        policies_dir = policies_dir.resolve()
        if not policies_dir.exists():
            raise typer.BadParameter(f"Policies directory not found: {policies_dir}")

    detector = Detector(
        kube_linter_cmd=kube_linter_cmd,
        kyverno_cmd=kyverno_cmd,
        policies_dir=policies_dir,
    )
    results = detector.detect(manifests)
    detector.write_results(results, output)
    typer.echo(f"Detected {len(results)} violation(s). Report written to {output.resolve()}")


if __name__ == "__main__":  # pragma: no cover
    app()
