#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import sys


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.scheduler.cli import (  # type: ignore
    _compute_metrics,
    _load_array,
    _load_detection_policies,
    _load_risk_map,
    )
from src.scheduler.schedule import PatchCandidate, schedule_patches, EPSILON


def _build_candidates(
    verified_path: Path,
    detections_path: Path,
    risk_path: Optional[Path],
) -> Tuple[List[PatchCandidate], Dict[str, Dict[str, object]], Dict[str, int]]:
    verified_records = _load_array(verified_path, "verified")
    detection_records = _load_array(detections_path, "detections")
    detection_map = _load_detection_policies(detections_path)
    risk_map = _load_risk_map(risk_path) if risk_path else {}

    detection_index: Dict[str, int] = {}
    for idx, record in enumerate(detection_records):
        if isinstance(record, dict):
            detection_index[str(record.get("id"))] = idx

    candidates: List[PatchCandidate] = []
    metadata: Dict[str, Dict[str, object]] = {}

    for record in verified_records:
        if not isinstance(record, dict):
            continue
        if not record.get("accepted"):
            continue
        patch_id = str(record.get("id"))
        policy_id = detection_map.get(patch_id, {}).get("policy_id")
        metrics = _compute_metrics(patch_id, policy_id, risk_map)
        candidate = PatchCandidate(
            id=patch_id,
            risk=metrics["risk"],
            probability=metrics["probability"],
            expected_time=metrics["expected_time"],
            wait=metrics["wait"],
            kev=metrics["kev"],
            explore=metrics["explore"],
        )
        candidates.append(candidate)
        metadata[patch_id] = {
            "risk": metrics["risk"],
            "probability": metrics["probability"],
            "expected_time": metrics["expected_time"],
            "wait": metrics["wait"],
            "kev": metrics["kev"],
            "policy": policy_id,
            "detection_index": detection_index.get(patch_id, len(detection_records)),
        }
    return candidates, metadata, detection_index


def _order_by(
    ids: Sequence[str],
    metadata: Dict[str, Dict[str, object]],
    *,
    key_fn,
) -> List[str]:
    return [
        item[0]
        for item in sorted(
            ((id_, metadata[id_]) for id_ in ids),
            key=lambda pair: key_fn(pair[0], pair[1]),
        )
    ]


