#!/usr/bin/env python3
"""Summarise verifier failures from a verifier JSON output file."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    TextIO,
    Tuple,
)


GATE_ORDER: Tuple[Tuple[str, str], ...] = (
    ("ok_schema", "Kubernetes schema / dry-run"),
    ("ok_policy", "target policy"),
    ("ok_safety", "patch safety"),
    ("ok_rescan", "post-patch rescan"),
)

NEXT_ACTIONS: Mapping[str, str] = {
    "ok_schema": "Fix generated manifest validity first; inspect kubectl dry-run errors and invalid field paths.",
    "ok_policy": "Adjust the patch for the target policy; compare patched YAML against the policy-specific verifier check.",
    "ok_safety": "Review patch side effects; remove unsafe hostPath, hostPort, capability, privilege, or rootfs regressions.",
    "ok_rescan": "Run the detector rescan locally and inspect kube-linter or Kyverno output for residual violations.",
    "unknown": "Rerun verification with errors enabled or inspect the source record; no failing gate flag was present.",
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a concise failure report from verifier JSON.",
    )
    parser.add_argument(
        "verified_json",
        nargs="?",
        type=Path,
        default=Path("data/verified.json"),
        help="Path to verifier JSON output (default: data/verified.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print a compact machine-readable report instead of markdown.",
    )
    parser.add_argument(
        "--max-groups",
        type=int,
        default=8,
        help="Maximum groups to show per markdown section (default: 8).",
    )
    parser.add_argument(
        "--max-ids",
        type=int,
        default=5,
        help="Maximum sample ids to show per group (default: 5).",
    )
    return parser.parse_args(argv)


def load_records(path: Path) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"failed to read {path}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array of verifier records")

    records: List[Dict[str, Any]] = []
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(f"{path} record {index} must be a JSON object")
        records.append(record)
    return records


def build_report(
    records: Sequence[Mapping[str, Any]],
    *,
    source: Optional[Path] = None,
    max_ids: int = 5,
) -> Dict[str, Any]:
    rejected = [record for record in records if record.get("accepted") is not True]
    accepted_count = len(records) - len(rejected)

    gate_buckets: Dict[Tuple[str, ...], List[Mapping[str, Any]]] = defaultdict(list)
    policy_buckets: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    error_buckets: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    action_counts: Counter[str] = Counter()

    for record in rejected:
        failing_gates = _failing_gates(record)
        gate_buckets[failing_gates].append(record)
        policy_buckets[_policy_id(record)].append(record)

        errors = _normalise_errors(record)
        if errors:
            for error in _unique(errors):
                error_buckets[error].append(record)
        else:
            error_buckets["(no errors recorded)"].append(record)

        if failing_gates == ("unknown",):
            action_counts["unknown"] += 1
        else:
            for gate in failing_gates:
                action_counts[gate] += 1

    return {
        "source": str(source) if source is not None else None,
        "summary": {
            "total": len(records),
            "accepted": accepted_count,
            "rejected": len(rejected),
        },
        "by_failing_gates": _serialise_tuple_groups(gate_buckets, max_ids=max_ids),
        "by_policy_id": _serialise_string_groups(policy_buckets, "policy_id", max_ids=max_ids),
        "by_error": _serialise_string_groups(error_buckets, "error", max_ids=max_ids),
        "next_actions": _next_actions(action_counts),
    }


def render_markdown(report: Mapping[str, Any], *, max_groups: int = 8) -> str:
    summary = report["summary"]
    lines = [
        "# Verifier Failure Report",
        "",
    ]
    source = report.get("source")
    if source:
        lines.append(f"Source: `{source}`")
    lines.append(
        "Total: {total} | Accepted: {accepted} | Rejected: {rejected}".format(**summary)
    )

    if summary["rejected"] == 0:
        lines.extend(["", "No rejected verifier records found."])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "## Rejected By Failing Gates",
            "",
            "| Failing gates | Count | Sample ids |",
            "| --- | ---: | --- |",
        ]
    )
    lines.extend(
        _render_groups(
            report["by_failing_gates"],
            key_name="gates",
            max_groups=max_groups,
            key_formatter=lambda value: ", ".join(value),
        )
    )

    lines.extend(
        [
            "",
            "## Rejected By Policy",
            "",
            "| Policy id | Count | Sample ids |",
            "| --- | ---: | --- |",
        ]
    )
    lines.extend(_render_groups(report["by_policy_id"], key_name="policy_id", max_groups=max_groups))

    lines.extend(
        [
            "",
            "## Top Errors",
            "",
            "| Error | Count | Sample ids |",
            "| --- | ---: | --- |",
        ]
    )
    lines.extend(
        _render_groups(
            report["by_error"],
            key_name="error",
            max_groups=max_groups,
            key_formatter=lambda value: _truncate(str(value), 140),
        )
    )

    lines.extend(["", "## Suggested Next Actions", ""])
    for action in report["next_actions"]:
        gate = action["gate"]
        count = action["count"]
        text = action["action"]
        label = "gate flags missing" if gate == "unknown" else f"{gate}=false"
        lines.append(f"- `{label}` ({count}): {text}")

    return "\n".join(lines) + "\n"


def _failing_gates(record: Mapping[str, Any]) -> Tuple[str, ...]:
    gates = tuple(gate for gate, _label in GATE_ORDER if record.get(gate) is False)
    return gates or ("unknown",)


def _policy_id(record: Mapping[str, Any]) -> str:
    value = record.get("policy_id")
    if value is None:
        return "(missing policy_id)"
    return str(value)


def _normalise_errors(record: Mapping[str, Any]) -> List[str]:
    errors = record.get("errors")
    if errors is None:
        return []
    if isinstance(errors, str):
        return [_one_line(errors)]
    if not isinstance(errors, list):
        return [_one_line(str(errors))]

    normalised: List[str] = []
    for error in errors:
        if error is None:
            continue
        text = _one_line(str(error))
        if text:
            normalised.append(text)
    return normalised


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _serialise_tuple_groups(
    buckets: Mapping[Tuple[str, ...], Sequence[Mapping[str, Any]]],
    *,
    max_ids: int,
) -> List[Dict[str, Any]]:
    groups = []
    for key, records in buckets.items():
        groups.append(
            {
                "gates": list(key),
                "count": len(records),
                "sample_ids": _sample_ids(records, max_ids=max_ids),
                "remaining": max(0, len(records) - max_ids),
            }
        )
    return sorted(groups, key=lambda item: (-item["count"], ", ".join(item["gates"])))


def _serialise_string_groups(
    buckets: Mapping[str, Sequence[Mapping[str, Any]]],
    key_name: str,
    *,
    max_ids: int,
) -> List[Dict[str, Any]]:
    groups = []
    for key, records in buckets.items():
        groups.append(
            {
                key_name: key,
                "count": len(records),
                "sample_ids": _sample_ids(records, max_ids=max_ids),
                "remaining": max(0, len(records) - max_ids),
            }
        )
    return sorted(groups, key=lambda item: (-item["count"], str(item[key_name])))


def _sample_ids(records: Sequence[Mapping[str, Any]], *, max_ids: int) -> List[str]:
    ids: List[str] = []
    for record in records[:max_ids]:
        value = record.get("id")
        ids.append("(missing id)" if value is None else str(value))
    return ids


def _next_actions(action_counts: Counter[str]) -> List[Dict[str, Any]]:
    gate_order = [gate for gate, _label in GATE_ORDER] + ["unknown"]
    actions = []
    for gate in gate_order:
        count = action_counts.get(gate, 0)
        if not count:
            continue
        actions.append(
            {
                "gate": gate,
                "count": count,
                "action": NEXT_ACTIONS[gate],
            }
        )
    return actions


def _render_groups(
    groups: Sequence[Mapping[str, Any]],
    *,
    key_name: str,
    max_groups: int,
    key_formatter: Optional[Callable[[Any], str]] = None,
) -> List[str]:
    lines: List[str] = []
    formatter = key_formatter or str
    shown = groups[:max_groups]
    for group in shown:
        key_value = formatter(group[key_name])
        sample_ids = ", ".join(group["sample_ids"])
        if group["remaining"]:
            if sample_ids:
                sample_ids = f"{sample_ids}, +{group['remaining']} more"
            else:
                sample_ids = f"+{group['remaining']} more"
        lines.append(
            f"| {_escape_table(key_value)} | {group['count']} | {_escape_table(sample_ids)} |"
        )
    if len(groups) > max_groups:
        lines.append(f"| ... | {len(groups) - max_groups} more group(s) hidden | ... |")
    return lines


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3] + "..."


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")


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
        if args.max_groups < 1:
            raise ValueError("--max-groups must be at least 1")
        if args.max_ids < 1:
            raise ValueError("--max-ids must be at least 1")
        records = load_records(args.verified_json)
        report = build_report(records, source=args.verified_json, max_ids=args.max_ids)
        if args.json_output:
            json.dump(report, stdout, indent=2)
            stdout.write("\n")
        else:
            stdout.write(render_markdown(report, max_groups=args.max_groups))
        return 0
    except ValueError as exc:
        stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
