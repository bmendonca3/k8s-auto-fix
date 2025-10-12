from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from .schedule import EPSILON, PatchCandidate, schedule_patches
from src.common.policy_ids import normalise_policy_id

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
    risk: Optional[Path] = typer.Option(
        Path("data/risk.json"),
        "--risk",
        help="Optional risk store JSON; if present, overrides default metrics per id.",
    ),
    policy_metrics: Optional[Path] = typer.Option(
        Path("data/policy_metrics.json"),
        "--policy-metrics",
        help="Optional policy-level probability/expected_time metrics.",
    ),
    alpha: float = typer.Option(
        1.0,
        help="Weight applied to wait time in score.",
    ),
    epsilon: float = typer.Option(
        EPSILON,
        help="Lower bound used for expected time denominator.",
    ),
    kev_weight: float = typer.Option(
        1.0,
        help="Additional priority added when a candidate is KEV-listed.",
    ),
    explore_weight: float = typer.Option(
        1.0,
        help="Weight applied to the exploration bonus when computing scores.",
    ),
) -> None:
    verified_records = _load_array(verified, "verified")
    detection_map = _load_detection_policies(detections)
    risk_map = _load_risk_map(risk) if risk else {}
    policy_metrics_map = _load_policy_metrics(policy_metrics) if policy_metrics else {}

    candidates: List[PatchCandidate] = []
    for record in verified_records:
        if not isinstance(record, dict):
            continue
        if not record.get("accepted", False):
            continue
        patch_id = str(record.get("id"))
        policy_id = detection_map.get(patch_id, {}).get("policy_id")
        metrics = _compute_metrics(patch_id, policy_id, risk_map, policy_metrics_map)
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

    ordered = schedule_patches(
        candidates,
        alpha=alpha,
        epsilon=epsilon,
        kev_weight=kev_weight,
        explore_weight=explore_weight,
    )
    output = [
        candidate.to_output(alpha=alpha, epsilon=epsilon, kev_weight=kev_weight, explore_weight=explore_weight)
        for candidate in ordered
    ]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    typer.echo(f"Scheduled {len(output)} patch(es) to {out.resolve()}")


def _open_json(path: Path):
    if path.exists():
        return path.open("r", encoding="utf-8")
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt", encoding="utf-8")
    raise FileNotFoundError(path)


def _load_array(path: Path, kind: str) -> List[Any]:
    try:
        with _open_json(path) as handle:
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
            "policy_id": normalise_policy_id(record.get("policy_id")),
        }
    return mapping


def _load_risk_map(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    try:
        with _open_json(path) as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            _id = str(entry.get("id"))
            if not _id:
                continue
            result[_id] = {
                "risk": float(entry.get("risk", 0.0)),
                "probability": float(entry.get("probability", 0.0)),
                "expected_time": float(entry.get("expected_time", 0.0)),
                "wait": float(entry.get("wait", 0.0)),
                "kev": bool(entry.get("kev", False)),
                "explore": float(entry.get("explore", 0.0)),
            }
    elif isinstance(data, dict):
        for _id, entry in data.items():
            if not isinstance(entry, dict):
                continue
            result[str(_id)] = {
                "risk": float(entry.get("risk", 0.0)),
                "probability": float(entry.get("probability", 0.0)),
                "expected_time": float(entry.get("expected_time", 0.0)),
                "wait": float(entry.get("wait", 0.0)),
                "kev": bool(entry.get("kev", False)),
                "explore": float(entry.get("explore", 0.0)),
            }
    return result


def _compute_metrics(
    patch_id: str,
    policy_id: Any,
    risk_map: Dict[str, Dict[str, Any]],
    policy_metrics_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    if patch_id in risk_map:
        return risk_map[patch_id]
    policy = normalise_policy_id(policy_id)
    if policy in policy_metrics_map:
        metrics = policy_metrics_map[policy]
        return {
            "risk": metrics.get("risk", _default_risk(policy)),
            "probability": metrics.get("probability", 0.9),
            "expected_time": metrics.get("expected_time", 10.0),
            "wait": metrics.get("wait", 0.0),
            "kev": metrics.get("kev", policy in {"no_privileged", "drop_capabilities", "drop_cap_sys_admin"}),
            "explore": metrics.get("explore", 0.0),
        }
    risk_lookup = {
        "no_privileged": 85.0,
        "no_latest_tag": 50.0,
        "run_as_non_root": 70.0,
        "no_host_path": 80.0,
        "no_host_ports": 65.0,
        "run_as_user": 72.0,
        "enforce_seccomp": 75.0,
        "drop_capabilities": 85.0,
        "drop_cap_sys_admin": 85.0,
        "env_var_secret": 78.0,
        "liveness_port": 45.0,
        "readiness_port": 50.0,
        "startup_port": 35.0,
    }
    base_risk = risk_lookup.get(policy, 40.0)
    kev_flag = policy in {"no_privileged", "drop_capabilities", "drop_cap_sys_admin"}
    return {
        "risk": base_risk,
        "probability": 0.9,
        "expected_time": 10.0,
        "wait": 0.0,
        "kev": kev_flag,
        "explore": 0.0,
    }


def _default_risk(policy: str) -> float:
    return {
        "no_privileged": 85.0,
        "drop_capabilities": 85.0,
        "drop_cap_sys_admin": 85.0,
        "no_latest_tag": 50.0,
        "run_as_non_root": 70.0,
    }.get(policy, 40.0)


def _load_policy_metrics(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if not path or not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for policy, entry in data.items():
        if not isinstance(entry, dict):
            continue
        result[str(normalise_policy_id(policy))] = {
            "risk": float(entry.get("risk", _default_risk(policy))),
            "probability": float(entry.get("probability", 0.9)),
            "expected_time": float(entry.get("expected_time", 10.0)),
            "wait": float(entry.get("wait", 0.0)),
            "kev": bool(entry.get("kev", normalise_policy_id(policy) in {"no_privileged", "drop_capabilities", "drop_cap_sys_admin"})),
            "explore": float(entry.get("explore", 0.0)),
        }
    return result


if __name__ == "__main__":  # pragma: no cover
    app()
