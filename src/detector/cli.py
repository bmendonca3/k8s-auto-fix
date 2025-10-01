from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import typer

from .detector import Detector

app = typer.Typer(help="Detect Kubernetes manifest violations using kube-linter and Kyverno.")


def _collect_from_inputs(paths: Iterable[Path]) -> List[Path]:
    files: List[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved.is_dir():
            files.extend(_collect_from_directory(resolved))
        elif resolved.exists():
            files.append(resolved)
    return _dedupe(files)


def _collect_from_directory(directory: Path) -> List[Path]:
    patterns = ("*.yml", "*.yaml")
    results: List[Path] = []
    for pattern in patterns:
        results.extend(directory.glob(pattern))
    return results


def _dedupe(paths: Iterable[Path]) -> List[Path]:
    unique: List[Path] = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


@app.command()
def detect(
    inputs: Optional[List[Path]] = typer.Option(
        None,
        "--in",
        "-i",
        help="Path(s) to manifest files or directories (defaults to data/manifests).",
    ),
    out: Path = typer.Option(
        Path("data/detections.json"),
        "--out",
        "-o",
        help="Where to write detections JSON file.",
    ),
    policies_dir: Optional[Path] = typer.Option(
        None,
        "--policies-dir",
        help="Directory containing Kyverno policies.",
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
    search_paths = inputs or [Path("data/manifests")]
    manifests = _collect_from_inputs(search_paths)
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
    detector.write_results(results, out)
    typer.echo(f"Detected {len(results)} violation(s). Report written to {out.resolve()}")


if __name__ == "__main__":  # pragma: no cover
    app()
