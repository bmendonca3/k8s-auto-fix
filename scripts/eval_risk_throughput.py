#!/usr/bin/env python3
"""
Evaluate scheduler throughput on risk-weighted closure rates.

Computes KEV-weighted and severity-weighted risk closed per wall-clock hour for
two orderings: FIFO and the risk-aware scheduler output.

Inputs:
- verified JSON (accepted patches with timestamps or estimated durations)
- detections JSON (policy ids)
- risk JSON (per-id risk metrics with KEV flags)

Outputs:
- data/metrics_risk_throughput.json with summary statistics and sensitivity
  analysis over alternate policy weight maps.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Risk throughput evaluation")
    p.add_argument("--verified", type=Path, default=Path("data/verified.json"))
    p.add_argument("--detections", type=Path, default=Path("data/detections.json"))
    p.add_argument("--risk", type=Path, default=Path("data/risk.json"))
    p.add_argument("--out", type=Path, default=Path("data/metrics_risk_throughput.json"))
    return p.parse_args()


def load_json_array(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [x for x in data if isinstance(x, dict)]


def index_by_id(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in records:
        rid = str(r.get("id") or r.get("patch_id") or r.get("detection_id") or "").strip()
        if rid:
            out[rid] = r
    return out


def build_policy_weights() -> List[Dict[str, float]]:
    # Three maps for sensitivity: baseline, severity-tilted, and flat
    baseline = {
        "run_as_non_root": 70.0,
        "read_only_root_fs": 60.0,
        "drop_capabilities": 65.0,
        "drop_cap_sys_admin": 75.0,
        "set_requests_limits": 40.0,
        "enforce_seccomp": 55.0,
        "no_host_path": 80.0,
        "no_host_ports": 45.0,
    }
    severity_tilted = {k: (v * 1.2 if v >= 60.0 else v * 0.9) for k, v in baseline.items()}
    flat = {k: 50.0 for k in baseline}
    return [baseline, severity_tilted, flat]


def kev_bonus(entry: Dict[str, Any]) -> float:
    return 10.0 if bool(entry.get("kev")) else 0.0


def compute_throughput(
    verified: List[Dict[str, Any]],
    detections: Dict[str, Dict[str, Any]],
    risk_map: Dict[str, Dict[str, Any]],
    weights: Dict[str, float],
) -> Dict[str, Any]:
    fifo_order = list(verified)
    sched_order = sorted(verified, key=lambda x: float(risk_map.get(str(x.get("id")), {}).get("risk", 0.0)), reverse=True)

    def score(order: List[Dict[str, Any]]) -> Tuple[float, float, int]:
        t = 0.0
        kev_closed = 0
        risk_closed = 0.0
        for entry in order:
            rid = str(entry.get("id"))
            pol = str(detections.get(rid, {}).get("policy_id") or "").lower()
            per_item_time = float(entry.get("verify_latency_ms") or entry.get("latency_ms") or 1000.0) / 1000.0
            # 1 second floor to avoid zero-time
            per_item_time = max(per_item_time, 1.0)
            t += per_item_time
            base = float(weights.get(pol, 40.0))
            metrics = risk_map.get(rid, {})
            risk = base + kev_bonus(metrics)
            risk_closed += risk
            if bool(metrics.get("kev")):
                kev_closed += 1
        hours = max(t / 3600.0, 1e-6)
        return (risk_closed / hours, kev_closed / hours, len(order))

    risk_per_hour_fifo, kev_per_hour_fifo, n_fifo = score(fifo_order)
    risk_per_hour_sched, kev_per_hour_sched, n_sched = score(sched_order)
    return {
        "n": n_fifo,
        "risk_per_hour_fifo": risk_per_hour_fifo,
        "risk_per_hour_sched": risk_per_hour_sched,
        "kev_per_hour_fifo": kev_per_hour_fifo,
        "kev_per_hour_sched": kev_per_hour_sched,
        "improvement_factor_risk": (risk_per_hour_sched / risk_per_hour_fifo) if risk_per_hour_fifo else None,
        "improvement_factor_kev": (kev_per_hour_sched / kev_per_hour_fifo) if kev_per_hour_fifo else None,
    }


def main() -> None:
    args = parse_args()
    verified = load_json_array(args.verified)
    det_list = load_json_array(args.detections)
    risk_list = load_json_array(args.risk)
    det_index = index_by_id(det_list)
    risk_index = index_by_id(risk_list)

    results: List[Dict[str, Any]] = []
    for weight_map in build_policy_weights():
        res = compute_throughput(verified, det_index, risk_index, weight_map)
        res["weights"] = weight_map
        results.append(res)
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

