#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.compare_schedulers import compare_schedulers


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: str) -> dict[str, Any]:
    candidate = ROOT / path
    if not candidate.exists():
        return {}
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_json_array(path: str, failures: list[str]) -> list[dict[str, Any]]:
    candidate = ROOT / path
    compressed = candidate.with_suffix(candidate.suffix + ".gz")
    try:
        if candidate.exists():
            with candidate.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        elif compressed.exists():
            with gzip.open(compressed, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            failures.append(f"{path}: missing raw source artifact (including .gz fallback)")
            return []
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"{path}: cannot load raw source artifact: {exc}")
        return []
    if not isinstance(payload, list):
        failures.append(f"{path}: raw source artifact must contain a JSON array")
        return []
    return [item for item in payload if isinstance(item, dict)]


def _recompute_rules_metrics(failures: list[str]) -> dict[str, int | float]:
    detections = _load_json_array("data/detections.json", failures)
    patches = _load_json_array("data/patches_rules_full.json", failures)
    verified = _load_json_array("data/verified_rules_full.json", failures)
    patch_lengths = {
        str(item.get("id")): len(item.get("patch") or [])
        for item in patches
    }
    accepted_records = [item for item in verified if item.get("accepted")]
    accepted_lengths = [
        patch_lengths[str(item.get("id"))]
        for item in accepted_records
        if str(item.get("id")) in patch_lengths
    ]
    rejected = [item for item in verified if not item.get("accepted")]
    accepted = len(accepted_records)
    return {
        "detections": len(detections),
        "patches": len(patches),
        "verified": len(verified),
        "accepted": accepted,
        "auto_fix_rate": round(accepted / len(detections), 4) if detections else 0.0,
        "median_patch_ops": statistics.median(accepted_lengths) if accepted_lengths else 0,
        "failed_policy": sum(not bool(item.get("ok_policy", True)) for item in rejected),
        "failed_schema": sum(not bool(item.get("ok_schema", True)) for item in rejected),
        "failed_safety": sum(not bool(item.get("ok_safety", True)) for item in rejected),
        "failed_rescan": sum(not bool(item.get("ok_rescan", True)) for item in rejected),
    }


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_mode_comparison(failures: list[str]) -> None:
    path = ROOT / "data/baselines/mode_comparison.csv"
    if not path.exists():
        failures.append("data/baselines/mode_comparison.csv: missing matched-corpus comparison")
        return
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = {
        "rules+guardrails": (4677, 5000, "data/metrics_rules_5000.json"),
        "grok+rule-guardrails": (4426, 5000, "data/batch_runs/grok_5k/metrics_grok5k.json"),
    }
    if {row.get("mode") for row in rows} != set(expected):
        failures.append(f"data/baselines/mode_comparison.csv: expected modes {sorted(expected)}")
        return
    if {row.get("corpus") for row in rows} != {"shared_supported_5000"}:
        failures.append("data/baselines/mode_comparison.csv: rows must use shared_supported_5000")
    for row in rows:
        mode = str(row.get("mode"))
        accepted, total, source = expected[mode]
        actual = (row.get("accepted"), row.get("manifests"), row.get("source_metrics"))
        wanted = (str(accepted), str(total), source)
        if actual != wanted:
            failures.append(f"data/baselines/mode_comparison.csv: {mode} has {actual}, expected {wanted}")
        try:
            rate = float(str(row.get("acceptance_rate")))
        except ValueError:
            rate = -1.0
        if abs(rate - accepted / total) > 1e-12:
            failures.append(f"data/baselines/mode_comparison.csv: {mode} has inconsistent acceptance_rate")
    rules_detections = ROOT / "data/detections_supported_5000.json"
    grok_detections = ROOT / "data/batch_runs/grok_5k/detections_grok5k.json"
    if not rules_detections.exists() or not grok_detections.exists():
        failures.append("matched 5k mode comparison: a detection source is missing")
    elif _sha256(rules_detections) != _sha256(grok_detections):
        failures.append("matched 5k mode comparison: rules and Grok detection sources differ")


