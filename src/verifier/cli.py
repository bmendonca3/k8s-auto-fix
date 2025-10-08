from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from .verifier import Verifier
from pathlib import Path as _Path

app = typer.Typer(help="Verify patches against policies, schema, and safety gates.")


@app.command()
def verify(
    patches: Path = typer.Option(
        Path("data/patches.json"),
        "--patches",
        "-p",
        help="Path to patches JSON file.",
    ),
    out: Path = typer.Option(
        Path("data/verified.json"),
        "--out",
        "-o",
        help="Where to write verification results.",
    ),
    detections: Path = typer.Option(
        Path("data/detections.json"),
        "--detections",
        "-d",
        help="Detections file to retrieve manifest YAML by id.",
    ),
    kubectl_cmd: str = typer.Option(
        "kubectl",
        help="Kubectl binary used for dry-run validation.",
    ),
    require_kubectl: bool = typer.Option(
        True,
        "--require-kubectl/--no-require-kubectl",
        help="If disabled, verifier will pass schema gate when kubectl is missing.",
    ),
    enable_rescan: bool = typer.Option(
        False,
        "--enable-rescan",
        help="Re-run kube-linter and Kyverno on patched manifests and fail on any violation.",
    ),
    kube_linter_cmd: str = typer.Option(
        "kube-linter",
        help="Command used to invoke kube-linter for re-scan.",
    ),
    kyverno_cmd: str = typer.Option(
        "kyverno",
        help="Command used to invoke Kyverno for re-scan.",
    ),
    policies_dir: Optional[_Path] = typer.Option(
        None,
        "--policies-dir",
        help="Directory containing Kyverno policies for re-scan.",
    ),
    include_errors: bool = typer.Option(
        False,
        "--include-errors/--no-include-errors",
        help="Include verifier error messages in the output JSON.",
    ),
    jobs: int = typer.Option(
        1,
        "--jobs",
        "-j",
        min=1,
        help="Number of parallel workers to use (default: 1).",
    ),
) -> None:
    patch_records = _load_array(patches, "patches")
    detection_map = _load_detections(detections)

    verifier_kwargs = {
        "kubectl_cmd": kubectl_cmd,
        "require_kubectl": require_kubectl,
        "enable_rescan": enable_rescan,
        "kube_linter_cmd": kube_linter_cmd,
        "kyverno_cmd": kyverno_cmd,
        "policies_dir": policies_dir,
    }

    results: List[Dict[str, Any]] = []
    if jobs <= 1:
        verifier = Verifier(**verifier_kwargs)
        for record in patch_records:
            results.append(
                _verify_record(
                    record,
                    detection_map=detection_map,
                    include_errors=include_errors,
                    verifier_kwargs=verifier_kwargs,
                    verifier=verifier,
                    detections_path=detections,
                )
            )
    else:
        jobs = min(jobs, len(patch_records))
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = []
            for record in patch_records:
                futures.append(
                    executor.submit(
                        _verify_record,
                        record,
                        detection_map=detection_map,
                        include_errors=include_errors,
                        verifier_kwargs=verifier_kwargs,
                        detections_path=detections,
                    )
                )
            for future in futures:
                results.append(future.result())

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    typer.echo(f"Verified {len(results)} patch(es) to {out.resolve()}")


def _verify_record(
    record: Dict[str, Any],
    *,
    detection_map: Dict[str, Dict[str, Any]],
    include_errors: bool,
    verifier_kwargs: Dict[str, Any],
    detections_path: Path,
    verifier: Optional[Verifier] = None,
) -> Dict[str, Any]:
    patch_id = str(record.get("id"))
    policy_id = record.get("policy_id")
    patch_ops = record.get("patch")

    if patch_id not in detection_map:
        raise typer.BadParameter(f"Detection id {patch_id} missing from {detections_path}")
    if not isinstance(patch_ops, list):
        raise typer.BadParameter(f"Patch for id {patch_id} must be a list of operations")
    if not isinstance(policy_id, str):
        raise typer.BadParameter(f"Patch for id {patch_id} missing policy_id")

    detection = detection_map[patch_id]
    manifest_yaml = detection["manifest_yaml"]

    verifier_local = verifier if verifier is not None else Verifier(**verifier_kwargs)
    result = verifier_local.verify(manifest_yaml, patch_ops, policy_id)
    record_out = {
        "id": patch_id,
        "policy_id": policy_id,
        "accepted": result.accepted,
        "ok_schema": result.ok_schema,
        "ok_policy": result.ok_policy,
        "ok_safety": result.ok_safety,
        "ok_rescan": result.ok_rescan,
        "patched_yaml": result.patched_yaml,
    }
    if include_errors:
        record_out["errors"] = result.errors
    return record_out


def _load_array(path: Path, kind: str) -> List[Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"{kind.title()} file not found: {path}") from exc
    if not isinstance(data, list):
        raise typer.BadParameter(f"{kind.title()} file must contain a JSON array")
    return data


def _load_detections(path: Path) -> Dict[str, Dict[str, Any]]:
    records = _load_array(path, "detections")
    result: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        detection_id = str(record.get("id"))
        manifest_yaml = record.get("manifest_yaml")
        if manifest_yaml is None:
            manifest_path = record.get("manifest_path")
            if manifest_path:
                candidate = Path(manifest_path)
                if not candidate.is_absolute():
                    candidate = (path.parent / candidate).resolve()
                try:
                    manifest_yaml = candidate.read_text(encoding="utf-8")
                except OSError as exc:
                    raise typer.BadParameter(f"Failed to read manifest for id {detection_id}: {exc}") from exc
        if manifest_yaml is None:
            raise typer.BadParameter(f"Detection {detection_id} missing manifest YAML")
        result[detection_id] = {
            "manifest_yaml": manifest_yaml,
        }
    return result


if __name__ == "__main__":  # pragma: no cover
    app()
