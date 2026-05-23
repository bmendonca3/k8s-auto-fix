#!/usr/bin/env python3
"""Explain scheduler priority decisions for patch candidates."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional, TextIO


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.scheduler.schedule import EPSILON, PatchCandidate, schedule_patches


REQUIRED_FIELDS = ("id", "risk", "probability", "expected_time")
FORMULA = (
    "score = (risk * probability) / max(expected_time, epsilon) "
    "+ explore_weight * explore + alpha * wait + kev_bonus"
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explain scheduler prioritisation for JSON patch candidates.",
    )
    parser.add_argument(
        "candidates_json",
        nargs="?",
        default="-",
        help="Path to a JSON array of patch candidates, or '-' for stdin (default: -).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print a machine-readable JSON explanation instead of markdown.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Weight applied to wait time in score (default: 1.0).",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=EPSILON,
        help=f"Lower bound used for expected time denominator (default: {EPSILON}).",
    )
    parser.add_argument(
        "--kev-weight",
        type=float,
        default=1.0,
        help="Additional priority added when a candidate is KEV-listed (default: 1.0).",
    )
    parser.add_argument(
        "--explore-weight",
        type=float,
        default=1.0,
        help="Weight applied to exploration bonuses (default: 1.0).",
    )
    return parser.parse_args(argv)


def load_candidates(path_arg: str, *, stdin: TextIO = sys.stdin) -> list[Mapping[str, Any]]:
    try:
        if path_arg == "-":
            source = "stdin"
            data = json.load(stdin)
        else:
            source = path_arg
            with Path(path_arg).open("r", encoding="utf-8") as handle:
                data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse {source}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"failed to read {path_arg}: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"{source} must contain a JSON array of candidate records")

    records: list[Mapping[str, Any]] = []
    for index, record in enumerate(data):
        if not isinstance(record, Mapping):
            raise ValueError(f"{source} record {index} must be a JSON object")
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            raise ValueError(
                f"{source} record {index} missing required field(s): {', '.join(missing)}"
            )
        records.append(record)
    return records


def explain_candidates(
    records: Sequence[Mapping[str, Any]],
    *,
    alpha: float = 1.0,
    epsilon: float = EPSILON,
    kev_weight: float = 1.0,
    explore_weight: float = 1.0,
) -> dict[str, Any]:
    if epsilon <= 0:
        raise ValueError("--epsilon must be greater than 0")

    try:
        ordered = schedule_patches(
            records,
            alpha=alpha,
            epsilon=epsilon,
            kev_weight=kev_weight,
            explore_weight=explore_weight,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid candidate record values: {exc}") from exc

    return {
        "formula": FORMULA,
        "parameters": {
            "alpha": alpha,
            "epsilon": epsilon,
            "kev_weight": kev_weight,
            "explore_weight": explore_weight,
        },
        "candidates": [
            _explain_candidate(
                priority=index + 1,
                candidate=candidate,
                alpha=alpha,
                epsilon=epsilon,
                kev_weight=kev_weight,
                explore_weight=explore_weight,
            )
            for index, candidate in enumerate(ordered)
        ],
    }


def render_markdown(explanation: Mapping[str, Any]) -> str:
    params = explanation["parameters"]
    lines = [
        "# Scheduler Priority Explanation",
        "",
        f"Formula: `{explanation['formula']}`",
        "",
        (
            "Parameters: "
            f"`alpha={_format_float(params['alpha'])}`, "
            f"`epsilon={_format_float(params['epsilon'])}`, "
            f"`kev_weight={_format_float(params['kev_weight'])}`, "
            f"`explore_weight={_format_float(params['explore_weight'])}`"
        ),
        "",
        "| Priority | ID | Score | Risk | Probability | Expected time | Wait | KEV | Explore | Risk/time | Explore bonus | Wait bonus | KEV bonus |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for entry in explanation["candidates"]:
        inputs = entry["inputs"]
        components = entry["components"]
        lines.append(
            " | ".join(
                [
                    f"| {entry['priority']}",
                    _escape_table(str(entry["id"])),
                    _format_float(entry["score"]),
                    _format_float(inputs["risk"]),
                    _format_float(inputs["probability"]),
                    _format_float(inputs["expected_time"]),
                    _format_float(inputs["wait"]),
                    "yes" if inputs["kev"] else "no",
                    _format_float(inputs["explore"]),
                    _format_float(components["risk_probability_over_time"]),
                    _format_float(components["explore_bonus"]),
                    _format_float(components["wait_bonus"]),
                    f"{_format_float(components['kev_bonus'])} |",
                ]
            )
        )

    return "\n".join(lines) + "\n"


def _explain_candidate(
    *,
    priority: int,
    candidate: PatchCandidate,
    alpha: float,
    epsilon: float,
    kev_weight: float,
    explore_weight: float,
) -> dict[str, Any]:
    denominator = max(candidate.expected_time, epsilon)
    risk_probability_over_time = (candidate.risk * candidate.probability) / denominator
    explore_bonus = explore_weight * candidate.explore
    wait_bonus = alpha * candidate.wait
    kev_bonus = kev_weight if candidate.kev else 0.0
    score = candidate.score(
        alpha=alpha,
        epsilon=epsilon,
        kev_weight=kev_weight,
        explore_weight=explore_weight,
    )
    return {
        "priority": priority,
        "id": candidate.id,
        "score": _round_float(score),
        "inputs": {
            "risk": _round_float(candidate.risk),
            "probability": _round_float(candidate.probability),
            "expected_time": _round_float(candidate.expected_time),
            "wait": _round_float(candidate.wait),
            "kev": bool(candidate.kev),
            "explore": _round_float(candidate.explore),
        },
        "components": {
            "expected_time_denominator": _round_float(denominator),
            "risk_probability_over_time": _round_float(risk_probability_over_time),
            "explore_bonus": _round_float(explore_bonus),
            "wait_bonus": _round_float(wait_bonus),
            "kev_bonus": _round_float(kev_bonus),
        },
    }


def _round_float(value: float) -> float:
    return round(float(value), 6)


def _format_float(value: Any) -> str:
    formatted = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = parse_args(argv)
        records = load_candidates(args.candidates_json, stdin=stdin)
        explanation = explain_candidates(
            records,
            alpha=args.alpha,
            epsilon=args.epsilon,
            kev_weight=args.kev_weight,
            explore_weight=args.explore_weight,
        )
        if args.json_output:
            json.dump(explanation, stdout, indent=2)
            stdout.write("\n")
        else:
            stdout.write(render_markdown(explanation))
        return 0
    except ValueError as exc:
        stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
