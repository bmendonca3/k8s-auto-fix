#!/usr/bin/env python3
"""Render unified YAML diffs for generated patch records."""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO

import jsonpatch
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print unified before/after YAML diffs for accepted patch records."
    )
    parser.add_argument(
        "--detections",
        type=Path,
        default=Path("data/detections.json"),
        help="JSON detections file used to retrieve original manifest YAML.",
    )
    parser.add_argument(
        "--patches",
        type=Path,
        default=Path("data/patches.json"),
        help="JSON file containing patch records.",
    )
    parser.add_argument(
        "--id",
        dest="ids",
        action="append",
        help="Only render the patch for this detection id. Repeat to render multiple ids.",
    )
    return parser.parse_args(argv)


def load_json_array(path: Path, label: str) -> list[Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"{label} file not found: {path}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{label} file must contain a JSON array")
    return data


def load_detection_map(path: Path) -> dict[str, dict[str, Any]]:
    detections = load_json_array(path, "detections")
    result: dict[str, dict[str, Any]] = {}
    for record in detections:
        if not isinstance(record, dict):
            continue
        if "id" not in record:
            continue
        detection_id = str(record["id"])
        manifest_yaml = _manifest_yaml(record, path.parent)
        result[detection_id] = {"manifest_yaml": manifest_yaml}
    return result


def _manifest_yaml(record: dict[str, Any], detections_dir: Path) -> str:
    manifest_yaml = record.get("manifest_yaml")
    if isinstance(manifest_yaml, str):
        return manifest_yaml

    manifest_path = record.get("manifest_path")
    if not isinstance(manifest_path, str) or not manifest_path.strip():
        detection_id = record.get("id", "<unknown>")
        raise ValueError(f"Detection {detection_id} missing manifest YAML")

    candidate = _resolve_manifest_path(Path(manifest_path), detections_dir)
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError as exc:
        detection_id = record.get("id", "<unknown>")
        raise ValueError(f"Failed to read manifest for id {detection_id}: {exc}") from exc


def _resolve_manifest_path(path: Path, detections_dir: Path) -> Path:
    if path.is_absolute():
        return path
    candidates = (
        detections_dir / path,
        Path.cwd() / path,
        REPO_ROOT / path,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (detections_dir / path).resolve()


def accepted_patch_records(records: Iterable[Any], ids: set[str] | None = None) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    matched_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Patch records must be JSON objects")
        record_id = str(record.get("id"))
        if ids is not None:
            if record_id not in ids:
                continue
            matched_ids.add(record_id)
        if record.get("accepted") is False:
            continue
        selected.append(record)

    if ids is not None and not matched_ids:
        raise ValueError("No patches matched the provided id filter")
    return selected


def render_patch_diffs(
    detections_path: Path,
    patches_path: Path,
    ids: Iterable[str] | None = None,
) -> list[str]:
    detection_map = load_detection_map(detections_path)
    patch_records = load_json_array(patches_path, "patches")
    id_filter = {str(item) for item in ids} if ids else None
    records = accepted_patch_records(patch_records, id_filter)

    return [render_record_diff(record, detection_map, detections_path) for record in records]


def render_record_diff(
    record: dict[str, Any],
    detection_map: dict[str, dict[str, Any]],
    detections_path: Path,
) -> str:
    record_id = str(record.get("id"))
    if record_id not in detection_map:
        raise ValueError(f"Detection id {record_id} missing from {detections_path}")

    manifest_yaml = detection_map[record_id]["manifest_yaml"]
    before_obj = _load_first_yaml_document(manifest_yaml)
    after_obj = _patched_object(before_obj, record, record_id)

    before_yaml = _dump_yaml(before_obj)
    after_yaml = _dump_yaml(after_obj)
    policy_id = record.get("policy_id")
    label = record_id if not isinstance(policy_id, str) else f"{record_id}-{policy_id}"
    diff_lines = difflib.unified_diff(
        before_yaml.splitlines(keepends=True),
        after_yaml.splitlines(keepends=True),
        fromfile=f"{label}:before.yaml",
        tofile=f"{label}:after.yaml",
    )
    return "".join(diff_lines)


def _load_first_yaml_document(manifest_yaml: str) -> Any:
    documents = list(yaml.safe_load_all(manifest_yaml))
    if not documents:
        raise ValueError("manifest is empty")
    return documents[0]


def _patched_object(before_obj: Any, record: dict[str, Any], record_id: str) -> Any:
    patch_ops = record.get("patch")
    if isinstance(patch_ops, list):
        try:
            return jsonpatch.apply_patch(copy.deepcopy(before_obj), patch_ops, in_place=False)
        except jsonpatch.JsonPatchException as exc:
            raise ValueError(f"Patch for id {record_id} failed to apply: {exc}") from exc

    patched_yaml = record.get("patched_yaml")
    if isinstance(patched_yaml, str):
        return _load_first_yaml_document(patched_yaml)

    raise ValueError(f"Patch for id {record_id} must include patch operations or patched_yaml")


def _dump_yaml(value: Any) -> str:
    return yaml.safe_dump(value, sort_keys=False)


def main(argv: list[str] | None = None, stdout: TextIO | None = None) -> int:
    args = parse_args(argv)
    output = stdout if stdout is not None else sys.stdout
    chunks = render_patch_diffs(args.detections, args.patches, args.ids)
    for index, chunk in enumerate(chunks):
        if index:
            output.write("\n")
        output.write(chunk)
        if chunk and not chunk.endswith("\n"):
            output.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
