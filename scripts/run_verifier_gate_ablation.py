#!/usr/bin/env python3
"""
Run verifier gate ablation experiments.

This script evaluates how acceptance changes when individual verifier gates are
suppressed. It executes a baseline verification pass (all gates enabled) and
then simulates gate removal by relaxing the relevant checks. Aggregate metrics
are written to JSON for downstream analysis (e.g., Table/figure additions in
Section V-D of the paper).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import sys

if __package__ is None or __package__ == "":  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.verifier.cli import _load_array, _load_detections  # type: ignore
from src.verifier.verifier import Verifier, VerificationResult


GateName = str
Scenario = Tuple[str, Tuple[GateName, ...]]

# Default scenarios: baseline + removing each gate independently.
DEFAULT_SCENARIOS: Tuple[Scenario, ...] = (
    ("full", tuple()),
    ("no_policy", ("policy",)),
    ("no_safety", ("safety",)),
    ("no_schema", ("kubectl",)),
    ("no_rescan", ("rescan",)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run verifier gate ablation metrics.")
    parser.add_argument(
        "--patches",
        type=Path,
        default=Path("data/patches.json"),
        help="Path to patches JSON (default: data/patches.json).",
    )
    parser.add_argument(
        "--detections",
        type=Path,
        default=Path("data/detections.json"),
        help="Path to detections JSON (default: data/detections.json).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/ablation/verifier_gate_metrics.json"),
        help="Output JSON path for aggregate metrics.",
    )
    parser.add_argument(
        "--kubectl-cmd",
        default="kubectl",
        help="kubectl binary to use for dry-run validation.",
    )
    parser.add_argument(
        "--require-kubectl",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Require kubectl success for schema gate (default: False).",
    )
    parser.add_argument(
        "--enable-rescan",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Enable detector re-scan (kube-linter/Kyverno) during verification.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=None,
        help=(
            "Optional scenario override in the form name:gate1,gate2 "
            "(use empty gate list to represent baseline)."
        ),
    )
    parser.add_argument(
        "--details",
        type=Path,
        default=None,
        help="Optional path to write per-patch detail records.",
    )
    return parser.parse_args()


def _parse_custom_scenarios(raw: Optional[Sequence[str]]) -> Tuple[Scenario, ...]:
    if not raw:
        return DEFAULT_SCENARIOS
    scenarios: List[Scenario] = []
    for entry in raw:
        if ":" in entry:
            name, gate_str = entry.split(":", 1)
            gates = tuple(filter(bool, (gate.strip() for gate in gate_str.split(","))))
        else:
            name, gates = entry, tuple()
        scenarios.append((name.strip(), gates))
    return tuple(scenarios)


def _load_patches(path: Path) -> List[Dict[str, Any]]:
    data = _load_array(path, "patches")
    patches: List[Dict[str, Any]] = []
    for record in data:
        if isinstance(record, dict):
            patches.append(record)
    return patches


def _evaluate_baseline(
    patches: Iterable[Mapping[str, Any]],
    detection_map: Mapping[str, Mapping[str, Any]],
    *,
    kubectl_cmd: str,
    require_kubectl: bool,
    enable_rescan: bool,
) -> Dict[str, VerificationResult]:
    verifier = Verifier(
        kubectl_cmd=kubectl_cmd,
        require_kubectl=require_kubectl,
        enable_rescan=enable_rescan,
    )
    baseline: Dict[str, VerificationResult] = {}
    for record in patches:
        patch_id = str(record.get("id"))
        patch_ops = record.get("patch")
        policy_id = record.get("policy_id")
        detection = detection_map.get(patch_id)
        if detection is None:
            raise ValueError(f"Detection {patch_id} missing from detections file")
        manifest_yaml = detection["manifest_yaml"]
        if not isinstance(policy_id, str):
            raise ValueError(f"Patch {patch_id} missing policy_id")
        if not isinstance(patch_ops, list):
            raise ValueError(f"Patch {patch_id} must be a list of JSON Patch operations")
        result = verifier.verify(manifest_yaml, patch_ops, policy_id)
        baseline[patch_id] = result
    return baseline


def _apply_scenario(result: VerificationResult, disabled: Iterable[GateName]) -> Tuple[bool, Dict[str, bool]]:
    disabled_set = set(disabled)
    gate_states = {
        "policy": result.ok_policy or ("policy" in disabled_set),
        "safety": result.ok_safety or ("safety" in disabled_set),
        "kubectl": result.ok_schema or ("kubectl" in disabled_set),
        "rescan": result.ok_rescan or ("rescan" in disabled_set),
    }
    accepted = all(gate_states.values())
    return accepted, gate_states


def _summarise_gate_failures(results: Mapping[str, VerificationResult]) -> Dict[str, int]:
    counts = {"policy": 0, "safety": 0, "kubectl": 0, "rescan": 0}
    for item in results.values():
        if not item.ok_policy:
            counts["policy"] += 1
        if not item.ok_safety:
            counts["safety"] += 1
        if not item.ok_schema:
            counts["kubectl"] += 1
        if not item.ok_rescan:
            counts["rescan"] += 1
    return counts


def run_ablation(
    baseline_results: Mapping[str, VerificationResult],
    scenarios: Sequence[Scenario],
) -> Dict[str, Any]:
    gate_failures = _summarise_gate_failures(baseline_results)
    total = len(baseline_results)
    baseline_accepts = sum(1 for result in baseline_results.values() if result.accepted)

    per_scenario: List[Dict[str, Any]] = []
    for name, disabled in scenarios:
        accepted = 0
        escaped_ids: List[str] = []  # Cases where scenario accepts but baseline rejected
        gate_state_counts: MutableMapping[str, Dict[str, int]] = {}

        for patch_id, result in baseline_results.items():
            scenario_accept, gate_states = _apply_scenario(result, disabled)
            if scenario_accept:
                accepted += 1
                if not result.accepted:
                    escaped_ids.append(patch_id)
            for gate_name, is_ok in gate_states.items():
                stats = gate_state_counts.setdefault(gate_name, {"passing": 0, "failing": 0})
                key = "passing" if is_ok else "failing"
                stats[key] += 1

        no_new_violations_rate = round(baseline_accepts / total if total else 0.0, 6)
        per_scenario.append(
            {
                "name": name,
                "disabled_gates": list(disabled),
                "total": total,
                "accepted": accepted,
                "acceptance_rate": round(accepted / total if total else 0.0, 6),
                "no_new_violations_rate": no_new_violations_rate,
                "escapes": {
                    "count": len(escaped_ids),
                    "ids": escaped_ids,
                },
                "gate_states": gate_state_counts,
            }
        )

    return {
        "total_patches": total,
        "baseline_accepted": baseline_accepts,
        "baseline_acceptance_rate": round(baseline_accepts / total if total else 0.0, 6),
        "gate_failures": gate_failures,
        "scenarios": per_scenario,
    }


def write_details(path: Path, results: Mapping[str, VerificationResult]) -> None:
    records: List[Dict[str, Any]] = []
    for patch_id, result in results.items():
        records.append(
            {
                "id": patch_id,
                "accepted": result.accepted,
                "ok_policy": result.ok_policy,
                "ok_safety": result.ok_safety,
                "ok_schema": result.ok_schema,
                "ok_rescan": result.ok_rescan,
                "latency_ms": result.latency_ms,
                "kubectl_ms": result.kubectl_ms,
                "errors": result.errors,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    scenarios = _parse_custom_scenarios(args.scenarios)

    patches = _load_patches(args.patches)
    detections = _load_detections(args.detections)

    baseline_results = _evaluate_baseline(
        patches,
        detections,
        kubectl_cmd=args.kubectl_cmd,
        require_kubectl=args.require_kubectl,
        enable_rescan=args.enable_rescan,
    )

    metrics = run_ablation(baseline_results, scenarios)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if args.details:
        write_details(args.details, baseline_results)


if __name__ == "__main__":
    main()
