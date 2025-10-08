#!/usr/bin/env python3
"""
Summarise verifier outcomes for large batch runs.

Example:
    python scripts/summarize_failures.py \
        --verified-glob "data/batch_runs/grok_5k/verified_grok5k_batch_*.json" \
        --detections-glob "data/batch_runs/grok_5k/detections_grok5k_batch_*.json"
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Tuple


def load_json_records(glob: str) -> Iterable[Tuple[dict, Path]]:
    for path in sorted(Path().glob(glob)):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse {path}") from exc
        if not isinstance(payload, list):
            raise ValueError(f"Expected list in {path}, got {type(payload).__name__}")
        for entry in payload:
            yield entry, path


def load_detection_index(glob: str) -> Dict[str, dict]:
    index: Dict[str, dict] = {}
    for record, path in load_json_records(glob):
        key = record.get("id")
        if not key:
            raise ValueError(f"Detection in {path} missing 'id'")
        index[key] = record
    return index


def human_percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{numerator / denominator:.1%}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise verifier failures by reason, policy, and manifest."
    )
    parser.add_argument(
        "--verified-glob",
        type=str,
        required=True,
        help="Glob pattern for verified JSON files (e.g., data/batch_runs/.../verified_*.json).",
    )
    parser.add_argument(
        "--detections-glob",
        type=str,
        default=None,
        help="Optional glob for detections to map ids to manifests/policies.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top failure reasons to display (default: 10).",
    )
    args = parser.parse_args()

    detection_index: Dict[str, dict] = {}
    if args.detections_glob:
        detection_index = load_detection_index(args.detections_glob)

    total = 0
    accepted = 0
    failures_by_reason: Counter[str] = Counter()
    failures_by_policy: Counter[str] = Counter()
    failures_by_manifest: Counter[str] = Counter()
    kubectl_details: Counter[str] = Counter()
    policy_success: Counter[str] = Counter()

    for record, path in load_json_records(args.verified_glob):
        total += 1
        policy_id = record.get("policy_id", "unknown")
        entry_id = record.get("id", "unknown")
        manifest_path = None
        if entry_id in detection_index:
            manifest_path = detection_index[entry_id].get("manifest_path")
            policy_id = detection_index[entry_id].get("policy_id", policy_id)

        if record.get("accepted"):
            accepted += 1
            policy_success[policy_id] += 1
            continue

        errors = record.get("errors") or ["<missing error>"]
        for error in errors:
            reason_key = error.split(":", 1)[0].strip()
            failures_by_reason[reason_key] += 1
            if reason_key == "kubectl dry-run failed" and ":" in error:
                detail = error.split(":", 1)[1].strip()
                if detail:
                    kubectl_details[detail] += 1
            failures_by_policy[policy_id] += 1
            if manifest_path:
                failures_by_manifest[manifest_path] += 1

    rejected = total - accepted

    print(f"Verified entries  : {total}")
    print(f"Accepted           : {accepted} ({human_percent(accepted, total)})")
    print(f"Rejected           : {rejected} ({human_percent(rejected, total)})")
    print()

    if rejected:
        print(f"Top {args.top} failure reasons:")
        for reason, count in failures_by_reason.most_common(args.top):
            print(f"  - {reason}: {count} ({human_percent(count, rejected)})")
        print()

        if kubectl_details:
            print("Kubectl dry-run failure details:")
            for detail, count in kubectl_details.most_common(args.top):
                print(f"  - {detail}: {count}")
            print()

        print("Failures by policy:")
        for policy, count in failures_by_policy.most_common():
            total_for_policy = policy_success[policy] + count
            percent = human_percent(total_for_policy - count, total_for_policy)
            print(f"  - {policy}: {count} fails out of {total_for_policy} ({percent} acceptance)")
        print()

        if failures_by_manifest:
            print("Noisiest manifests (failures):")
            for manifest, count in failures_by_manifest.most_common(args.top):
                print(f"  - {manifest}: {count}")
            print()

    print("Successes by policy:")
    combined = defaultdict(lambda: {"success": 0, "total": 0})
    for policy, succ in policy_success.items():
        combined[policy]["success"] += succ
        combined[policy]["total"] += succ
    for policy, fail in failures_by_policy.items():
        combined[policy]["total"] += fail

    for policy, stats in sorted(combined.items(), key=lambda kv: kv[1]["total"], reverse=True):
        total_for_policy = stats["total"]
        rate = human_percent(stats["success"], total_for_policy)
        print(f"  - {policy}: {stats['success']}/{total_for_policy} accepted ({rate})")


if __name__ == "__main__":  # pragma: no cover
    main()
