from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml

from .guards import PatchError, extract_json_array
from .model_client import ClientOptions, ModelClient
from src.verifier.jsonpatch_guard import validate_paths_exist

app = typer.Typer(help="Generate JSON patches from detections using configurable backends.")


@app.command()
def propose(
    detections: Path = typer.Option(
        Path("data/detections.json"),
        "--detections",
        "-d",
        help="Path to detections JSON file.",
    ),
    out: Path = typer.Option(
        Path("data/patches.json"),
        "--out",
        "-o",
        help="Where to write generated patches.",
    ),
    config: Path = typer.Option(
        Path("configs/run.yaml"),
        "--config",
        "-c",
        help="Run configuration file.",
    ),
) -> None:
    detections_data = _load_json(detections)
    config_data = _load_yaml(config)
    base_dir = detections.parent.resolve()

    mode = config_data.get("proposer", {}).get("mode", "rules")
    seed = config_data.get("seed")
    rng = random.Random(seed) if seed is not None else random.Random()
    generator = _build_generator(mode, config_data, seed)
    max_attempts = int(config_data.get("max_attempts", 1))

    patches: List[Dict[str, Any]] = []
    for record in detections_data:
        if not isinstance(record, dict):
            raise typer.BadParameter("Detection entries must be JSON objects")
        detection = _normalise_detection(record, base_dir)
        manifest_yaml = detection.get("manifest_yaml")
        policy_id = detection["policy_id"]
        detection_id = detection["id"]
        violation_text = detection["violation_text"]

        patch_ops: Optional[List[Dict[str, Any]]] = None
        attempts = 0
        errors: List[str] = []
        while attempts < max_attempts and patch_ops is None:
            attempts += 1
            try:
                raw_patch = generator(detection, rng)
                if isinstance(raw_patch, str):
                    patch_list = extract_json_array(raw_patch)
                else:
                    patch_list = raw_patch
                validate_paths_exist(manifest_yaml, patch_list)
                patch_ops = patch_list
            except PatchError as exc:
                errors.append(str(exc))
        if patch_ops is None:
            raise RuntimeError(
                f"Unable to produce patch for detection {detection_id} after {max_attempts} attempts: {errors}"
            )

        patches.append(
            {
                "id": detection_id,
                "policy_id": policy_id,
                "source": generator.source,
                "patch": patch_ops,
            }
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(patches, indent=2), encoding="utf-8")
    typer.echo(f"Generated {len(patches)} patch(es) to {out.resolve()}")


def _load_json(path: Path) -> List[Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Input file not found: {path}") from exc
    if not isinstance(data, list):
        raise typer.BadParameter("Detections file must contain a JSON array")
    return data


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Config file not found: {path}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("Config file must contain a mapping")
    return data


def _normalise_detection(record: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
    required_fields = {"id", "policy_id", "violation_text"}
    missing = required_fields - record.keys()
    if missing:
        raise typer.BadParameter(f"Detection missing required fields: {', '.join(sorted(missing))}")

    manifest_yaml = record.get("manifest_yaml")
    if manifest_yaml is None:
        manifest_path = record.get("manifest_path")
        if manifest_path:
            candidate = Path(manifest_path)
            if not candidate.is_absolute():
                candidate = (base_dir / candidate).resolve()
            try:
                manifest_yaml = candidate.read_text(encoding="utf-8")
            except OSError as exc:
                raise typer.BadParameter(f"Failed to read manifest {manifest_path}: {exc}") from exc
        else:
            raise typer.BadParameter("Detection must include manifest_yaml or manifest_path")
    return {
        "id": str(record["id"]),
        "policy_id": str(record["policy_id"]),
        "violation_text": str(record["violation_text"]),
        "manifest_yaml": manifest_yaml,
    }


class _GeneratorWrapper:
    def __init__(self, source: str, func):
        self.source = source
        self._func = func

    def __call__(self, detection: Dict[str, Any], rng: random.Random):
        return self._func(detection, rng)


def _build_generator(mode: str, config: Dict[str, Any], seed: Optional[int]) -> _GeneratorWrapper:
    mode_lower = (mode or "rules").lower()
    proposer_cfg = config.get("proposer", {})
    timeout = float(proposer_cfg.get("timeout_seconds", 60))
    retries = int(proposer_cfg.get("retries", 0))

    if mode_lower in {"vendor", "vllm"}:
        backend_cfg = config.get(mode_lower, {})
        options = ClientOptions(
            endpoint=backend_cfg.get("endpoint") or proposer_cfg.get("endpoint") or "http://localhost:8000",
            model=backend_cfg.get("model") or proposer_cfg.get("model") or "proposer-model",
            api_key_env=backend_cfg.get("api_key_env"),
            timeout_seconds=timeout,
            retries=retries,
            seed=seed,
        )
        client = ModelClient(options)

        def func(detection: Dict[str, Any], _rng: random.Random) -> str:
            prompt = _build_prompt(detection)
            return client.request_patch(prompt)

        return _GeneratorWrapper(mode_lower, func)

    if mode_lower == "rules":
        def func(detection: Dict[str, Any], _rng: random.Random) -> List[Dict[str, Any]]:
            return _rule_based_patch(detection)

        return _GeneratorWrapper("rules", func)

    raise typer.BadParameter(f"Unsupported proposer mode: {mode}")


def _build_prompt(detection: Dict[str, Any]) -> str:
    manifest_yaml = detection["manifest_yaml"]
    policy_id = detection["policy_id"]
    violation_text = detection["violation_text"]
    return (
        "You are fixing a Kubernetes manifest.\n"
        "Manifest YAML:\n"
        f"{manifest_yaml}\n\n"
        f"Policy: {policy_id}\n"
        f"Violation: {violation_text}\n"
        "Return ONLY a valid RFC6902 JSON Patch array."
    )


def _rule_based_patch(detection: Dict[str, Any]) -> List[Dict[str, Any]]:
    manifest_yaml = detection["manifest_yaml"]
    policy_id = detection["policy_id"]
    obj = yaml.safe_load(manifest_yaml) or {}

    if policy_id == "no_latest_tag":
        return _patch_no_latest(obj)
    if policy_id == "no_privileged":
        return _patch_no_privileged(obj)
    raise PatchError(f"no rule available for policy {policy_id}")


def _patch_no_latest(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            image = container.get("image")
            if isinstance(image, str) and image.endswith(":latest"):
                new_image = image.rsplit(":", 1)[0] + ":stable"
                path = f"{base_path}/containers/{idx}/image"
                return [{"op": "replace", "path": path, "value": new_image}]
    raise PatchError("no container with :latest tag found")


def _patch_no_privileged(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict) and security.get("privileged") is True:
                path = f"{base_path}/containers/{idx}/securityContext/privileged"
                return [{"op": "replace", "path": path, "value": False}]
    raise PatchError("no privileged container found")


def _find_containers(obj: Dict[str, Any]) -> List[tuple[str, List[Dict[str, Any]]]]:
    results: List[tuple[str, List[Dict[str, Any]]]] = []

    def visit(spec_obj: Any, base_path: str) -> None:
        if not isinstance(spec_obj, dict):
            return
        containers = spec_obj.get("containers")
        if isinstance(containers, list):
            valid_containers = [c for c in containers if isinstance(c, dict)]
            if valid_containers:
                results.append((base_path, valid_containers))
        template = spec_obj.get("template")
        if isinstance(template, dict):
            visit(template.get("spec"), f"{base_path}/template/spec")

    visit(obj.get("spec"), "/spec")
    return results


if __name__ == "__main__":  # pragma: no cover
    app()
