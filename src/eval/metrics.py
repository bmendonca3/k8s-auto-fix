from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, List

import typer


def run(
    detections: Path = typer.Option(Path("data/detections.json")),
    patches: Path = typer.Option(Path("data/patches.json")),
    verified: Path = typer.Option(Path("data/verified.json")),
    out: Path = typer.Option(Path("data/metrics.json")),
) -> None:
    det = _load_array(detections)
    pat = _load_array(patches)
    ver = _load_array(verified)

    num_detections = len(det)
    num_verified = len(ver)
    num_patches = len(pat)
    accepted = sum(1 for r in ver if isinstance(r, dict) and r.get("accepted"))
    auto_fix_rate = (accepted / num_detections) if num_detections else 0.0

    # median patch ops for accepted items
    id_to_patch_len = {str(p.get("id")): len(p.get("patch") or []) for p in pat if isinstance(p, dict)}
    accepted_lengths: List[int] = []
    failed_policy = 0
    failed_schema = 0
    failed_safety = 0
    failed_rescan = 0
    for r in ver:
        if not isinstance(r, dict):
            continue
        _id = str(r.get("id"))
        ok_policy = bool(r.get("ok_policy", True))
        ok_schema = bool(r.get("ok_schema", True))
        ok_safety = bool(r.get("ok_safety", True))
        ok_rescan = bool(r.get("ok_rescan", True))
        if not r.get("accepted"):
            if not ok_policy:
                failed_policy += 1
            if not ok_schema:
                failed_schema += 1
            if not ok_safety:
                failed_safety += 1
            if not ok_rescan:
                failed_rescan += 1
        if r.get("accepted") and _id in id_to_patch_len:
            accepted_lengths.append(id_to_patch_len[_id])
    median_ops = statistics.median(accepted_lengths) if accepted_lengths else 0

    metrics = {
        "detections": num_detections,
        "patches": num_patches,
        "verified": num_verified,
        "accepted": accepted,
        "auto_fix_rate": round(auto_fix_rate, 4),
        "median_patch_ops": median_ops,
        "failed_policy": failed_policy,
        "failed_schema": failed_schema,
        "failed_safety": failed_safety,
        "failed_rescan": failed_rescan,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    typer.echo(json.dumps(metrics, indent=2))


def _load_array(path: Path) -> List[Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    if not isinstance(data, list):
        return []
    return data


if __name__ == "__main__":  # pragma: no cover
    typer.run(run)

