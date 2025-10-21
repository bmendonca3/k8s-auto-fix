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

app = typer.Typer(help="Compute precision/recall/F1 (with optional CIs) for detector outputs.")


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


def _compute_metrics(label_map: Dict[str, Set[str]], per_manifest_pred: Dict[str, Set[str]]):
    """Compute global and per-policy counts and metrics (no CI)."""

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
    supports: Dict[str, int] = {}
    for policy, counts in per_policy_counts.items():
        ptp, pfp, pfn = counts["tp"], counts["fp"], counts["fn"]
        support = ptp + pfn  # number of ground-truth positives for this policy
        supports[policy] = support
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
            "support": support,
        }

    # Macro and weighted (by support) averages
    if per_policy_metrics:
        macro_p = sum(m["precision"] for m in per_policy_metrics.values()) / len(per_policy_metrics)
        macro_r = sum(m["recall"] for m in per_policy_metrics.values()) / len(per_policy_metrics)
        macro_f1 = sum(m["f1"] for m in per_policy_metrics.values()) / len(per_policy_metrics)
        total_support = sum(supports.values()) or 1
        weighted_f1 = sum(per_policy_metrics[p]["f1"] * (supports[p] / total_support) for p in per_policy_metrics)
    else:
        macro_p = macro_r = macro_f1 = weighted_f1 = 0.0

    metrics = {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "macro_precision": round(macro_p, 3),
        "macro_recall": round(macro_r, 3),
        "macro_f1": round(macro_f1, 3),
        "weighted_f1": round(weighted_f1, 3),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "per_policy": per_policy_metrics,
    }
    return metrics


def _bootstrap_cis(label_map: Dict[str, Set[str]], per_manifest_pred: Dict[str, Set[str]],
                   n: int, alpha: float) -> Dict[str, Dict[str, float]]:
    import random
    manifests = list(label_map.keys())
    if not manifests or n <= 0:
        return {}
    stats = {"precision": [], "recall": [], "f1": [], "macro_f1": [], "weighted_f1": []}
    for _ in range(n):
        sample = [random.choice(manifests) for _ in manifests]
        lm = {m: label_map[m] for m in sample}
        pm = {m: per_manifest_pred.get(m, set()) for m in sample}
        m = _compute_metrics(lm, pm)
        for k in stats:
            stats[k].append(m.get(k, 0.0))
    def q(vals, q):
        vals = sorted(vals)
        idx = max(0, min(len(vals) - 1, int(q * (len(vals) - 1))))
        return vals[idx]
    lower = alpha / 2
    upper = 1 - alpha / 2
    out = {}
    for k, vals in stats.items():
        if not vals:
            continue
        out[k] = {"low": round(q(vals, lower), 3), "high": round(q(vals, upper), 3)}
    return out


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
    bootstrap: int = typer.Option(0, "--bootstrap", help="Bootstrap samples for CIs (0 to disable)."),
    alpha: float = typer.Option(0.05, "--alpha", help="CI alpha (default 0.05 => 95% CI)."),
) -> None:
    """Compare detector predictions with labelled ground truth. Optionally compute bootstrap CIs."""

    label_map = _load_labels(labels)
    predictions = list(_load_predictions(detections))
    per_manifest_pred: Dict[str, Set[str]] = defaultdict(set)
    for manifest, policy in predictions:
        per_manifest_pred[manifest].add(policy)

    metrics = _compute_metrics(label_map, per_manifest_pred)
    if bootstrap > 0:
        cis = _bootstrap_cis(label_map, per_manifest_pred, bootstrap, alpha)
        metrics["ci"] = cis

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    typer.echo(json.dumps(metrics, indent=2))


if __name__ == "__main__":  # pragma: no cover
    app()
