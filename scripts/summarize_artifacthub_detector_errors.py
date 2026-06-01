#!/usr/bin/env python3
"""Summarize residual detector disagreements on the ArtifactHub structural labels."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common.policy_ids import normalise_policy_id

LABELS = ROOT / "data/eval/artifacthub_sample_labels_structural.json"
DETECTIONS = ROOT / "data/eval/artifacthub_sample_detections.json"
OUT = ROOT / "data/eval/artifacthub_detector_error_summary.json"


def main() -> None:
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    detections = json.loads(DETECTIONS.read_text(encoding="utf-8"))

    predictions: dict[str, set[str]] = defaultdict(set)
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    for record in detections:
        manifest = str(record.get("manifest_path"))
        policy = normalise_policy_id(record.get("policy_id"))
        if not manifest or not policy:
            continue
        predictions[manifest].add(policy)
        text = str(record.get("violation_text") or "")
        if text:
            examples[(manifest, policy)].append(text)

    fp: dict[str, list[dict[str, str]]] = defaultdict(list)
    fn: dict[str, list[str]] = defaultdict(list)
    for manifest in sorted(set(labels) | set(predictions)):
        expected = set(labels.get(manifest, []))
        predicted = set(predictions.get(manifest, []))
        for policy in sorted(predicted - expected):
            fp[policy].append(
                {
                    "manifest": manifest,
                    "example": (examples.get((manifest, policy)) or [""])[0],
                }
            )
        for policy in sorted(expected - predicted):
            fn[policy].append(manifest)

    summary = {
        "false_positive_total": sum(len(v) for v in fp.values()),
        "false_negative_total": sum(len(v) for v in fn.values()),
        "false_positives_by_policy": {
            policy: {"count": len(items), "examples": items[:3]}
            for policy, items in sorted(fp.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        },
        "false_negatives_by_policy": {
            policy: {"count": len(items), "examples": items[:5]}
            for policy, items in sorted(fn.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        },
    }
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
