#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
) -> Tuple[List[PatchCandidate], Dict[str, Dict[str, object]]]:
    verified_records = _load_array(verified_path, "verified")
    detection_records = _load_array(detections_path, "detections")
    detection_map = _load_detection_policies(detections_path)
    risk_map = _load_risk_map(risk_path) if risk_path else {}

    metadata: Dict[str, Dict[str, object]] = {}
    candidates: List[PatchCandidate] = []

    detection_index: Dict[str, int] = {}
    for idx, record in enumerate(detection_records):
        if isinstance(record, dict):
            detection_index[str(record.get("id"))] = idx

    for record in verified_records:
        if not isinstance(record, dict):
            continue
        if not record.get("accepted"):
            continue
        patch_id = str(record.get("id"))
        policy_id = detection_map.get(patch_id, {}).get("policy_id")
        metrics = _compute_metrics(patch_id, policy_id, risk_map, {})
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
            "explore": metrics["explore"],
            "detection_index": detection_index.get(patch_id, len(detection_records)),
        }
    return candidates, metadata


def _compute_waits(order: Sequence[str], metadata: Dict[str, Dict[str, object]]) -> Dict[str, float]:
    waits: Dict[str, float] = {}
    cumulative = 0.0
    for patch_id in order:
        waits[patch_id] = cumulative
        duration = float(metadata.get(patch_id, {}).get("expected_time", 0.0))
        cumulative += duration
    return waits


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    rank = pct / 100.0 * (len(sorted_vals) - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return sorted_vals[lower]
    lower_val = sorted_vals[lower]
    upper_val = sorted_vals[upper]
    weight = rank - lower
    return lower_val + (upper_val - lower_val) * weight


def _assign_band(percentile: float, boundaries: Sequence[float]) -> int:
    for idx, boundary in enumerate(boundaries):
        if percentile <= boundary:
            return idx
    return len(boundaries)


def _summarise_band(wait_hours: Sequence[float]) -> Dict[str, float]:
    if not wait_hours:
        return {"median": 0.0, "p90": 0.0, "p95": 0.0}
    return {
        "median": round(_percentile(wait_hours, 50.0), 4),
        "p90": round(_percentile(wait_hours, 90.0), 4),
        "p95": round(_percentile(wait_hours, 95.0), 4),
    }


def _format_band_names(count: int) -> List[str]:
    labels = ["High", "Mid", "Low"]
    if count <= len(labels):
        return labels[:count]
    # Extend labels for additional bands (e.g., quartiles)
    extra = [f"Band{idx+1}" for idx in range(count - len(labels))]
    return labels + extra


def run_sweep(
    verified_path: Path,
    detections_path: Path,
    risk_path: Optional[Path],
    alpha_values: Sequence[float],
    explore_weights: Sequence[float],
    epsilon: float,
    risk_quantiles: Sequence[float],
) -> List[Dict[str, object]]:
    candidates, metadata = _build_candidates(verified_path, detections_path, risk_path)
    ordered_by_risk = sorted(
        metadata.items(),
        key=lambda item: (-float(item[1].get("risk", 0.0)), item[1].get("detection_index", 0)),
    )
    denom = max(1, len(ordered_by_risk) - 1)
    percentile_map = {
        patch_id: (index / denom if denom else 0.0)
        for index, (patch_id, _meta) in enumerate(ordered_by_risk)
    }
    boundaries = sorted(risk_quantiles)
    band_labels = _format_band_names(len(boundaries) + 1)

    results: List[Dict[str, object]] = []
    for alpha in alpha_values:
        for explore_weight in explore_weights:
            ordered_candidates = schedule_patches(
                candidates,
                alpha=alpha,
                epsilon=epsilon,
                explore_weight=explore_weight,
            )
            ordered_ids = [candidate.id for candidate in ordered_candidates]
            waits_minutes = _compute_waits(ordered_ids, metadata)
            waits_hours = {pid: mins / 60.0 for pid, mins in waits_minutes.items()}

            band_waits: Dict[str, List[float]] = {label: [] for label in band_labels}
            for patch_id in ordered_ids:
                percentile = percentile_map.get(patch_id, 1.0)
                band_index = _assign_band(percentile, boundaries)
                label = band_labels[min(band_index, len(band_labels) - 1)]
                band_waits[label].append(waits_hours.get(patch_id, 0.0))

            band_stats = {label: _summarise_band(values) for label, values in band_waits.items()}
            overall_median = _percentile(list(waits_hours.values()), 50.0) if waits_hours else 0.0
            overall_p90 = _percentile(list(waits_hours.values()), 90.0) if waits_hours else 0.0
            results.append(
                {
                    "alpha": alpha,
                    "explore_weight": explore_weight,
                    "order": ordered_ids,
                    "band_wait_hours": band_stats,
                    "overall_wait_hours": {
                        "median": round(overall_median, 4),
                        "p90": round(overall_p90, 4),
                    },
                }
            )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep scheduler parameters and report fairness metrics.")
    parser.add_argument("--verified", type=Path, required=True, help="Verified JSON path.")
    parser.add_argument("--detections", type=Path, required=True, help="Detections JSON path.")
    parser.add_argument("--risk", type=Path, default=None, help="Optional risk JSON path.")
    parser.add_argument(
        "--alpha-values",
        type=str,
        default="0.0,0.5,1.0,2.0",
        help="Comma-separated alpha values to sweep (default: 0.0,0.5,1.0,2.0).",
    )
    parser.add_argument(
        "--explore-weights",
        type=str,
        default="0.0,1.0",
        help="Comma-separated exploration weights to sweep (default: 0.0,1.0).",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=EPSILON,
        help=f"Epsilon for expected time denominator (default: {EPSILON}).",
    )
    parser.add_argument(
        "--risk-quantiles",
        type=str,
        default="0.25,0.75",
        help="Comma-separated quantiles (0-1, ascending) that define risk band boundaries (default: 0.25,0.75).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/metrics_schedule_sweep.json"),
        help="Output JSON path (default: data/metrics_schedule_sweep.json).",
    )
    return parser.parse_args()


def _parse_floats(value: str) -> List[float]:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return [float(part) for part in parts] if parts else []


def main() -> None:
    args = parse_args()
    alpha_values = _parse_floats(args.alpha_values)
    explore_weights = _parse_floats(args.explore_weights)
    risk_quantiles = _parse_floats(args.risk_quantiles)
    if not alpha_values:
        alpha_values = [1.0]
    if not explore_weights:
        explore_weights = [1.0]
    if not risk_quantiles:
        risk_quantiles = [0.25, 0.75]
    risk_quantiles = sorted({min(1.0, max(0.0, q)) for q in risk_quantiles})

    results = run_sweep(
        verified_path=args.verified,
        detections_path=args.detections,
        risk_path=args.risk,
        alpha_values=alpha_values,
        explore_weights=explore_weights,
        epsilon=args.epsilon,
        risk_quantiles=risk_quantiles,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} sweep entries to {args.out}")


if __name__ == "__main__":
    main()
