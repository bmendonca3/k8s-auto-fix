#!/usr/bin/env python3
"""Evaluate detector precision/recall against a labelled manifest set."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer

from src.common.policy_ids import normalise_policy_id

app = typer.Typer(help="Compute precision/recall/F1 for detector outputs.")


def _load_labels(path: Path) -> Dict[str, Set[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    labels: Dict[str, Set[str]] = {}
    for manifest, policies in data.items():
        labels[str(manifest)] = {normalise_policy_id(policy) for policy in policies}
    return labels


def _load_predictions(path: Path) -> Iterable[Tuple[str, str]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    for record in records:
        manifest = str(record.get("manifest_path"))
        policy = normalise_policy_id(record.get("policy_id"))
        if manifest and policy:
            yield (manifest, policy)


@app.command()
def evaluate(
    detections: Path = typer.Option(..., "--detections", "-d", help="Detector JSON output to score."),
    labels: Path = typer.Option(..., "--labels", "-l", help="Ground truth manifest→policies mapping."),
    out: Path = typer.Option(
        Path("data/eval/detector_metrics.json"),
        "--out",
        "-o",
        help="Where to write aggregated metrics JSON.",
    ),
) -> None:
    """Compare detector predictions with labelled ground truth."""

    label_map = _load_labels(labels)
    predictions = list(_load_predictions(detections))

    per_manifest_pred: Dict[str, Set[str]] = defaultdict(set)
    for manifest, policy in predictions:
        per_manifest_pred[manifest].add(policy)

    tp = 0
    fp = 0
    fn = 0
    per_policy_counts: Dict[str, Counter] = defaultdict(Counter)

    for manifest, expected in label_map.items():
        predicted = per_manifest_pred.get(manifest, set())
        tp_set = predicted & expected
        fp_set = predicted - expected
        fn_set = expected - predicted

        tp += len(tp_set)
        fp += len(fp_set)
        fn += len(fn_set)

        for policy in expected | predicted:
            stats = per_policy_counts[policy]
            if policy in tp_set:
                stats["tp"] += 1
            if policy in fp_set:
                stats["fp"] += 1
            if policy in fn_set:
                stats["fn"] += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0

    per_policy_metrics: Dict[str, Dict[str, float]] = {}
    for policy, counts in per_policy_counts.items():
        ptp, pfp, pfn = counts["tp"], counts["fp"], counts["fn"]
        p_precision = ptp / (ptp + pfp) if ptp + pfp else 0.0
        p_recall = ptp / (ptp + pfn) if ptp + pfn else 0.0
        p_f1 = (2 * p_precision * p_recall / (p_precision + p_recall)) if p_precision + p_recall else 0.0
        per_policy_metrics[policy] = {
            "precision": round(p_precision, 3),
            "recall": round(p_recall, 3),
            "f1": round(p_f1, 3),
            "tp": ptp,
            "fp": pfp,
            "fn": pfn,
        }

    metrics = {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "per_policy": per_policy_metrics,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    typer.echo(json.dumps(metrics, indent=2))


if __name__ == "__main__":  # pragma: no cover
    app()
