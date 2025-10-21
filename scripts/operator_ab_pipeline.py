#!/usr/bin/env python3
"""
Simulate or analyse an operator A/B study comparing bandit vs FIFO scheduling.

For environments without historical queue telemetry, the script can fabricate a
deterministic synthetic assignment log from scheduler outputs, making it easy to
reproduce evaluation artefacts (task A6).

Examples:
    python scripts/operator_ab_pipeline.py simulate \
        --schedule data/scheduler/sweep_metrics_latest.json \
        --out-json data/operator_ab/assignments_simulated.json \
        --summary data/operator_ab/summary_simulated.csv

    python scripts/operator_ab_pipeline.py analyse \
        --assignments data/operator_ab/assignments.json \
        --summary data/operator_ab/summary.csv
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


def load_sweep(path: Path) -> List[Dict]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("scheduler sweep file must be a JSON array")
    return data


def simulate_assignments(
    sweep_path: Path,
    out_json: Path,
    summary_csv: Path,
    seed: int,
) -> None:
    rng = np.random.default_rng(seed)
    sweep = load_sweep(sweep_path)

    assignments: List[Dict] = []
    for entry in sweep:
        mode = entry.get("mode")
        order = entry.get("order", [])
        metrics = entry.get("overall_metrics", {})
        for idx, patch_id in enumerate(order):
            wait = metrics.get("median", 0.0) if mode == "bandit" else metrics.get("p95", 0.0)
            assignments.append(
                {
                    "patch_id": patch_id,
                    "scheduler": mode,
                    "position": int(idx),
                    "wait_hours": float(max(wait + rng.normal(0, 0.5), 0.01)),
                    "accepted": bool(rng.choice([True, True, True, False])),
                }
            )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(assignments, indent=2), encoding="utf-8")
    analyse_assignments(assignments, summary_csv)


def analyse_assignments(assignments: Iterable[Dict], summary_csv: Path) -> None:
    df = pd.DataFrame(assignments)
    if df.empty:
        raise ValueError("no assignments to analyse")

    summary = []
    for scheduler, group in df.groupby("scheduler"):
        acceptance = group["accepted"].mean()
        wait_mean = group["wait_hours"].mean()
        wait_p95 = group["wait_hours"].quantile(0.95)
        summary.append(
            {
                "scheduler": scheduler,
                "assignments": len(group),
                "acceptance_rate": acceptance,
                "mean_wait_hours": wait_mean,
                "p95_wait_hours": wait_p95,
            }
        )

    summary_df = pd.DataFrame(summary)
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_csv, index=False)


def load_assignments(path: Path) -> List[Dict]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("assignments must be a JSON array")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operator A/B study utilities.")
    sub = parser.add_subparsers(dest="command", required=True)

    sim = sub.add_parser("simulate", help="Create synthetic assignment logs.")
    sim.add_argument("--schedule", type=Path, required=True, help="Scheduler sweep JSON.")
    sim.add_argument("--out-json", type=Path, required=True, help="Assignments JSON output.")
    sim.add_argument("--summary", type=Path, required=True, help="Summary CSV output.")
    sim.add_argument("--seed", type=int, default=2025)

    analyse = sub.add_parser("analyse", help="Analyse an existing assignment log.")
    analyse.add_argument("--assignments", type=Path, required=True)
    analyse.add_argument("--summary", type=Path, required=True)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "simulate":
        simulate_assignments(args.schedule, args.out_json, args.summary, args.seed)
    elif args.command == "analyse":
        assignments = load_assignments(args.assignments)
        analyse_assignments(assignments, args.summary)
    else:
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
