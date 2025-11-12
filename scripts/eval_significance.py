#!/usr/bin/env python3
"""
Compute statistical significance for acceptance-rate and latency comparisons.

Usage:
    python scripts/eval_significance.py \
        --counts data/eval/table4_counts.csv \
        --rules-latencies data/batch_runs/verified_rules_100.json \
        --llm-latencies data/batch_runs/verified_grok200.json \
        --output data/eval/significance_tests.json

The script emits JSON containing the test statistics so that the paper can cite
concrete evidence (referenced in Table 4 notes).
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from scipy.stats import mannwhitneyu


def load_latencies(path: Path) -> List[float]:
    """Return verifier latency in milliseconds from a verified manifest log."""
    with path.open() as fh:
        data = json.load(fh)
    latencies = []
    for entry in data:
        latency = entry.get("latency_ms")
        if latency is not None:
            latencies.append(float(latency))
    if not latencies:
        raise ValueError(f"No latency_ms entries found in {path}")
    return latencies


def _proportions_ztest(count1: int, nobs1: int, count2: int, nobs2: int) -> Dict[str, float]:
    """Manual two-proportion z-test (two-sided)."""
    p1 = count1 / nobs1
    p2 = count2 / nobs2
    pooled = (count1 + count2) / (nobs1 + nobs2)
    std = (pooled * (1 - pooled) * (1 / nobs1 + 1 / nobs2)) ** 0.5
    if std == 0:
        return {"z_stat": 0.0, "p_value": 1.0}
    z_stat = (p1 - p2) / std
    # Two-sided p-value assuming normal distribution
    from math import erf, sqrt

    p_value = 2 * (1 - 0.5 * (1 + erf(abs(z_stat) / sqrt(2))))
    return {"z_stat": z_stat, "p_value": p_value}


def compute_acceptance_tests(counts: pd.DataFrame) -> List[Dict[str, float]]:
    """Run pairwise proportion z-tests for acceptance rates."""
    results = []
    for (a_name, b_name) in itertools.combinations(counts["corpus"], 2):
        a_row = counts[counts["corpus"] == a_name].iloc[0]
        b_row = counts[counts["corpus"] == b_name].iloc[0]
        stats = _proportions_ztest(
            int(a_row["accepted"]),
            int(a_row["total"]),
            int(b_row["accepted"]),
            int(b_row["total"]),
        )
        results.append(
            {
                "corpus_a": a_name,
                "corpus_b": b_name,
                "z_stat": float(stats["z_stat"]),
                "p_value": float(stats["p_value"]),
                "rate_a": a_row["accepted"] / a_row["total"],
                "rate_b": b_row["accepted"] / b_row["total"],
            }
        )
    return results


def compute_latency_test(
    rules_latencies: List[float], llm_latencies: List[float]
) -> Dict[str, float]:
    """Run a two-sided Mann-Whitney U test on latency distributions."""
    stat, p_value = mannwhitneyu(rules_latencies, llm_latencies, alternative="two-sided")
    return {
        "statistic": float(stat),
        "p_value": float(p_value),
        "rules_median_ms": float(pd.Series(rules_latencies).median()),
        "llm_median_ms": float(pd.Series(llm_latencies).median()),
        "rules_p95_ms": float(pd.Series(rules_latencies).quantile(0.95)),
        "llm_p95_ms": float(pd.Series(llm_latencies).quantile(0.95)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", type=Path, required=True,
                        help="CSV with columns corpus,accepted,total (Table 4 inputs)")
    parser.add_argument("--rules-latencies", type=Path, required=True,
                        help="JSON log with latency_ms for deterministic rules replay")
    parser.add_argument("--llm-latencies", type=Path, required=True,
                        help="JSON log with latency_ms for Grok/LLM replay")
    parser.add_argument("--output", type=Path, required=True,
                        help="Destination JSON for the computed statistics")
    args = parser.parse_args()

    counts_df = pd.read_csv(args.counts)
    acceptance = compute_acceptance_tests(counts_df)
    latency = compute_latency_test(
        load_latencies(args.rules_latencies),
        load_latencies(args.llm_latencies),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        json.dump({"acceptance": acceptance, "latency": latency}, fh, indent=2)


if __name__ == "__main__":
    main()
