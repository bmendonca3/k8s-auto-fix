from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import typer

from .schedule import EPSILON, PatchCandidate, schedule_patches

app = typer.Typer(help="Prioritise verified patches using heuristic scoring.")


@app.command()
def schedule(
    verified: Path = typer.Option(
        Path("data/verified.json"),
        "--verified",
        "-v",
        help="Path to verified patches JSON file.",
    ),
    out: Path = typer.Option(
        Path("data/schedule.json"),
        "--out",
        "-o",
        help="Where to write prioritised schedule output.",
    ),
    detections: Path = typer.Option(
        Path("data/detections.json"),
        "--detections",
        "-d",
        help="Detections file for policy lookups.",
    ),
    alpha: float = typer.Option(
        1.0,
        help="Weight applied to wait time in score.",
    ),
    epsilon: float = typer.Option(
        EPSILON,
        help="Lower bound used for expected time denominator.",
    ),
) -> None:
    verified_records = _load_array(verified, "verified")
    detection_map = _load_detection_policies(detections)

    candidates: List[PatchCandidate] = []
    for record in verified_records:
        if not isinstance(record, dict):
            continue
        if not record.get("accepted", False):
            continue
        patch_id = str(record.get("id"))
        policy_id = detection_map.get(patch_id, {}).get("policy_id")
        metrics = _compute_metrics(patch_id, policy_id)
        candidates.append(
            PatchCandidate(
                id=patch_id,
                risk=metrics["risk"],
                probability=metrics["probability"],
                expected_time=metrics["expected_time"],
                wait=metrics["wait"],
                kev=metrics["kev"],
                explore=metrics["explore"],
            )
        )

    ordered = schedule_patches(candidates, alpha=alpha, epsilon=epsilon)
    output = [candidate.to_output(alpha=alpha, epsilon=epsilon) for candidate in ordered]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    typer.echo(f"Scheduled {len(output)} patch(es) to {out.resolve()}")


def _load_array(path: Path, kind: str) -> List[Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"{kind.title()} file not found: {path}") from exc
    if not isinstance(data, list):
        raise typer.BadParameter(f"{kind.title()} file must contain a JSON array")
    return data


def _load_detection_policies(path: Path) -> Dict[str, Dict[str, Any]]:
    records = _load_array(path, "detections")
    mapping: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        detection_id = str(record.get("id"))
        mapping[detection_id] = {
            "policy_id": record.get("policy_id"),
        }
    return mapping


def _compute_metrics(patch_id: str, policy_id: Any) -> Dict[str, Any]:
    policy = (policy_id or "").lower()
    risk_lookup = {
        "no_privileged": 80.0,
        "no_latest_tag": 50.0,
    }
    base_risk = risk_lookup.get(policy, 40.0)
    kev_flag = policy == "no_privileged"
    return {
        "risk": base_risk,
        "probability": 0.9,
        "expected_time": 10.0,
        "wait": 0.0,
        "kev": kev_flag,
        "explore": 0.0,
    }


if __name__ == "__main__":  # pragma: no cover
    app()
