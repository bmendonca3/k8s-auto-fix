#!/usr/bin/env python3
"""Report scheduler queue health from an existing SQLite database."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.scheduler.schedule import EPSILON, PatchCandidate, schedule_patches  # noqa: E402


REQUIRED_COLUMNS = {
    "id",
    "policy_id",
    "state",
    "attempts",
    "max_attempts",
    "enqueued_at",
    "risk",
    "probability",
    "expected_time",
    "kev",
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report scheduler queue health without mutating the queue database.",
    )
    parser.add_argument(
        "db",
        nargs="?",
        type=Path,
        default=Path("data/queue.db"),
        help="Path to the scheduler queue SQLite DB (default: data/queue.db).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print a machine-readable JSON report instead of markdown.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of queued candidates to include (default: 10).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Wait-time weight used by the scheduler scoring formula (default: 1.0).",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=EPSILON,
        help=f"Minimum expected_time denominator (default: {EPSILON}).",
    )
    parser.add_argument(
        "--kev-weight",
        type=float,
        default=1.0,
        help="KEV boost used by the scheduler scoring formula (default: 1.0).",
    )
    return parser.parse_args(argv)


def build_report(
    db_path: Path,
    *,
    now: Optional[float] = None,
    top: int = 10,
    alpha: float = 1.0,
    epsilon: float = EPSILON,
    kev_weight: float = 1.0,
) -> Dict[str, Any]:
    if top < 1:
        raise ValueError("--top must be at least 1")
    if epsilon <= 0:
        raise ValueError("--epsilon must be greater than 0")

    now_value = time.time() if now is None else now
    rows = _load_items_read_only(db_path)
    state_counts = _state_counts(rows)
    queued_rows = [row for row in rows if _state(row) == "queued"]
    top_queued = _top_queued(
        queued_rows,
        now=now_value,
        top=top,
        alpha=alpha,
        epsilon=epsilon,
        kev_weight=kev_weight,
    )

    return {
        "source": str(db_path),
        "generated_at": _format_epoch(now_value),
        "summary": {
            "total_items": len(rows),
            "state_counts": dict(sorted(state_counts.items())),
        },
        "attempts": _attempt_signals(rows),
        "oldest_queued": _oldest_queued(queued_rows, now=now_value),
        "top_queued": top_queued,
        "scoring": {
            "formula": "(risk * probability) / max(expected_time, epsilon) + alpha * wait_hours + kev_weight_if_kev",
            "alpha": alpha,
            "epsilon": epsilon,
            "kev_weight": kev_weight,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    attempts = report["attempts"]
    lines = [
        "# Scheduler Queue Report",
        "",
        f"Source: `{report['source']}`",
        f"Generated at: `{report['generated_at']}`",
        f"Total items: {summary['total_items']}",
        "",
        "## State Counts",
        "",
        "| State | Count |",
        "| --- | ---: |",
    ]

    state_counts = summary["state_counts"]
    if state_counts:
        for state, count in state_counts.items():
            lines.append(f"| {_escape_table(str(state))} | {count} |")
    else:
        lines.append("| (none) | 0 |")

    lines.extend(
        [
            "",
            "## Attempts Risk Signals",
            "",
            "| Signal | Count |",
            "| --- | ---: |",
            f"| Items with attempts | {attempts['items_with_attempts']} |",
            f"| Items one attempt from max | {attempts['items_one_attempt_from_max']} |",
            f"| Items at or over max attempts | {attempts['items_at_or_over_max_attempts']} |",
            f"| Queued items at or over max attempts | {attempts['queued_items_at_or_over_max_attempts']} |",
            "",
            "## Oldest Queued Item",
            "",
        ]
    )

    oldest = report["oldest_queued"]
    if oldest is None:
        lines.append("No queued items found.")
    else:
        lines.append(
            "`{id}` has been queued for {age_hours}h since `{enqueued_at}`.".format(
                id=_escape_inline(str(oldest["id"])),
                age_hours=_format_float(oldest["age_hours"]),
                enqueued_at=oldest["enqueued_at"],
            )
        )

    lines.extend(
        [
            "",
            "## Top Queued Candidates",
            "",
            "| Rank | Id | Policy | Score | Risk | p | Et | Wait h | KEV | Attempts |",
            "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )

    top_queued = report["top_queued"]
    if top_queued:
        for index, item in enumerate(top_queued, start=1):
            lines.append(
                "| {rank} | `{id}` | {policy} | {score} | {risk} | {probability} | "
                "{expected_time} | {wait} | {kev} | {attempts}/{max_attempts} |".format(
                    rank=index,
                    id=_escape_inline_table(str(item["id"])),
                    policy=_escape_table(str(item["policy_id"])),
                    score=_format_float(item["score"]),
                    risk=_format_float(item["risk"]),
                    probability=_format_float(item["probability"]),
                    expected_time=_format_float(item["expected_time"]),
                    wait=_format_float(item["wait_hours"]),
                    kev="yes" if item["kev"] else "no",
                    attempts=item["attempts"],
                    max_attempts=item["max_attempts"],
                )
            )
    else:
        lines.append("|  | No queued candidates |  |  |  |  |  |  |  |  |")

    return "\n".join(lines) + "\n"


def _load_items_read_only(db_path: Path) -> List[sqlite3.Row]:
    if not db_path.exists():
        raise ValueError(f"database not found: {db_path}")
    if not db_path.is_file():
        raise ValueError(f"database path is not a file: {db_path}")

    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"failed to open database read-only: {db_path}: {exc}") from exc

    conn.row_factory = sqlite3.Row
    try:
        _validate_schema(conn)
        return list(
            conn.execute(
                """
                SELECT id, policy_id, state, attempts, max_attempts, enqueued_at,
                       risk, probability, expected_time, kev
                FROM items
                """
            )
        )
    except sqlite3.Error as exc:
        raise ValueError(f"failed to read queue items from {db_path}: {exc}") from exc
    finally:
        conn.close()


def _validate_schema(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
    ).fetchone()
    if table is None:
        raise ValueError("missing required table: items")

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}
    missing = sorted(REQUIRED_COLUMNS - columns)
    if missing:
        raise ValueError(f"items table missing required column(s): {', '.join(missing)}")


def _state_counts(rows: Sequence[sqlite3.Row]) -> Counter[str]:
    return Counter(_state(row) for row in rows)


def _attempt_signals(rows: Sequence[sqlite3.Row]) -> Dict[str, int]:
    items_with_attempts = 0
    items_one_attempt_from_max = 0
    items_at_or_over_max_attempts = 0
    queued_items_at_or_over_max_attempts = 0

    for row in rows:
        attempts = _int_value(row, "attempts")
        max_attempts = _int_value(row, "max_attempts")
        remaining = max_attempts - attempts
        at_or_over = attempts >= max_attempts

        if attempts > 0:
            items_with_attempts += 1
        if remaining == 1:
            items_one_attempt_from_max += 1
        if at_or_over:
            items_at_or_over_max_attempts += 1
            if _state(row) == "queued":
                queued_items_at_or_over_max_attempts += 1

    return {
        "items_with_attempts": items_with_attempts,
        "items_one_attempt_from_max": items_one_attempt_from_max,
        "items_at_or_over_max_attempts": items_at_or_over_max_attempts,
        "queued_items_at_or_over_max_attempts": queued_items_at_or_over_max_attempts,
    }


def _oldest_queued(rows: Sequence[sqlite3.Row], *, now: float) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    oldest = min(rows, key=lambda row: _float_value(row, "enqueued_at"))
    age_seconds = _age_seconds(now, _float_value(oldest, "enqueued_at"))
    return {
        "id": _text_value(oldest, "id"),
        "policy_id": _text_value(oldest, "policy_id"),
        "enqueued_at": _format_epoch(_float_value(oldest, "enqueued_at")),
        "age_seconds": round(age_seconds, 3),
        "age_hours": round(age_seconds / 3600.0, 4),
    }


def _top_queued(
    rows: Sequence[sqlite3.Row],
    *,
    now: float,
    top: int,
    alpha: float,
    epsilon: float,
    kev_weight: float,
) -> List[Dict[str, Any]]:
    candidates: List[PatchCandidate] = []
    by_id: Dict[str, sqlite3.Row] = {}
    for row in rows:
        item_id = _text_value(row, "id")
        wait_hours = _age_seconds(now, _float_value(row, "enqueued_at")) / 3600.0
        candidates.append(
            PatchCandidate(
                id=item_id,
                risk=_float_value(row, "risk"),
                probability=_float_value(row, "probability"),
                expected_time=_float_value(row, "expected_time"),
                wait=wait_hours,
                kev=bool(_int_value(row, "kev")),
                explore=0.0,
            )
        )
        by_id[item_id] = row

    ordered = schedule_patches(
        candidates,
        alpha=alpha,
        epsilon=epsilon,
        kev_weight=kev_weight,
    )

    top_items: List[Dict[str, Any]] = []
    for candidate in ordered[:top]:
        row = by_id[candidate.id]
        score = candidate.score(alpha=alpha, epsilon=epsilon, kev_weight=kev_weight)
        top_items.append(
            {
                "id": candidate.id,
                "policy_id": _text_value(row, "policy_id"),
                "score": round(score, 6),
                "risk": candidate.risk,
                "probability": candidate.probability,
                "expected_time": candidate.expected_time,
                "wait_hours": round(candidate.wait, 4),
                "kev": candidate.kev,
                "attempts": _int_value(row, "attempts"),
                "max_attempts": _int_value(row, "max_attempts"),
                "enqueued_at": _format_epoch(_float_value(row, "enqueued_at")),
            }
        )
    return top_items


def _state(row: sqlite3.Row) -> str:
    value = row["state"]
    if value is None or str(value) == "":
        return "(missing)"
    return str(value)


def _text_value(row: sqlite3.Row, field: str) -> str:
    value = row[field]
    if value is None:
        return ""
    return str(value)


def _int_value(row: sqlite3.Row, field: str) -> int:
    value = row[field]
    if value is None:
        raise ValueError(f"items.{field} is NULL for id={_text_value(row, 'id')}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"items.{field} must be an integer for id={_text_value(row, 'id')}"
        ) from exc


def _float_value(row: sqlite3.Row, field: str) -> float:
    value = row[field]
    if value is None:
        raise ValueError(f"items.{field} is NULL for id={_text_value(row, 'id')}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"items.{field} must be numeric for id={_text_value(row, 'id')}"
        ) from exc


def _age_seconds(now: float, enqueued_at: float) -> float:
    return max(0.0, now - enqueued_at)


def _format_epoch(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _format_float(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def _escape_inline(value: str) -> str:
    return value.replace("`", "\\`")


def _escape_inline_table(value: str) -> str:
    return _escape_table(_escape_inline(value))


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
        report = build_report(
            args.db,
            top=args.top,
            alpha=args.alpha,
            epsilon=args.epsilon,
            kev_weight=args.kev_weight,
        )
        if args.json_output:
            json.dump(report, stdout, indent=2)
            stdout.write("\n")
        else:
            stdout.write(render_markdown(report))
        return 0
    except ValueError as exc:
        stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
