#!/usr/bin/env python3
"""Build an operator review packet from existing review/report surfaces."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, TextIO


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts import artifact_traceability
from scripts import queue_report
from scripts import render_patch_diff
from scripts import scheduler_explain
from scripts import verifier_report
from src.scheduler.rollout import annotate_rollout_batches


DEFAULT_MAX_DIFFS = 5
DEFAULT_CONCISE_LIMIT = 5


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a repeatable operator review packet from pipeline artifacts.",
    )
    parser.add_argument(
        "--detections",
        type=Path,
        required=True,
        help="JSON detections file used to retrieve original manifest YAML.",
    )
    parser.add_argument(
        "--patches",
        type=Path,
        required=True,
        help="JSON file containing patch records.",
    )
    parser.add_argument(
        "--verified",
        type=Path,
        required=True,
        help="JSON verifier output file.",
    )
    parser.add_argument(
        "--schedule",
        type=Path,
        default=None,
        help="Optional JSON scheduler candidates file. Included when the path exists.",
    )
    parser.add_argument(
        "--queue-db",
        type=Path,
        default=None,
        help="Optional scheduler queue SQLite DB. Included when the path exists.",
    )
    parser.add_argument(
        "--batches",
        type=Path,
        default=None,
        help=(
            "Optional scheduler batch summary JSON. When supplied, batches are "
            "annotated with rollout window and blast-radius metadata."
        ),
    )
    parser.add_argument(
        "--rollout-default-window",
        default="standard",
        help="Default rollout change-window label for annotated batches.",
    )
    parser.add_argument(
        "--rollout-max-count",
        type=int,
        default=None,
        help="Block rollout batches with more than this many patch ids.",
    )
    parser.add_argument(
        "--rollout-max-total-risk",
        type=float,
        default=None,
        help="Block rollout batches whose total risk exceeds this value.",
    )
    parser.add_argument(
        "--rollout-max-namespaces",
        type=int,
        default=None,
        help="Block rollout batches spanning more than this many namespaces.",
    )
    parser.add_argument(
        "--rollout-max-policies",
        type=int,
        default=None,
        help="Block rollout batches spanning more than this many policies.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        dest="artifacts",
        type=Path,
        default=[],
        help="Optional artifact path to trace. May be supplied more than once.",
    )
    parser.add_argument(
        "--id",
        dest="ids",
        action="append",
        help="Only include patch diffs for this detection id. Repeat for multiple ids.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument(
        "--markdown-mode",
        choices=("full", "concise"),
        default="full",
        help=(
            "Markdown detail level. 'full' preserves the operator packet; "
            "'concise' emits a PR/release-friendly summary without diffs "
            "(default: full)."
        ),
    )
    parser.add_argument(
        "--max-diffs",
        type=int,
        default=DEFAULT_MAX_DIFFS,
        help=f"Maximum selected patch diffs to include (default: {DEFAULT_MAX_DIFFS}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output file. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def build_packet(
    *,
    detections_path: Path,
    patches_path: Path,
    verified_path: Path,
    schedule_path: Optional[Path] = None,
    queue_db_path: Optional[Path] = None,
    batches_path: Optional[Path] = None,
    artifact_paths: Sequence[Path] = (),
    ids: Optional[Sequence[str]] = None,
    max_diffs: int = DEFAULT_MAX_DIFFS,
    rollout_default_window: str = "standard",
    rollout_max_count: Optional[int] = None,
    rollout_max_total_risk: Optional[float] = None,
    rollout_max_namespaces: Optional[int] = None,
    rollout_max_policies: Optional[int] = None,
    cwd: Optional[Path] = None,
) -> dict[str, Any]:
    if max_diffs < 0:
        raise ValueError("--max-diffs must be at least 0")

    detections = _load_json_objects(detections_path, "detections")
    patch_records = _load_json_objects(patches_path, "patches")
    verified_records = verifier_report.load_records(verified_path)
    verifier_summary = verifier_report.build_report(
        verified_records, source=verified_path, max_ids=5
    )

    verifier_accepted_ids = _verifier_accepted_ids(verified_records)
    selected_patch_records = _selected_patch_records(
        patch_records,
        ids,
        verifier_accepted_ids=verifier_accepted_ids,
    )
    patch_diffs = _build_patch_diffs(
        detections_path=detections_path,
        patch_records=selected_patch_records[:max_diffs],
    )

    schedule = _build_schedule_section(schedule_path)
    queue = _build_queue_section(queue_db_path)
    rollout = _build_rollout_section(
        batches_path,
        default_window=rollout_default_window,
        max_count=rollout_max_count,
        max_total_risk=rollout_max_total_risk,
        max_namespaces=rollout_max_namespaces,
        max_policies=rollout_max_policies,
    )
    artifacts = _build_artifact_section(artifact_paths, cwd=cwd or Path.cwd())

    verifier_counts = verifier_summary["summary"]
    counts = {
        "detections": len(detections),
        "patch_records": len(patch_records),
        "accepted_patch_records": len(
            _selected_patch_records(
                patch_records,
                None,
                verifier_accepted_ids=verifier_accepted_ids,
            )
        ),
        "selected_patch_records": len(selected_patch_records),
        "patch_diffs_included": len(patch_diffs),
        "verifier_records": len(verified_records),
        "verifier_accepted": verifier_counts["accepted"],
        "verifier_rejected": verifier_counts["rejected"],
        "schedule_candidates": _optional_count(schedule, "candidate_count"),
        "queue_items": _optional_count(queue, "total_items"),
        "artifact_records": _optional_count(artifacts, "record_count"),
    }
    if rollout["status"] != "not_requested":
        counts.update(
            {
                "rollout_batches": _optional_count(rollout, "batch_count"),
                "rollout_selected_batches": _optional_count(
                    rollout, "selected_batch_count"
                ),
                "rollout_blocked_batches": _optional_count(
                    rollout, "blocked_batch_count"
                ),
            }
        )

    sources = {
        "detections": str(detections_path),
        "patches": str(patches_path),
        "verified": str(verified_path),
        "schedule": str(schedule_path) if schedule_path is not None else None,
        "queue_db": str(queue_db_path) if queue_db_path is not None else None,
    }
    if batches_path is not None:
        sources["batches"] = str(batches_path)

    filters: dict[str, Any] = {
        "ids": list(ids) if ids else None,
        "max_diffs": max_diffs,
    }
    if batches_path is not None:
        filters["rollout"] = {
            "default_window": rollout_default_window,
            "max_count": rollout_max_count,
            "max_total_risk": rollout_max_total_risk,
            "max_namespaces": rollout_max_namespaces,
            "max_policies": rollout_max_policies,
        }

    packet = {
        "sources": sources,
        "filters": filters,
        "counts": counts,
        "verifier_report": verifier_summary,
        "selected_patch_ids": [
            str(record.get("id")) for record in selected_patch_records
        ],
        "patch_diffs": patch_diffs,
        "schedule": schedule,
        "queue": queue,
        "artifacts": artifacts,
    }
    if rollout["status"] != "not_requested":
        packet["rollout"] = rollout
    return packet


def render_markdown(packet: Mapping[str, Any]) -> str:
    lines = [
        "# Operator Review Packet",
        "",
        "## Summary Counts",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]
    for key, value in packet["counts"].items():
        lines.append(f"| {_label(key)} | {_count_cell(value)} |")

    filters = packet["filters"]
    if filters.get("ids"):
        ids = ", ".join(str(item) for item in filters["ids"])
        lines.extend(["", f"Selected ids: `{_escape_inline(ids)}`"])
    lines.append(f"Max diffs: {filters['max_diffs']}")

    lines.extend(["", "## Verifier Report Summary", ""])
    lines.append(
        _shift_markdown_headings(
            verifier_report.render_markdown(packet["verifier_report"], max_groups=5),
            levels=2,
        ).rstrip()
    )

    lines.extend(["", "", "## Selected Patch Diffs", ""])
    selected_count = packet["counts"]["selected_patch_records"]
    included_count = packet["counts"]["patch_diffs_included"]
    lines.append(
        f"Included {included_count} of {selected_count} selected accepted patch record(s)."
    )
    if not packet["patch_diffs"]:
        lines.extend(["", "No selected patch diffs."])
    for diff_record in packet["patch_diffs"]:
        lines.extend(["", f"### `{_escape_inline(diff_record['id'])}`"])
        policy_id = diff_record.get("policy_id")
        if policy_id is not None:
            lines.append(f"Policy: `{_escape_inline(str(policy_id))}`")
        diff = diff_record["diff"].rstrip()
        if diff:
            lines.extend(["", "```diff", diff, "```"])
        else:
            lines.extend(["", "Patch produced no textual diff."])

    schedule = packet["schedule"]
    if schedule["status"] != "not_requested":
        lines.extend(["", "## Schedule Summary", ""])
        if schedule["status"] == "missing":
            lines.append(f"Skipped: `{_escape_inline(schedule['path'])}` does not exist.")
        else:
            lines.append(f"Source: `{_escape_inline(schedule['path'])}`")
            lines.append(f"Candidates: {schedule['candidate_count']}")
            lines.extend(
                [
                    "",
                    _shift_markdown_headings(
                        scheduler_explain.render_markdown(schedule["explanation"]),
                        levels=2,
                    ).rstrip(),
                ]
            )

    queue = packet["queue"]
    if queue["status"] != "not_requested":
        lines.extend(["", "## Queue Report", ""])
        if queue["status"] == "missing":
            lines.append(f"Skipped: `{_escape_inline(queue['path'])}` does not exist.")
        else:
            lines.append(
                _shift_markdown_headings(
                    queue_report.render_markdown(queue["report"]), levels=2
                ).rstrip()
            )

    rollout = packet.get("rollout", {"status": "not_requested"})
    if rollout["status"] != "not_requested":
        lines.extend(["", "## Rollout Batch Summary", ""])
        if rollout["status"] == "missing":
            lines.append(f"Skipped: `{_escape_inline(rollout['path'])}` does not exist.")
        else:
            lines.extend(_rollout_markdown_lines(rollout))

    artifacts = packet["artifacts"]
    if artifacts["status"] != "not_requested":
        lines.extend(["", "## Artifact Traceability Records", ""])
        lines.extend(_artifact_markdown_lines(artifacts["records"]))

    return "\n".join(lines).rstrip() + "\n"


def render_concise_markdown(
    packet: Mapping[str, Any],
    *,
    limit: int = DEFAULT_CONCISE_LIMIT,
) -> str:
    lines = [
        "# PR / Release Review Summary",
        "",
        "## Counts",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]
    for key, value in packet["counts"].items():
        lines.append(f"| {_label(key)} | {_count_cell(value)} |")

    lines.extend(["", "## Verifier Rejects", ""])
    verifier_report_data = packet["verifier_report"]
    rejected = verifier_report_data["summary"]["rejected"]
    lines.append(f"Rejected verifier records: {rejected}")
    if rejected:
        lines.extend(
            [
                "",
                "| Failing gates | Count | Sample ids |",
                "| --- | ---: | --- |",
            ]
        )
        for group in verifier_report_data["by_failing_gates"][:limit]:
            gates = ", ".join(str(gate) for gate in group["gates"])
            sample_ids = ", ".join(str(item) for item in group["sample_ids"])
            lines.append(
                f"| {_escape_table(gates)} | {group['count']} | {_escape_table(sample_ids)} |"
            )

    lines.extend(["", "## Selected Patch IDs", ""])
    selected_count = packet["counts"]["selected_patch_records"]
    selected_ids = [str(item) for item in packet.get("selected_patch_ids", [])]
    if selected_ids:
        lines.append(f"Selected patch IDs: {_limited_code_list(selected_ids, limit)}")
    else:
        lines.append("No selected patch IDs were rendered.")
    lines.append(f"Selected accepted patch records: {selected_count}")
    lines.append(
        "Patch diffs included in full packet: "
        f"{packet['counts']['patch_diffs_included']}"
    )

    schedule = packet["schedule"]
    if schedule["status"] != "not_requested":
        lines.extend(["", "## Schedule Top Entries", ""])
        if schedule["status"] == "missing":
            lines.append(f"Skipped: `{_escape_inline(schedule['path'])}` does not exist.")
        else:
            candidates = schedule["explanation"]["candidates"][:limit]
            if candidates:
                lines.extend(
                    [
                        "| Priority | ID | Score |",
                        "| ---: | --- | ---: |",
                    ]
                )
                for candidate in candidates:
                    lines.append(
                        "| {priority} | {id} | {score} |".format(
                            priority=candidate["priority"],
                            id=_escape_table(str(candidate["id"])),
                            score=_format_number(candidate["score"]),
                        )
                    )
            else:
                lines.append("No schedule candidates.")

    rollout = packet.get("rollout", {"status": "not_requested"})
    if rollout["status"] != "not_requested":
        lines.extend(["", "## Rollout Batch Summary", ""])
        if rollout["status"] == "missing":
            lines.append(f"Skipped: `{_escape_inline(rollout['path'])}` does not exist.")
        else:
            lines.append(
                "Selected rollout batches: "
                f"{rollout['selected_batch_count']} of {rollout['batch_count']}"
            )
            lines.append(f"Blocked rollout batches: {rollout['blocked_batch_count']}")
            blocked_batches = rollout["blocked_batches"][:limit]
            if blocked_batches:
                lines.extend(
                    [
                        "",
                        "| Blocked batch | Reasons | Count | Total risk |",
                        "| --- | --- | ---: | ---: |",
                    ]
                )
                for batch in blocked_batches:
                    blast_radius = batch["blast_radius"]
                    lines.append(
                        "| {batch} | {reasons} | {count} | {risk} |".format(
                            batch=_escape_table(str(batch["id"])),
                            reasons=_rollout_reasons_cell(batch),
                            count=blast_radius["count"],
                            risk=_format_number(blast_radius["total_risk"]),
                        )
                    )
            selected_batches = rollout["selected_batches"][:limit]
            if selected_batches:
                lines.extend(
                    [
                        "",
                        "| Selected batch | Window | Count | Total risk | IDs |",
                        "| --- | --- | ---: | ---: | --- |",
                    ]
                )
                for batch in selected_batches:
                    blast_radius = batch["blast_radius"]
                    lines.append(
                        "| {batch} | {window} | {count} | {risk} | {ids} |".format(
                            batch=_escape_table(str(batch["id"])),
                            window=_escape_table(str(batch["change_window"])),
                            count=blast_radius["count"],
                            risk=_format_number(blast_radius["total_risk"]),
                            ids=_table_list(batch.get("ids", []), limit=limit),
                        )
                    )
            else:
                lines.append("No rollout batches selected by the current limits.")

    artifacts = packet["artifacts"]
    if artifacts["status"] != "not_requested":
        lines.extend(["", "## Artifact Hashes", ""])
        records = artifacts.get("records", [])[:limit]
        if records:
            lines.extend(
                [
                    "| Path | Size bytes | SHA-256 |",
                    "| --- | ---: | --- |",
                ]
            )
            for record in records:
                lines.append(
                    "| {path} | {size} | {sha} |".format(
                        path=artifact_traceability.markdown_cell(
                            record["path"], code=True
                        ),
                        size=artifact_traceability.markdown_cell(record["size_bytes"]),
                        sha=artifact_traceability.markdown_cell(
                            record["sha256"], code=True
                        ),
                    )
                )
        else:
            lines.append("No artifact records.")

    return "\n".join(lines).rstrip() + "\n"


def render_json(packet: Mapping[str, Any]) -> str:
    payload = dict(packet)
    payload.pop("selected_patch_ids", None)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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
        packet = build_packet(
            detections_path=args.detections,
            patches_path=args.patches,
            verified_path=args.verified,
            schedule_path=args.schedule,
            queue_db_path=args.queue_db,
            batches_path=args.batches,
            artifact_paths=args.artifacts,
            ids=args.ids,
            max_diffs=args.max_diffs,
            rollout_default_window=args.rollout_default_window,
            rollout_max_count=args.rollout_max_count,
            rollout_max_total_risk=args.rollout_max_total_risk,
            rollout_max_namespaces=args.rollout_max_namespaces,
            rollout_max_policies=args.rollout_max_policies,
        )
        if args.format == "json":
            rendered = render_json(packet)
        elif args.markdown_mode == "concise":
            rendered = render_concise_markdown(packet)
        else:
            rendered = render_markdown(packet)
        if args.out is None:
            stdout.write(rendered)
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
        return 0
    except (artifact_traceability.ArtifactTraceabilityError, OSError, ValueError) as exc:
        stderr.write(f"error: {exc}\n")
        return 2


def _load_json_objects(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        data = render_patch_diff.load_json_array(path, label)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {label} file {path}: {exc}") from exc

    records: list[dict[str, Any]] = []
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(f"{label} file record {index} must be a JSON object")
        records.append(record)
    return records


def _selected_patch_records(
    patch_records: Iterable[Mapping[str, Any]],
    ids: Optional[Sequence[str]],
    *,
    verifier_accepted_ids: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    id_filter = {str(item) for item in ids} if ids else None
    selected: list[dict[str, Any]] = []
    matched_requested_ids: set[str] = set()
    for record in render_patch_diff.accepted_patch_records(patch_records, None):
        record_id = str(record.get("id"))
        if ids and record_id in id_filter:
            matched_requested_ids.add(record_id)
        if id_filter is not None and record_id not in id_filter:
            continue
        if verifier_accepted_ids is not None and record_id not in verifier_accepted_ids:
            continue
        selected.append(record)
    if ids and not matched_requested_ids:
        raise ValueError("No patches matched the provided id filter")
    return selected


def _verifier_accepted_ids(records: Iterable[Mapping[str, Any]]) -> set[str]:
    accepted: set[str] = set()
    for record in records:
        if record.get("accepted") is True and record.get("id") is not None:
            accepted.add(str(record["id"]))
    return accepted


def _build_patch_diffs(
    *,
    detections_path: Path,
    patch_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    detection_map = render_patch_diff.load_detection_map(detections_path)
    diffs: list[dict[str, Any]] = []
    for record in patch_records:
        record_id = str(record.get("id"))
        diffs.append(
            {
                "id": record_id,
                "policy_id": record.get("policy_id"),
                "diff": render_patch_diff.render_record_diff(
                    dict(record), detection_map, detections_path
                ),
            }
        )
    return diffs


def _build_schedule_section(schedule_path: Optional[Path]) -> dict[str, Any]:
    if schedule_path is None:
        return {"status": "not_requested"}
    if not schedule_path.exists():
        return {"status": "missing", "path": str(schedule_path)}

    records = _normalise_schedule_candidates(_load_json_objects(schedule_path, "schedule"))
    explanation = scheduler_explain.explain_candidates(records)
    return {
        "status": "included",
        "path": str(schedule_path),
        "candidate_count": len(records),
        "explanation": explanation,
    }


def _normalise_schedule_candidates(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    normalised: list[Mapping[str, Any]] = []
    for record in records:
        candidate = dict(record)
        if "risk" not in candidate and "R" in candidate:
            candidate["risk"] = candidate["R"]
        if "probability" not in candidate and "p" in candidate:
            candidate["probability"] = candidate["p"]
        if "expected_time" not in candidate and "Et" in candidate:
            candidate["expected_time"] = candidate["Et"]
        normalised.append(candidate)
    return normalised


def _build_queue_section(queue_db_path: Optional[Path]) -> dict[str, Any]:
    if queue_db_path is None:
        return {"status": "not_requested"}
    if not queue_db_path.exists():
        return {"status": "missing", "path": str(queue_db_path)}

    report = queue_report.build_report(queue_db_path)
    return {
        "status": "included",
        "path": str(queue_db_path),
        "total_items": report["summary"]["total_items"],
        "report": report,
    }


def _build_rollout_section(
    batches_path: Optional[Path],
    *,
    default_window: str,
    max_count: Optional[int],
    max_total_risk: Optional[float],
    max_namespaces: Optional[int],
    max_policies: Optional[int],
) -> dict[str, Any]:
    if batches_path is None:
        return {"status": "not_requested"}
    if not batches_path.exists():
        return {"status": "missing", "path": str(batches_path)}

    batches = _load_json_objects(batches_path, "batches")
    annotated = annotate_rollout_batches(
        batches,
        default_window=default_window,
        max_count=max_count,
        max_total_risk=max_total_risk,
        max_namespaces=max_namespaces,
        max_policies=max_policies,
    )
    selected_batches = [
        batch for batch in annotated if bool(batch.get("rollout_allowed"))
    ]
    blocked_batches = [
        batch for batch in annotated if not bool(batch.get("rollout_allowed"))
    ]
    return {
        "status": "included",
        "path": str(batches_path),
        "batch_count": len(annotated),
        "selected_batch_count": len(selected_batches),
        "blocked_batch_count": len(blocked_batches),
        "batches": annotated,
        "selected_batches": selected_batches,
        "blocked_batches": blocked_batches,
    }


def _build_artifact_section(
    artifact_paths: Sequence[Path],
    *,
    cwd: Path,
) -> dict[str, Any]:
    if not artifact_paths:
        return {"status": "not_requested"}

    records = artifact_traceability.trace_artifacts(
        paths=artifact_paths,
        cwd=cwd,
        producer=None,
        category=None,
        note=None,
        allow_missing=False,
    )
    return {
        "status": "included",
        "record_count": len(records),
        "records": [record.to_dict() for record in records],
    }


def _optional_count(section: Mapping[str, Any], key: str) -> Optional[int]:
    if section.get("status") != "included":
        return None
    value = section.get(key)
    return int(value) if value is not None else None


def _artifact_markdown_lines(records: Sequence[Mapping[str, Any]]) -> list[str]:
    output = io.StringIO()
    output.write("| Path | Status | Kind | Producer | Category | Size bytes | SHA-256 | Note |\n")
    output.write("| --- | --- | --- | --- | --- | ---: | --- | --- |\n")
    for record in records:
        status = "present" if record["exists"] else "missing"
        output.write(
            "| {path} | {status} | {kind} | {producer} | {category} | {size} | {sha} | {note} |\n".format(
                path=artifact_traceability.markdown_cell(record["path"], code=True),
                status=status,
                kind=artifact_traceability.markdown_cell(record["kind"]),
                producer=artifact_traceability.markdown_cell(record["producer"]),
                category=artifact_traceability.markdown_cell(record["category"]),
                size=artifact_traceability.markdown_cell(record["size_bytes"]),
                sha=artifact_traceability.markdown_cell(record["sha256"], code=True),
                note=artifact_traceability.markdown_cell(record["note"]),
            )
        )
    return output.getvalue().rstrip().splitlines()


def _rollout_markdown_lines(rollout: Mapping[str, Any]) -> list[str]:
    lines = [
        f"Source: `{_escape_inline(rollout['path'])}`",
        f"Batches: {rollout['batch_count']}",
        f"Selected rollout batches: {rollout['selected_batch_count']}",
        f"Blocked rollout batches: {rollout['blocked_batch_count']}",
    ]
    batches = rollout.get("batches", [])
    if not batches:
        lines.extend(["", "No rollout batches."])
        return lines

    lines.extend(
        [
            "",
            "| Batch | Window | Allowed | Count | Total risk | Namespaces | Policies | Reasons | IDs |",
            "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for batch in batches:
        blast_radius = batch["blast_radius"]
        lines.append(
            "| {batch} | {window} | {allowed} | {count} | {risk} | {namespaces} | {policies} | {reasons} | {ids} |".format(
                batch=_escape_table(str(batch["id"])),
                window=_escape_table(str(batch["change_window"])),
                allowed="yes" if batch["rollout_allowed"] else "no",
                count=blast_radius["count"],
                risk=_format_number(blast_radius["total_risk"]),
                namespaces=_table_list(batch.get("namespaces", [])),
                policies=_table_list(batch.get("policies", [])),
                reasons=_rollout_reasons_cell(batch),
                ids=_table_list(batch.get("ids", [])),
            )
        )
    return lines


def _rollout_reasons_cell(batch: Mapping[str, Any]) -> str:
    return _table_list(batch.get("rollout_reasons", []))


def _shift_markdown_headings(markdown: str, *, levels: int) -> str:
    shifted = []
    for line in markdown.splitlines():
        if line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            if hashes and len(line) > hashes and line[hashes] == " ":
                line = "#" * min(6, hashes + levels) + line[hashes:]
        shifted.append(line)
    return "\n".join(shifted) + ("\n" if markdown.endswith("\n") else "")


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _count_cell(value: object) -> str:
    return "n/a" if value is None else str(value)


def _format_number(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _limited_code_list(values: Sequence[str], limit: int) -> str:
    rendered = ", ".join(f"`{_escape_inline(value)}`" for value in values[:limit])
    remaining = len(values) - limit
    if remaining > 0:
        return f"{rendered} (+{remaining} more)"
    return rendered


def _table_list(values: object, *, limit: Optional[int] = None) -> str:
    if isinstance(values, str):
        items = [values] if values else []
    elif isinstance(values, Iterable):
        items = [str(item) for item in values if str(item)]
    else:
        items = [str(values)] if values is not None else []

    if limit is not None and len(items) > limit:
        shown = items[:limit]
        rendered = ", ".join(shown)
        rendered = f"{rendered} (+{len(items) - limit} more)"
    else:
        rendered = ", ".join(items)
    return _escape_table(rendered) if rendered else "n/a"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def _escape_inline(value: str) -> str:
    return value.replace("`", "\\`")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
