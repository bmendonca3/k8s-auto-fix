#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _pct_from_counts(accepted: int, total: int) -> str:
    return _pct(accepted / total if total else 0.0)


def _read(path: str) -> str:
    candidate = ROOT / path
    if not candidate.exists():
        return ""
    return candidate.read_text(encoding="utf-8")


def _require(path: str, pattern: str, label: str, failures: list[str]) -> None:
    if re.search(pattern, _read(path), flags=re.MULTILINE) is None:
        failures.append(f"{path}: missing {label} ({pattern})")


def _reject(path: str, pattern: str, label: str, failures: list[str]) -> None:
    if re.search(pattern, _read(path), flags=re.MULTILINE) is not None:
        failures.append(f"{path}: contains stale {label} ({pattern})")


def _load_csv_rows(path: str, failures: list[str]) -> dict[str, dict[str, str]]:
    candidate = ROOT / path
    if not candidate.exists():
        failures.append(f"{path}: missing required metrics table")
        return {}
    with candidate.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {str(row.get("corpus", "")): row for row in rows}


def _require_csv_count(
    rows: dict[str, dict[str, str]],
    path: str,
    corpus: str,
    accepted: int,
    total: int,
    failures: list[str],
) -> None:
    row = rows.get(corpus)
    if row is None:
        failures.append(f"{path}: missing {corpus} row")
        return
    got = (row.get("accepted"), row.get("total"))
    expected = (str(accepted), str(total))
    if got != expected:
        failures.append(f"{path}: {corpus} has accepted/total {got}, expected {expected}")


def _require_csv_rate(
    rows: dict[str, dict[str, str]],
    path: str,
    corpus: str,
    accepted: int,
    total: int,
    failures: list[str],
) -> None:
    row = rows.get(corpus)
    if row is None:
        failures.append(f"{path}: missing {corpus} row")
        return
    _require_csv_count(rows, path, corpus, accepted, total, failures)
    if "acceptance_rate" not in row:
        failures.append(f"{path}: {corpus} missing acceptance_rate")
        return
    try:
        actual_rate = float(row["acceptance_rate"])
    except (TypeError, ValueError):
        failures.append(f"{path}: {corpus} has invalid acceptance_rate {row.get('acceptance_rate')!r}")
        return
    expected_rate = accepted / total if total else 0.0
    if abs(actual_rate - expected_rate) > 1e-12:
        failures.append(f"{path}: {corpus} has acceptance_rate {actual_rate}, expected {expected_rate}")


def _expected_rate(rows: dict[str, dict[str, str]], corpus: str) -> float | None:
    row = rows.get(corpus)
    if row is None:
        return None
    try:
        accepted = int(str(row["accepted"]))
        total = int(str(row["total"]))
    except (KeyError, TypeError, ValueError):
        return None
    return accepted / total if total else 0.0


def _check_significance_rates(counts_rows: dict[str, dict[str, str]], failures: list[str]) -> None:
    path = "data/eval/significance_tests.json"
    candidate = ROOT / path
    if not candidate.exists():
        failures.append(f"{path}: missing required significance table")
        return
    data = json.loads(candidate.read_text(encoding="utf-8"))
    acceptance = data.get("acceptance")
    if not isinstance(acceptance, list):
        failures.append(f"{path}: missing acceptance list")
        return
    for index, entry in enumerate(acceptance):
        if not isinstance(entry, dict):
            failures.append(f"{path}: acceptance[{index}] is not an object")
            continue
        for corpus_key, rate_key in (("corpus_a", "rate_a"), ("corpus_b", "rate_b")):
            corpus = entry.get(corpus_key)
            if not isinstance(corpus, str):
                failures.append(f"{path}: acceptance[{index}] missing {corpus_key}")
                continue
            expected = _expected_rate(counts_rows, corpus)
            if expected is None:
                failures.append(f"{path}: acceptance[{index}] references unknown corpus {corpus}")
                continue
            try:
                actual = float(entry[rate_key])
            except (KeyError, TypeError, ValueError):
                failures.append(f"{path}: acceptance[{index}] missing numeric {rate_key}")
                continue
            if abs(actual - expected) > 1e-12:
                failures.append(f"{path}: acceptance[{index}] {rate_key} for {corpus} is {actual}, expected {expected}")


