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
    for r in ver:
        if not isinstance(r, dict):
            continue
        _id = str(r.get("id"))
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