def _mean(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _percentile(values: Sequence[int], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    rank = int(math.ceil(pct / 100.0 * len(sorted_vals))) - 1
    rank = max(0, min(rank, len(sorted_vals) - 1))
    return float(sorted_vals[rank])


def _compute_wait_stats(waits_minutes: List[float]) -> Dict[str, float]:
    if not waits_minutes:
        return {
            "mean": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "max": 0.0,
        }
    waits_hours = [value / 60.0 for value in waits_minutes]
    mean_val = statistics.mean(waits_hours)
    median_val = statistics.median(waits_hours)
    p95_val = _percentile_float(waits_hours, 95.0)
    return {
        "mean": round(mean_val, 4),
        "median": round(median_val, 4),
        "p95": round(p95_val, 4),
        "max": round(max(waits_hours), 4),
    }


def _percentile_float(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    rank = int(math.ceil(pct / 100.0 * len(sorted_vals))) - 1
    rank = max(0, min(rank, len(sorted_vals) - 1))
    return float(sorted_vals[rank])


def _compute_telemetry(order: Sequence[str], metadata: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    if not order:
        return {
            "items": 0,
            "total_runtime_hours": 0.0,
            "throughput_per_hour": 0.0,
            "risk_reduction_per_hour": 0.0,
            "wait_hours": {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0},
            "top_risk_wait_hours": {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0},
        }

    waits_minutes: List[float] = []
    cumulative_minutes = 0.0
    total_minutes = 0.0
    risk_resolved = 0.0
    wait_map: Dict[str, float] = {}
    for patch_id in order:
        meta = metadata.get(patch_id, {})
        waits_minutes.append(cumulative_minutes)
        wait_map[patch_id] = cumulative_minutes
        duration = float(meta.get("expected_time", 0.0))
        total_minutes += duration
        cumulative_minutes += duration
        risk = float(meta.get("risk", 0.0))
        probability = float(meta.get("probability", 0.0))
        risk_resolved += risk * probability

    total_hours = total_minutes / 60.0 if total_minutes else 0.0
    throughput_per_hour = (len(order) / total_hours) if total_hours else 0.0
    risk_reduction_per_hour = (risk_resolved / total_hours) if total_hours else 0.0

    wait_stats = _compute_wait_stats(waits_minutes)

    top_n = max(1, len(order) // 10)
    top_risk_ids = sorted(order, key=lambda pid: -float(metadata.get(pid, {}).get("risk", 0.0)))[:top_n]
    top_waits = [wait_map[pid] for pid in top_risk_ids if pid in wait_map]
    top_wait_stats = _compute_wait_stats(top_waits) if top_waits else {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}

    return {
        "items": len(order),
        "total_runtime_hours": round(total_hours, 4),
        "throughput_per_hour": round(throughput_per_hour, 4),
        "risk_reduction_per_hour": round(risk_reduction_per_hour, 4),
        "wait_hours": wait_stats,
        "top_risk_wait_hours": top_wait_stats,
    }


def compare_schedulers(
    verified_path: Path,
    detections_path: Path,
    risk_path: Optional[Path],
    out_path: Optional[Path],
    *,
    alpha: float,
    epsilon: float,
    top_n: int,
) -> Dict[str, object]:
    candidates, metadata, detection_index = _build_candidates(verified_path, detections_path, risk_path)

    baseline_order = [c.id for c in schedule_patches(candidates, alpha=alpha, epsilon=epsilon)]
    fifo_order = _order_by(
        baseline_order,
        metadata,
        key_fn=lambda _id, meta: (meta["detection_index"], _id),
    )
    risk_only_order = _order_by(
        baseline_order,
        metadata,
        key_fn=lambda _id, meta: (-meta["risk"], meta["detection_index"]),
    )

    rank_maps = {
        "baseline": {patch_id: idx + 1 for idx, patch_id in enumerate(baseline_order)},
        "fifo": {patch_id: idx + 1 for idx, patch_id in enumerate(fifo_order)},
        "risk_only": {patch_id: idx + 1 for idx, patch_id in enumerate(risk_only_order)},
    }

    top_candidates = sorted(
        metadata.items(),
        key=lambda item: (-item[1]["risk"], item[1]["detection_index"]),
    )[: min(top_n, len(metadata))]

    top_rankings: List[Dict[str, object]] = []
    for patch_id, meta in top_candidates:
        top_rankings.append(
            {
                "id": patch_id,
                "policy": meta["policy"],
                "risk": meta["risk"],
                "baseline_rank": rank_maps["baseline"][patch_id],
                "fifo_rank": rank_maps["fifo"][patch_id],
                "risk_only_rank": rank_maps["risk_only"][patch_id],
            }
        )

    baseline_scores = [rank_maps["baseline"][item["id"]] for item in top_rankings]
    fifo_scores = [rank_maps["fifo"][item["id"]] for item in top_rankings]
    risk_only_scores = [rank_maps["risk_only"][item["id"]] for item in top_rankings]

    summary = {
        "total_candidates": len(metadata),
        "top_n": len(top_rankings),
        "baseline": {
            "mean_rank_top_n": _mean(baseline_scores),
            "median_rank_top_n": statistics.median(baseline_scores) if baseline_scores else 0,
            "p95_rank_top_n": _percentile(baseline_scores, 95.0),
        },
        "fifo": {
            "mean_rank_top_n": _mean(fifo_scores),
            "median_rank_top_n": statistics.median(fifo_scores) if fifo_scores else 0,
            "p95_rank_top_n": _percentile(fifo_scores, 95.0),
        },
        "risk_only": {
            "mean_rank_top_n": _mean(risk_only_scores),
            "median_rank_top_n": statistics.median(risk_only_scores) if risk_only_scores else 0,
            "p95_rank_top_n": _percentile(risk_only_scores, 95.0),
        },
    }

    result = {
        "summary": summary,
        "orders": {
            "baseline": baseline_order,
            "fifo": fifo_order,
            "risk_only": risk_only_order,
        },
        "top_risk_positions": top_rankings,
    }

    result["telemetry"] = {
        "baseline": _compute_telemetry(baseline_order, metadata),
        "fifo": _compute_telemetry(fifo_order, metadata),
        "risk_only": _compute_telemetry(risk_only_order, metadata),
    }

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare scheduler prioritisation strategies.")
    parser.add_argument(
        "--verified",
        type=Path,
        default=Path("data/verified.json"),
        help="Path to verified JSON (default: data/verified.json).",
    )
    parser.add_argument(
        "--detections",
        type=Path,
        default=Path("data/detections.json"),
        help="Path to detections JSON (default: data/detections.json).",
    )
    parser.add_argument(
        "--risk",
        type=Path,
        default=None,
        help="Optional risk JSON file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write comparison JSON.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Alpha weight for scheduler score (default: 1.0).",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=EPSILON,
        help=f"Epsilon for expected time denominator (default: {EPSILON}).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Top-N high risk items to analyse (default: 50).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = compare_schedulers(
        verified_path=args.verified,
        detections_path=args.detections,
        risk_path=args.risk,
        out_path=args.out,
        alpha=args.alpha,
        epsilon=args.epsilon,
        top_n=args.top_n,
    )
    if args.out is None:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