def check() -> list[str]:
    failures: list[str] = []
    rules = _load_json("data/metrics_rules_full.json")
    grok5k = _load_json("data/outputs/batch_runs/grok_5k/metrics_grok5k.json")

    rules_accepted = int(rules["accepted"])
    rules_patches = int(rules.get("patches", rules["detections"]))
    rules_detections = int(rules["detections"])
    rules_rate = float(rules["auto_fix_rate"])
    rules_median = int(float(rules["median_patch_ops"]))
    rules_safety_failures = int(rules.get("failed_safety", 0))

    grok_accepted = int(grok5k["accepted"])
    grok_total = int(grok5k["detections"])
    grok_median = int(float(grok5k["median_patch_ops"]))
    grok_pct = _pct_from_counts(grok_accepted, grok_total)

    paper_files = [
        "README.md",
        "docs/ablation_rules_vs_grok.md",
        "docs/literature_comparison.md",
        "docs/related_work.md",
        "paper/access.tex",
        "paper/cover_letter.md",
        "paper/overleaf/paper/access.tex",
        "paper/overleaf/paper/cover_letter.md",
    ]
    for path in paper_files:
        _reject(
            path,
            r"13,589\s*/\s*13,656|13\{,\}589\s*/\s*13\{,\}656|13589/13656|99\.51%",
            "rules full-corpus metric",
            failures,
        )
        _reject(
            path,
            r"4,439\s*/\s*5,000|4\{,\}439\s*/\s*5\{,\}000|4439/5000|88\.78%",
            "Grok-5k metric",
            failures,
        )

    eval_files = ["data/eval/table4_counts.csv", "data/eval/table4_with_ci.csv", "data/eval/significance_tests.json"]
    for path in eval_files:
        _reject(path, r"manifest_slice_rules,13589,13656|13589,13656|0\.9950937316930287|0\.8878", "stale eval metric", failures)

    counts_rows = _load_csv_rows("data/eval/table4_counts.csv", failures)
    _require_csv_count(counts_rows, "data/eval/table4_counts.csv", "full_corpus_rules", rules_accepted, rules_patches, failures)
    _require_csv_count(counts_rows, "data/eval/table4_counts.csv", "grok5k_llm", grok_accepted, grok_total, failures)
    _check_significance_rates(counts_rows, failures)

    ci_rows = _load_csv_rows("data/eval/table4_with_ci.csv", failures)
    _require_csv_rate(ci_rows, "data/eval/table4_with_ci.csv", "full_corpus_rules", rules_accepted, rules_patches, failures)
    _require_csv_rate(ci_rows, "data/eval/table4_with_ci.csv", "grok5k_llm", grok_accepted, grok_total, failures)

    _require(
        "README.md",
        rf"{rules_accepted:,}\s*/\s*{rules_patches:,}.*{rules_rate:.4f}.*{rules_detections:,}.*{rules_median}",
        "current rules full-corpus summary",
        failures,
    )
    _require(
        "README.md",
        rf"{grok_accepted:,}\s*/\s*{grok_total:,}.*{grok_pct}.*{grok_median}",
        "current Grok-5k summary",
        failures,
    )
    _require(
        "paper/access.tex",
        rf"{rules_accepted:,}".replace(",", r"\{,\}") + rf".*{rules_patches:,}".replace(",", r"\{,\}") + rf".*{rules_rate:.4f}",
        "current paper rules summary",
        failures,
    )
    _require(
        "paper/access.tex",
        rf"{rules_safety_failures}\s+safety failures",
        "current paper safety failure count",
        failures,
    )
    _require(
        "paper/overleaf/paper/access.tex",
        rf"{rules_accepted:,}".replace(",", r"\{,\}") + rf".*{rules_patches:,}".replace(",", r"\{,\}") + rf".*{rules_rate:.4f}",
        "current Overleaf paper rules summary",
        failures,
    )
    _require(
        "paper/overleaf/paper/access.tex",
        rf"{rules_safety_failures}\s+safety failures",
        "current Overleaf paper safety failure count",
        failures,
    )
    _require(
        "paper/access.tex",
        rf"{grok_accepted:,}".replace(",", r"\{,\}")
        + rf"\s*/\s*{grok_total:,}".replace(",", r"\{,\}")
        + ".*"
        + re.escape(grok_pct.replace("%", r"\%")),
        "current paper Grok-5k summary",
        failures,
    )
    _require(
        "paper/overleaf/paper/access.tex",
        rf"{grok_accepted:,}".replace(",", r"\{,\}")
        + rf"\s*/\s*{grok_total:,}".replace(",", r"\{,\}")
        + ".*"
        + re.escape(grok_pct.replace("%", r"\%")),
        "current Overleaf paper Grok-5k summary",
        failures,
    )
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check paper-facing metric text against source JSON artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable check results.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = check()
    if args.json:
        print(json.dumps({"ok": not failures, "failures": failures}, indent=2))
    elif failures:
        print("Metric consistency check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
    else:
        print("Metric consistency check passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