def _check_taxonomy(failures: list[str]) -> None:
    path = ROOT / "data/failures/taxonomy_counts.csv"
    if not path.exists():
        failures.append("data/failures/taxonomy_counts.csv: missing failure taxonomy")
        return
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_columns = {
        "dataset",
        "source_artifact",
        "total_records",
        "rejected_records",
        "failure_category",
        "rejected_records_with_category",
        "error_events",
    }
    if not rows or set(rows[0]) != expected_columns:
        failures.append("data/failures/taxonomy_counts.csv: missing self-contained taxonomy provenance columns")
        return
    expected_datasets = {
        "full_rules_historical": ("data/verified_rules_full.json.gz", 13656, 67),
        "supported_historical": ("data/verified_rules_supported.json", 1278, 19),
    }
    for row in rows:
        dataset = str(row["dataset"])
        if dataset not in expected_datasets:
            failures.append(f"data/failures/taxonomy_counts.csv: unexpected dataset {dataset}")
            continue
        source, total, rejected = expected_datasets[dataset]
        if (row["source_artifact"], row["total_records"], row["rejected_records"]) != (
            source,
            str(total),
            str(rejected),
        ):
            failures.append(f"data/failures/taxonomy_counts.csv: {dataset} provenance mismatch")
        record_count = int(row["rejected_records_with_category"])
        event_count = int(row["error_events"])
        if record_count > rejected or event_count < record_count:
            failures.append(f"data/failures/taxonomy_counts.csv: invalid counts for {dataset}/{row['failure_category']}")
    capability_row = next(
        (
            row
            for row in rows
            if row["dataset"] == "supported_historical"
            and row["failure_category"] == "capabilities not defined"
        ),
        None,
    )
    if capability_row is None or (
        capability_row["rejected_records_with_category"], capability_row["error_events"]
    ) != ("5", "9"):
        failures.append("data/failures/taxonomy_counts.csv: duplicate error events are not separated from rejected records")


def _check_scheduler_reproduction(failures: list[str]) -> None:
    path = ROOT / "data/metrics_schedule_compare.json"
    if not path.exists():
        failures.append("data/metrics_schedule_compare.json: missing scheduler comparison")
        return
    actual = json.loads(path.read_text(encoding="utf-8"))
    expected = compare_schedulers(
        verified_path=ROOT / "data/verified_rules_supported.json",
        detections_path=ROOT / "data/detections_supported.json",
        risk_path=None,
        policy_metrics_path=ROOT / "data/policy_metrics.json",
        out_path=None,
        alpha=1.0,
        epsilon=1e-6,
        top_n=50,
    )
    expected["configuration"]["verified_source"] = "data/verified_rules_supported.json"
    expected["configuration"]["detections_source"] = "data/detections_supported.json"
    expected["configuration"]["policy_metrics_source"] = "data/policy_metrics.json"
    if actual != expected:
        failures.append("data/metrics_schedule_compare.json: does not exactly reproduce from the declared queue snapshot")
    configuration = actual.get("configuration", {})
    if configuration.get("nonzero_wait_inputs") != 0 or configuration.get("nonzero_exploration_inputs") != 0:
        failures.append("data/metrics_schedule_compare.json: paper replay must record zero initial ages and exploration inputs")


