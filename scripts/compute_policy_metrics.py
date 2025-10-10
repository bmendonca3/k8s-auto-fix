#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from src.common.policy_ids import normalise_policy_id

DEFAULT_RISK = {
    "no_privileged": 85.0,
    "drop_capabilities": 85.0,
    "drop_cap_sys_admin": 85.0,
    "no_latest_tag": 50.0,
    "run_as_non_root": 70.0,
}


def load_json_array(path: Path) -> List[Dict[str, object]]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - CLI guard
        raise SystemExit(f"File not found: {path}") from exc
    if not isinstance(data, list):  # pragma: no cover - CLI guard
        raise SystemExit(f"Expected JSON array in {path}")
    return data


def compute_metrics(patches_path: Path, verified_path: Path, out_path: Path) -> None:
    patch_records = load_json_array(patches_path)
    verified_records = load_json_array(verified_path)

    patch_map: Dict[str, Dict[str, object]] = {}
    for item in patch_records:
        if not isinstance(item, dict):
            continue
        patch_id = str(item.get("id"))
        if patch_id:
            patch_map[patch_id] = item

    totals = defaultdict(int)
    accepts = defaultdict(int)
    latency_samples = defaultdict(list)

    for item in verified_records:
        if not isinstance(item, dict):
            continue
        patch_id = str(item.get("id"))
        policy = normalise_policy_id(item.get("policy_id"))
        if not policy:
            continue
        totals[policy] += 1
        if item.get("accepted"):
            accepts[policy] += 1
        proposer_latency = None
        if patch_id in patch_map:
            proposer_latency = patch_map[patch_id].get("total_latency_ms")
        verifier_latency = item.get("latency_ms")
        if isinstance(proposer_latency, (int, float)) and isinstance(verifier_latency, (int, float)):
            latency_samples[policy].append((float(proposer_latency) + float(verifier_latency)) / 1000.0)

    output: Dict[str, Dict[str, float]] = {}
    for policy, total in totals.items():
        probability = accepts[policy] / total if total else 0.0
        samples = latency_samples.get(policy, [])
        expected_time = statistics.mean(samples) if samples else 10.0
        output[policy] = {
            "risk": DEFAULT_RISK.get(policy, 40.0),
            "probability": round(probability, 4),
            "expected_time": round(expected_time, 4),
            "wait": 0.0,
            "kev": policy in {"no_privileged", "drop_capabilities", "drop_cap_sys_admin"},
            "explore": 0.0,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute policy-level probability/time metrics from proposer & verifier telemetry.")
    parser.add_argument("--patches", type=Path, required=True, help="Path to patches JSON (with latency metadata).")
    parser.add_argument("--verified", type=Path, required=True, help="Path to verified JSON (with latency metadata).")
    parser.add_argument("--out", type=Path, default=Path("data/policy_metrics.json"), help="Output path for aggregated metrics.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    compute_metrics(args.patches, args.verified, args.out)


if __name__ == "__main__":  # pragma: no cover
    main()
