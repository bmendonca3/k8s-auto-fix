#!/usr/bin/env python3
"""
Compute risk calibration summaries and ΔR reporting.

Usage example:
    python scripts/risk_calibration.py \
        --risk-map data/policy_metrics.json \
        --dataset supported:data/detections_supported.json:data/verified_rules_supported.json \
        --dataset rules5k:data/detections_supported_5000.json:data/verified_rules_5000.json \
        --summary-out data/risk/risk_calibration.csv \
        --policy-out data/risk/policy_risk_map.json \
        --policy-table-out data/risk/policy_risk_table.csv
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.common.policy_ids import normalise_policy_id  # type: ignore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Risk calibration and ΔR reporting.")
    parser.add_argument(
        "--risk-map",
        type=Path,
        default=Path("data/policy_metrics.json"),
        help="JSON file containing per-policy risk metadata.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        metavar="LABEL:DETECTIONS:VERIFIED",
        help="Dataset specification as label:detections_path:verified_path. "
        "Repeat for each dataset to include.",
        required=True,
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("data/risk/risk_calibration.csv"),
        help="CSV path for dataset-level risk summaries.",
    )
    parser.add_argument(
        "--policy-out",
        type=Path,
        default=Path("data/risk/policy_risk_map.json"),
        help="JSON path for aggregated policy risk metadata.",
    )
    parser.add_argument(
        "--policy-table-out",
        type=Path,
        default=Path("data/risk/policy_risk_table.csv"),
        help="CSV table summarising per-policy counts and risk values.",
    )
    return parser.parse_args()


def load_json(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix == ".gz":
        with gzip.open(path, mode="rt", encoding="utf-8") as fh:
            return json.load(fh)
    with path.open() as fh:
        return json.load(fh)


def iter_datasets(specs: Iterable[str]) -> Iterator[Tuple[str, Path, Path]]:
    for spec in specs:
        parts = spec.split(":")
        if len(parts) != 3:
            raise ValueError(f"Dataset spec must be label:detections:verified, got {spec!r}")
        label, det_path, ver_path = (part.strip() for part in parts)
        if not label:
            raise ValueError(f"Dataset label cannot be empty: {spec!r}")
        yield label, Path(det_path), Path(ver_path)


def normalise_map(risk_map: Mapping[str, Mapping[str, float]]) -> Dict[str, Mapping[str, float]]:
    normalised: Dict[str, Mapping[str, float]] = {}
    for key, value in risk_map.items():
        normalised[normalise_policy_id(key)] = value
    return normalised


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, headers: Sequence[str], rows: Sequence[Sequence]) -> None:
    ensure_dir(path)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()

    risk_map_raw = json.loads(Path(args.risk_map).read_text())
    risk_map = normalise_map(risk_map_raw)

    summary_rows: List[List] = []
    policy_counts_total: Counter = Counter()
    policy_resolved_total: Counter = Counter()
    policy_residual_total: Counter = Counter()

    for label, det_path, ver_path in iter_datasets(args.dataset):
        detections = load_json(det_path)
        verified = load_json(ver_path)

        detection_map: Dict[str, Dict] = {}
        risk_total = 0.0
        time_total = 0.0
        for det in detections:
            det_id = str(det.get("id"))
            policy_raw = det.get("policy_id") or det.get("rule") or ""
            policy_norm = normalise_policy_id(str(policy_raw))
            metrics = risk_map.get(policy_norm, {})
            risk = float(metrics.get("risk", 0.0))
            expected_time = float(metrics.get("expected_time", 0.0))
            detection_map[det_id] = {
                "policy": policy_norm,
                "risk": risk,
                "expected_time": expected_time,
            }
            risk_total += risk
            time_total += expected_time
            policy_counts_total[policy_norm] += 1

        accepted_count = 0
        resolved_risk = 0.0
        resolved_time = 0.0

        for rec in verified:
            det_id = str(rec.get("id"))
            accepted = bool(rec.get("accepted"))
            info = detection_map.get(det_id)
            if info is None:
                continue
            policy = info["policy"]
            if accepted:
                accepted_count += 1
                resolved_risk += info["risk"]
                resolved_time += info["expected_time"]
                policy_resolved_total[policy] += 1
            else:
                policy_residual_total[policy] += 1

        residual_risk = risk_total - resolved_risk
        delta_per_time_unit = (resolved_risk / resolved_time) if resolved_time else 0.0

        summary_rows.append(
            [
                label,
                len(detections),
                accepted_count,
                len(detections) - accepted_count,
                round(risk_total, 4),
                round(resolved_risk, 4),
                round(residual_risk, 4),
                round(resolved_risk / risk_total, 4) if risk_total else 0.0,
                round(delta_per_time_unit, 4),
            ]
        )

    ensure_dir(args.summary_out)
    write_csv(
        args.summary_out,
        [
            "dataset",
            "detections",
            "accepted",
            "rejected",
            "risk_total",
            "risk_resolved",
            "risk_residual",
            "risk_reduction_ratio",
            "delta_r_per_time_unit",
        ],
        summary_rows,
    )

    policy_rows: List[List] = []
    enriched_policy_map: Dict[str, Dict] = {}
    for policy, metrics in sorted(risk_map.items()):
        counts = policy_counts_total.get(policy, 0)
        resolved = policy_resolved_total.get(policy, 0)
        residual = policy_residual_total.get(policy, 0)
        risk = float(metrics.get("risk", 0.0))
        enriched = {
            "policy_id": policy,
            "risk": risk,
            "kev": bool(metrics.get("kev", False)),
            "probability": float(metrics.get("probability", 0.0)),
            "expected_time": float(metrics.get("expected_time", 0.0)),
            "detections": counts,
            "resolved": resolved,
            "residual": residual,
            "resolution_rate": resolved / counts if counts else 0.0,
        }
        enriched_policy_map[policy] = enriched
        policy_rows.append(
            [
                policy,
                risk,
                metrics.get("probability", 0.0),
                metrics.get("expected_time", 0.0),
                int(enriched["kev"]),
                counts,
                resolved,
                residual,
                round(enriched["resolution_rate"], 4),
            ]
        )

    ensure_dir(args.policy_out)
    args.policy_out.write_text(json.dumps(enriched_policy_map, indent=2))

    write_csv(
        args.policy_table_out,
        [
            "policy_id",
            "risk",
            "probability",
            "expected_time",
            "kev",
            "detections",
            "resolved",
            "residual",
            "resolution_rate",
        ],
        policy_rows,
    )


if __name__ == "__main__":
    main()