def check(*, include_manuscript: bool = False) -> list[str]:
    failures: list[str] = []
    rules = _load_json("data/metrics_rules_full.json")
    raw_rules = _recompute_rules_metrics(failures)
    for key, expected in raw_rules.items():
        actual = rules.get(key)
        if actual != expected:
            failures.append(
                f"data/metrics_rules_full.json: {key} is {actual!r}, expected {expected!r} from raw artifacts"
            )
    metrics_latest = _load_json("data/metrics_latest.json")
    if metrics_latest != rules:
        failures.append("data/metrics_latest.json: does not exactly match data/metrics_rules_full.json")
    grok5k = _load_json("data/outputs/batch_runs/grok_5k/metrics_grok5k.json")

    rules_accepted = int(rules["accepted"])
    rules_patches = int(rules.get("patches", rules["detections"]))
    rules_detections = int(rules["detections"])
    rules_rate = float(rules["auto_fix_rate"])
    rules_median = int(float(rules["median_patch_ops"]))
    rules_rejected = rules_patches - rules_accepted

    grok_accepted = int(grok5k["accepted"])
    grok_total = int(grok5k["detections"])
    grok_median = int(float(grok5k["median_patch_ops"]))
    grok_pct = _pct_from_counts(grok_accepted, grok_total)

    paper_files = [
        "README.md",
        "docs/ablation_rules_vs_grok.md",
        "docs/literature_comparison.md",
        "docs/related_work.md",
    ]
    if include_manuscript:
        paper_files.extend(
            [
                "paper/cover_letter.md",
                "paper/overleaf/paper/access.tex",
                "paper/overleaf/paper/cover_letter.md",
            ]
        )
    for path in paper_files:
        _reject(
            path,
            r"13,338\s*/\s*13,373|13\{,\}338\s*/\s*13\{,\}373|13338/13373|99\.74%|0\.8486",
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
        _reject(path, r"full_corpus_rules,13338,13373|13338,13373|0\.9974|0\.8486|0\.8878", "stale eval metric", failures)

    counts_rows = _load_csv_rows("data/eval/table4_counts.csv", failures)
    _require_csv_count(counts_rows, "data/eval/table4_counts.csv", "full_corpus_rules", rules_accepted, rules_patches, failures)
    _require_csv_count(counts_rows, "data/eval/table4_counts.csv", "grok5k_llm", grok_accepted, grok_total, failures)
    _check_significance_rates(counts_rows, failures)

    ci_rows = _load_csv_rows("data/eval/table4_with_ci.csv", failures)
    _require_csv_rate(ci_rows, "data/eval/table4_with_ci.csv", "full_corpus_rules", rules_accepted, rules_patches, failures)
    _require_csv_rate(ci_rows, "data/eval/table4_with_ci.csv", "grok5k_llm", grok_accepted, grok_total, failures)
    _check_mode_comparison(failures)
    _check_taxonomy(failures)
    _check_scheduler_reproduction(failures)

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
    if include_manuscript:
        rules_accepted_text = f"{rules_accepted:,}".replace(",", r"(?:,|\{,\})")
        rules_patches_text = f"{rules_patches:,}".replace(",", r"(?:,|\{,\})")
        grok_accepted_text = f"{grok_accepted:,}".replace(",", r"(?:,|\{,\})")
        grok_total_text = f"{grok_total:,}".replace(",", r"(?:,|\{,\})")
        grok_pct_text = re.escape(grok_pct.rstrip("%")) + r"(?:\\)?%"
        for path, label in (
            ("paper/overleaf/paper/access.tex", "Overleaf paper"),
            ("paper/cover_letter.md", "cover letter"),
            ("paper/overleaf/paper/cover_letter.md", "Overleaf-package cover letter"),
        ):
            _require(
                path,
                rules_accepted_text
                + r"[\s\S]*?"
                + rules_patches_text
                + rf"[\s\S]*?{rules_rate:.4f}",
                f"current {label} rules summary",
                failures,
            )
            _require(
                path,
                rf"{rules_rejected}\s+rejected\s+(?:records|items)",
                f"current {label} rejected-record count",
                failures,
            )
            _require(
                path,
                grok_accepted_text
                + r"\s*/\s*"
                + grok_total_text
                + r"[\s\S]*?"
                + grok_pct_text,
                f"current {label} Grok-5k summary",
                failures,
            )
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check paper-facing metric text against source JSON artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable check results.")
    parser.add_argument(
        "--include-manuscript",
        action="store_true",
        help="Also validate downstream manuscript mirrors after the Overleaf sync stage.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = check(include_manuscript=args.include_manuscript)
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
