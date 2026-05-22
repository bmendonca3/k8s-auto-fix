#!/usr/bin/env python3
"""Compose artifact traceability records into an evidence manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, TextIO


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts import artifact_traceability


SCHEMA_VERSION = 1


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a higher-level evidence manifest from selected artifacts, "
            "producer commands, and optional claim labels."
        )
    )
    parser.add_argument(
        "--artifact",
        action="append",
        dest="artifacts",
        default=[],
        type=Path,
        help="Artifact path to include. May be supplied more than once.",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help=(
            "Optional JSON spec with an 'artifacts' array. Each entry supports "
            "path, producer_command, claim_labels, category, and note."
        ),
    )
    parser.add_argument(
        "--producer-command",
        default=None,
        help="Producer command applied to artifacts supplied with --artifact.",
    )
    parser.add_argument(
        "--claim",
        action="append",
        dest="claims",
        default=[],
        help="Claim label applied to artifacts supplied with --artifact.",
    )
    parser.add_argument(
        "--claims-table",
        type=Path,
        default=None,
        help=(
            "Optional JSON file with a claims array. Each claim supports id, "
            "label, title, and description; id/label values are matched against "
            "artifact claim_labels."
        ),
    )
    parser.add_argument(
        "--fail-on-uncovered-claims",
        action="store_true",
        help=(
            "Exit nonzero when --claims-table includes expected claims that have "
            "no present evidence artifact."
        ),
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Category applied to artifacts supplied with --artifact.",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="Note applied to artifacts supplied with --artifact.",
    )
    parser.add_argument(
        "--pipeline-manifest",
        action="append",
        dest="pipeline_manifests",
        default=[],
        type=Path,
        help=(
            "Optional scripts/run_pipeline.py reproducibility manifest JSON to "
            "summarize alongside evidence artifacts. May be supplied more than once."
        ),
    )
    parser.add_argument(
        "--pipeline-status",
        action="append",
        dest="pipeline_statuses",
        default=[],
        type=Path,
        help=(
            "Optional scripts/run_pipeline.py per-stage status JSON to summarize "
            "alongside evidence artifacts. May be supplied more than once."
        ),
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Emit missing records instead of failing on absent artifacts.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format. Defaults to JSON.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Shortcut for --format markdown.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output file. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def build_manifest(
    *,
    cli_artifacts: Sequence[Path] = (),
    spec_path: Optional[Path] = None,
    producer_command: Optional[str] = None,
    claim_labels: Sequence[str] = (),
    claims_table_path: Optional[Path] = None,
    category: Optional[str] = None,
    note: Optional[str] = None,
    pipeline_manifest_paths: Sequence[Path] = (),
    pipeline_status_paths: Sequence[Path] = (),
    allow_missing: bool = False,
    cwd: Optional[Path] = None,
) -> dict[str, Any]:
    root = (cwd or Path.cwd()).resolve(strict=False)
    specs = _load_spec_records(spec_path) if spec_path is not None else []
    specs.extend(
        {
            "path": artifact,
            "producer_command": producer_command,
            "claim_labels": list(claim_labels),
            "category": category,
            "note": note,
        }
        for artifact in cli_artifacts
    )

    if not specs:
        raise ValueError("at least one --artifact or --spec artifact is required")

    records = [
        _build_record(spec, cwd=root, allow_missing=allow_missing)
        for spec in specs
    ]
    claims = _claim_summary(records)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(records),
        "claim_count": len(claims),
        "claims": claims,
        "artifacts": records,
    }
    if claims_table_path is not None:
        manifest["claim_table_coverage"] = _claim_table_coverage(
            records, path=claims_table_path, cwd=root
        )
    pipeline_sources, pipeline_stages = _load_pipeline_summaries(
        pipeline_manifest_paths=pipeline_manifest_paths,
        pipeline_status_paths=pipeline_status_paths,
        cwd=root,
    )
    if pipeline_sources:
        manifest["pipeline_sources"] = pipeline_sources
        manifest["pipeline_stages"] = pipeline_stages
    return manifest


def render_json(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def render_markdown(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# Evidence Manifest",
        "",
        f"Schema version: {manifest['schema_version']}",
        f"Artifact records: {manifest['record_count']}",
        "",
        (
            "| Path | Status | Producer command | Claims | Category | "
            "Size bytes | SHA-256 | Note |"
        ),
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for record in manifest["artifacts"]:
        status = "present" if record["exists"] else "missing"
        claims = ", ".join(record["claim_labels"])
        lines.append(
            (
                "| {path} | {status} | {producer} | {claims} | {category} | "
                "{size} | {sha} | {note} |"
            ).format(
                path=artifact_traceability.markdown_cell(record["path"], code=True),
                status=status,
                producer=artifact_traceability.markdown_cell(
                    record["producer_command"], code=True
                ),
                claims=artifact_traceability.markdown_cell(claims),
                category=artifact_traceability.markdown_cell(record["category"]),
                size=artifact_traceability.markdown_cell(record["size_bytes"]),
                sha=artifact_traceability.markdown_cell(record["sha256"], code=True),
                note=artifact_traceability.markdown_cell(record["note"]),
            )
        )
    claims = manifest.get("claims", [])
    if claims:
        lines.extend(
            [
                "",
                "## Claim Coverage",
                "",
                "| Claim | Artifacts | Present | Missing | Paths |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for claim in claims:
            paths = ", ".join(
                artifact_traceability.markdown_cell(path, code=True)
                for path in claim["paths"]
            )
            lines.append(
                (
                    "| {claim} | {artifacts} | {present} | {missing} | {paths} |"
                ).format(
                    claim=artifact_traceability.markdown_cell(claim["claim"]),
                    artifacts=claim["artifact_count"],
                    present=claim["present_count"],
                    missing=claim["missing_count"],
                    paths=paths,
                )
            )
    pipeline_stages = manifest.get("pipeline_stages", [])
    claim_table_coverage = manifest.get("claim_table_coverage")
    if isinstance(claim_table_coverage, Mapping):
        source_path = artifact_traceability.markdown_cell(
            claim_table_coverage.get("source_path"), code=True
        )
        expected_claims = claim_table_coverage.get("claim_count", 0)
        covered_claims = claim_table_coverage.get("covered_count", 0)
        uncovered_claims = claim_table_coverage.get("uncovered_count", 0)
        lines.extend(
            [
                "",
                "## Claim Table Coverage",
                "",
                f"Claims table: {source_path}",
                (
                    "Expected claims: {expected}; covered: {covered}; "
                    "uncovered: {uncovered}"
                ).format(
                    expected=expected_claims,
                    covered=covered_claims,
                    uncovered=uncovered_claims,
                ),
                "",
                "| Claim | Title | Evidence | Artifacts | Present | Missing | Paths |",
                "| --- | --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for claim in claim_table_coverage.get("claims", []):
            if not isinstance(claim, Mapping):
                continue
            paths = ", ".join(
                artifact_traceability.markdown_cell(path, code=True)
                for path in claim.get("paths", [])
            )
            lines.append(
                (
                    "| {claim} | {title} | {evidence} | {artifacts} | "
                    "{present} | {missing} | {paths} |"
                ).format(
                    claim=artifact_traceability.markdown_cell(
                        _claim_table_claim_name(claim)
                    ),
                    title=artifact_traceability.markdown_cell(claim.get("title")),
                    evidence=(
                        "covered" if claim.get("has_evidence") else "uncovered"
                    ),
                    artifacts=claim.get("artifact_count", 0),
                    present=claim.get("present_count", 0),
                    missing=claim.get("missing_count", 0),
                    paths=paths,
                )
            )
    if pipeline_stages:
        lines.extend(
            [
                "",
                "## Pipeline Stages",
                "",
                "| Source | Stage | Status | Inputs | Outputs | Command |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for stage in pipeline_stages:
            source = "{kind}:{path}".format(
                kind=stage.get("source_kind", ""),
                path=stage.get("source_path", ""),
            )
            lines.append(
                (
                    "| {source} | {stage} | {status} | {inputs} | {outputs} | "
                    "{command} |"
                ).format(
                    source=artifact_traceability.markdown_cell(source, code=True),
                    stage=artifact_traceability.markdown_cell(stage.get("name")),
                    status=artifact_traceability.markdown_cell(stage.get("status")),
                    inputs=_pipeline_metadata_markdown(stage.get("inputs", [])),
                    outputs=_pipeline_metadata_markdown(stage.get("outputs", [])),
                    command=artifact_traceability.markdown_cell(
                        stage.get("command_string"), code=True
                    ),
                )
            )
    return "\n".join(lines).rstrip() + "\n"


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = parse_args(argv)
        output_format = "markdown" if args.markdown else args.format
        manifest = build_manifest(
            cli_artifacts=args.artifacts,
            spec_path=args.spec,
            producer_command=args.producer_command,
            claim_labels=args.claims,
            claims_table_path=args.claims_table,
            category=args.category,
            note=args.note,
            pipeline_manifest_paths=args.pipeline_manifests,
            pipeline_status_paths=args.pipeline_statuses,
            allow_missing=args.allow_missing,
        )
        rendered = (
            render_markdown(manifest)
            if output_format == "markdown"
            else render_json(manifest)
        )
        if args.out is None:
            stdout.write(rendered)
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
        if args.fail_on_uncovered_claims:
            uncovered_claims = _uncovered_claim_names(manifest)
            if uncovered_claims:
                stderr.write(
                    "error: uncovered expected claims: {claims}\n".format(
                        claims=", ".join(uncovered_claims)
                    )
                )
                return 1
        return 0
    except (
        artifact_traceability.ArtifactTraceabilityError,
        OSError,
        ValueError,
    ) as exc:
        stderr.write(f"error: {exc}\n")
        return 2


def _load_spec_records(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse evidence spec {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"evidence spec {path} must be a JSON object")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError(f"evidence spec {path} must include an artifacts array")

    records: list[dict[str, Any]] = []
    for index, record in enumerate(artifacts):
        if not isinstance(record, dict):
            raise ValueError(f"evidence spec artifact {index} must be a JSON object")
        records.append(dict(record))
    return records


def _load_pipeline_summaries(
    *,
    pipeline_manifest_paths: Sequence[Path],
    pipeline_status_paths: Sequence[Path],
    cwd: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    for source_kind, paths in (
        ("pipeline_manifest", pipeline_manifest_paths),
        ("pipeline_status", pipeline_status_paths),
    ):
        for path in paths:
            source, source_stages = _load_pipeline_summary(
                path, source_kind=source_kind, cwd=cwd
            )
            sources.append(source)
            stages.extend(source_stages)
    return sources, stages


def _load_pipeline_summary(
    path: Path,
    *,
    source_kind: str,
    cwd: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _load_json_object(path, label=source_kind.replace("_", " "))
    stages = payload.get("stages")
    if not isinstance(stages, list):
        raise ValueError(
            f"{source_kind.replace('_', ' ')} {path} must include a stages array"
        )

    source_path = _display_pipeline_source_path(path, cwd)
    source: dict[str, Any] = {
        "kind": source_kind,
        "path": source_path,
        "stage_count": len(stages),
    }
    for key in ("schema_version", "mode", "timestamp", "resume"):
        if key in payload:
            source[key] = payload[key]

    compact_stages = [
        _compact_pipeline_stage(
            stage,
            source_kind=source_kind,
            source_path=source_path,
            index=index,
        )
        for index, stage in enumerate(stages)
    ]
    return source, compact_stages


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {label} {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{label} {path} must be a JSON object")
    return payload


def _load_claim_table(path: Path) -> list[dict[str, Any]]:
    payload = _load_json_object(path, label="claims table")
    claims = payload.get("claims")
    if not isinstance(claims, list):
        raise ValueError(f"claims table {path} must include a claims array")

    normalized: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"claims table claim {index} must be a JSON object")
        claim_id = _claim_table_optional_string(
            claim.get("id"), f"claims table claim {index} id"
        )
        label = _claim_table_optional_string(
            claim.get("label"), f"claims table claim {index} label"
        )
        title = _claim_table_optional_string(
            claim.get("title"), f"claims table claim {index} title"
        )
        description = _claim_table_optional_string(
            claim.get("description"), f"claims table claim {index} description"
        )
        match_labels = []
        for value in (claim_id, label):
            if value is not None and value not in match_labels:
                match_labels.append(value)
        if not match_labels:
            raise ValueError(
                f"claims table claim {index} must include a non-empty id or label"
            )
        normalized.append(
            {
                "id": claim_id,
                "label": label,
                "title": title,
                "description": description,
                "match_labels": match_labels,
            }
        )
    return normalized


def _claim_table_coverage(
    records: Sequence[Mapping[str, Any]],
    *,
    path: Path,
    cwd: Path,
) -> dict[str, Any]:
    expected_claims = _load_claim_table(path)
    coverage_claims = [
        _claim_table_claim_coverage(claim, records)
        for claim in expected_claims
    ]
    covered_count = sum(1 for claim in coverage_claims if claim["has_evidence"])
    return {
        "source_path": _display_claim_table_path(path, cwd),
        "claim_count": len(coverage_claims),
        "covered_count": covered_count,
        "uncovered_count": len(coverage_claims) - covered_count,
        "claims": coverage_claims,
    }


def _claim_table_claim_coverage(
    claim: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    match_labels = set(claim["match_labels"])
    claim_records: list[Mapping[str, Any]] = []
    matched_labels: set[str] = set()
    for record in records:
        labels = record.get("claim_labels", [])
        if not isinstance(labels, list):
            continue
        record_matches = [
            label for label in labels
            if isinstance(label, str) and label in match_labels
        ]
        if not record_matches:
            continue
        claim_records.append(record)
        matched_labels.update(record_matches)

    present_count = sum(1 for record in claim_records if record.get("exists"))
    return {
        "id": claim.get("id"),
        "label": claim.get("label"),
        "title": claim.get("title"),
        "description": claim.get("description"),
        "match_labels": list(claim["match_labels"]),
        "matched_claim_labels": sorted(matched_labels),
        "has_evidence": present_count > 0,
        "artifact_count": len(claim_records),
        "present_count": present_count,
        "missing_count": len(claim_records) - present_count,
        "paths": sorted(str(record["path"]) for record in claim_records),
    }


def _claim_table_optional_string(value: object, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    stripped = value.strip()
    return stripped or None


def _display_claim_table_path(path: Path, cwd: Path) -> str:
    absolute_path = artifact_traceability.resolve_artifact_path(path, cwd)
    return artifact_traceability.display_path(absolute_path, cwd)


def _claim_table_claim_name(claim: Mapping[str, Any]) -> str:
    claim_id = claim.get("id")
    label = claim.get("label")
    if isinstance(claim_id, str) and isinstance(label, str) and claim_id != label:
        return f"{claim_id} / {label}"
    if isinstance(claim_id, str):
        return claim_id
    if isinstance(label, str):
        return label
    return ""


def _uncovered_claim_names(manifest: Mapping[str, Any]) -> list[str]:
    claim_table_coverage = manifest.get("claim_table_coverage")
    if not isinstance(claim_table_coverage, Mapping):
        return []
    names = []
    for claim in claim_table_coverage.get("claims", []):
        if not isinstance(claim, Mapping) or claim.get("has_evidence"):
            continue
        claim_name = _claim_table_claim_name(claim)
        if claim_name:
            names.append(claim_name)
    return names


def _display_pipeline_source_path(path: Path, cwd: Path) -> str:
    absolute_path = artifact_traceability.resolve_artifact_path(path, cwd)
    return artifact_traceability.display_path(absolute_path, cwd)


def _compact_pipeline_stage(
    stage: object,
    *,
    source_kind: str,
    source_path: str,
    index: int,
) -> dict[str, Any]:
    if not isinstance(stage, dict):
        raise ValueError(
            f"{source_kind.replace('_', ' ')} stage {index} must be a JSON object"
        )
    name = stage.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            f"{source_kind.replace('_', ' ')} stage {index} must include a non-empty name"
        )

    record: dict[str, Any] = {
        "source_kind": source_kind,
        "source_path": source_path,
        "name": name,
        "inputs": _compact_pipeline_metadata(
            stage.get("input_paths", []),
            stage.get("input_metadata", []),
            field=f"{source_kind} stage {name} input",
        ),
        "outputs": _compact_pipeline_metadata(
            stage.get("output_paths", []),
            stage.get("output_metadata", []),
            field=f"{source_kind} stage {name} output",
        ),
    }
    for key in ("command_string", "status", "returncode", "skip_reason"):
        if key in stage:
            record[key] = stage[key]
    return record


def _compact_pipeline_metadata(
    paths_value: object,
    metadata_value: object,
    *,
    field: str,
) -> list[dict[str, Any]]:
    paths = _string_list(paths_value, field=f"{field}_paths")
    metadata = _metadata_list(metadata_value, field=f"{field}_metadata")
    used_metadata: set[int] = set()
    compact: list[dict[str, Any]] = []

    for index, path in enumerate(paths):
        metadata_index = _matching_metadata_index(path, index, metadata, used_metadata)
        if metadata_index is None:
            compact.append({"path": path})
            continue
        used_metadata.add(metadata_index)
        compact_record = _compact_pipeline_metadata_record(metadata[metadata_index])
        compact_record.setdefault("path", path)
        compact.append(compact_record)

    if not paths:
        for index, record in enumerate(metadata):
            used_metadata.add(index)
            compact.append(_compact_pipeline_metadata_record(record))

    return compact


def _matching_metadata_index(
    path: str,
    index: int,
    metadata: Sequence[Mapping[str, Any]],
    used_metadata: set[int],
) -> Optional[int]:
    if index < len(metadata) and index not in used_metadata:
        candidate_path = metadata[index].get("path")
        if candidate_path in (None, path):
            return index

    for candidate_index, candidate in enumerate(metadata):
        if candidate_index in used_metadata:
            continue
        if candidate.get("path") == path:
            return candidate_index
    return None


def _compact_pipeline_metadata_record(record: Mapping[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("path", "exists", "type", "sha256", "size_bytes"):
        if key in record:
            compact[key] = record[key]
    return compact


def _string_list(value: object, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field} entry {index} must be a string")
        strings.append(item)
    return strings


def _metadata_list(value: object, *, field: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    records: list[Mapping[str, Any]] = []
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(f"{field} entry {index} must be a JSON object")
        records.append(record)
    return records


def _pipeline_metadata_markdown(records: object) -> str:
    if not isinstance(records, list):
        return ""
    return "<br>".join(
        _pipeline_metadata_record_markdown(record)
        for record in records
        if isinstance(record, dict)
    )


def _pipeline_metadata_record_markdown(record: Mapping[str, Any]) -> str:
    path = artifact_traceability.markdown_cell(record.get("path"), code=True)
    details = []
    exists = record.get("exists")
    if isinstance(exists, bool):
        details.append("present" if exists else "missing")
    record_type = record.get("type")
    if isinstance(record_type, str) and record_type not in {"file", "missing"}:
        details.append(record_type)
    sha256 = record.get("sha256")
    if isinstance(sha256, str) and sha256:
        digest = artifact_traceability.markdown_cell(sha256[:12], code=True)
        details.append(f"sha256 {digest}")
    size_bytes = record.get("size_bytes")
    if isinstance(size_bytes, int):
        details.append(f"{size_bytes} bytes")
    if not details:
        return path
    return f"{path} ({', '.join(details)})"


def _build_record(
    spec: Mapping[str, Any],
    *,
    cwd: Path,
    allow_missing: bool,
) -> dict[str, Any]:
    path_value = spec.get("path")
    if not isinstance(path_value, (str, Path)) or not str(path_value).strip():
        raise ValueError("evidence artifact record must include a non-empty path")

    producer_command = _optional_string(
        spec.get("producer_command"), "producer_command"
    )
    category = _optional_string(spec.get("category"), "category")
    note = _optional_string(spec.get("note"), "note")
    claim_labels = _claim_labels(spec.get("claim_labels", []))

    trace_record = artifact_traceability.trace_artifact(
        path=Path(path_value),
        cwd=cwd,
        producer=producer_command,
        category=category,
        note=note,
        allow_missing=allow_missing,
    ).to_dict()
    trace_record["producer_command"] = trace_record.pop("producer")
    trace_record["claim_labels"] = claim_labels
    return trace_record


def _optional_string(value: object, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"evidence artifact {field} must be a string")
    return value


def _claim_labels(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Iterable):
        raise ValueError("evidence artifact claim_labels must be a string or array")

    labels: list[str] = []
    for label in value:
        if not isinstance(label, str):
            raise ValueError("evidence artifact claim_labels entries must be strings")
        if label:
            labels.append(label)
    return labels


def _claim_summary(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_claim: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        for claim in record.get("claim_labels", []):
            by_claim.setdefault(claim, []).append(record)

    summary: list[dict[str, Any]] = []
    for claim in sorted(by_claim):
        claim_records = by_claim[claim]
        present_count = sum(1 for record in claim_records if record.get("exists"))
        paths = sorted(str(record["path"]) for record in claim_records)
        summary.append(
            {
                "claim": claim,
                "artifact_count": len(claim_records),
                "present_count": present_count,
                "missing_count": len(claim_records) - present_count,
                "paths": paths,
            }
        )
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
