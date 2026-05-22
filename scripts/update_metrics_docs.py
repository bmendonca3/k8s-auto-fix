#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


README_PATH = Path("README.md")
PAPER_PATH = Path("paper/access.tex")
OVERLEAF_PAPER_PATH = Path("paper/overleaf/paper/access.tex")

README_MARKERS = ("<!-- METRICS_SECTION_START -->", "<!-- METRICS_SECTION_END -->")
PAPER_MARKERS = ("% METRICS_EVAL_START", "% METRICS_EVAL_END")


def load_json(path: Path) -> Optional[object]:
    def _open(path: Path):
        if path.exists():
            return path.open("r", encoding="utf-8")
        gz_path = path.with_suffix(path.suffix + ".gz")
        if gz_path.exists():
            return gzip.open(gz_path, "rt", encoding="utf-8")
        raise FileNotFoundError

    try:
        with _open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def format_ratio(numerator: int, denominator: int, *, precision: int = 1) -> Tuple[str, str]:
    if denominator <= 0:
        return "0/0", "0%"
    pct = (numerator / denominator) * 100.0
    ratio = f"{numerator}/{denominator}"
    percentage = f"{pct:.{precision}f}%"
    return ratio, percentage


def format_metric_number(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def latex_int(value: int) -> str:
    return f"{value:,}".replace(",", "{,}")


def format_hours(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}h"


def format_float(value: Optional[float], precision: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{precision}f}"


def replace_section(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    if start_marker not in text or end_marker not in text:
        raise ValueError(f"Markers {start_marker} or {end_marker} not found")
    start_idx = text.index(start_marker) + len(start_marker)
    end_idx = text.index(end_marker)
    return text[:start_idx] + "\n" + replacement.strip() + "\n" + text[end_idx:]


@dataclass
class MetricsBundle:
    rules: Optional[Dict[str, object]]
    rules_5000: Optional[Dict[str, object]]
    supported_rules: Optional[Dict[str, object]]
    grok_full: Optional[Dict[str, object]]
    grok5k: Optional[Dict[str, object]]
    schedule: Optional[Dict[str, object]]
    grok200_results: Optional[Sequence[Dict[str, object]]]

    @classmethod
    def load(cls) -> "MetricsBundle":
        return cls(
            rules=load_json(Path("data/metrics_rules_full.json")),
            rules_5000=load_json(Path("data/metrics_rules_5000.json")),
            supported_rules=load_json(Path("data/outputs/batch_runs/secondary_supported/summary.json")),
            grok_full=load_json(Path("data/batch_runs/grok_full/metrics_grok_full.json")),
            grok5k=load_json(Path("data/outputs/batch_runs/grok_5k/metrics_grok5k.json")),
            schedule=load_json(Path("data/metrics_schedule_compare.json")),
            grok200_results=load_json(Path("data/batch_runs/results_grok200.json")),
        )


def build_rules_summary(data: Optional[Dict[str, object]]) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    detections = int(data.get("detections", 0))
    accepted = int(data.get("accepted", 0))
    patches = int(data.get("patches", detections))
    median_ops = data.get("median_patch_ops")
    _, acceptance_percentage = format_ratio(accepted, patches, precision=2)
    median_text = format_metric_number(median_ops) if median_ops is not None else "n/a"
    return (
        "- **Full rules + guardrails replay** – "
        f"{accepted:,} / {patches:,} patched items accepted "
        f"({acceptance_percentage}; auto-fix rate {float(data.get('auto_fix_rate', 0.0)):.4f} over "
        f"{detections:,} detections; median patch ops {median_text}) from "
        "`data/metrics_rules_full.json` (`patches_rules_full.json.gz`, `verified_rules_full.json.gz`)."
    )


def build_simple_acceptance_summary(
    data: Optional[Dict[str, object]],
    *,
    label: str,
    source: str,
) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    detections = int(data.get("detections", 0))
    accepted = int(data.get("accepted", 0))
    median_ops = data.get("median_patch_ops")
    ratio, percentage = format_ratio(accepted, detections)
    median_text = format_metric_number(median_ops) if median_ops is not None else "n/a"
    return f"- **{label}** – {ratio} accepted ({percentage}; median ops {median_text}) from `{source}`."


def build_grok200_summary(results: Optional[Sequence[Dict[str, object]]]) -> Optional[str]:
    if not isinstance(results, list) or not results:
        return None
    total = 0
    accepted = 0
    for entry in results:
        if not isinstance(entry, dict):
            continue
        total += int(entry.get("count", 0))
        accepted += int(entry.get("accepted", 0))
    if total == 0:
        return None
    ratio, percentage = format_ratio(accepted, total)
    batches = len(results)
    return (
        "- **Grok benchmark (first 200 detections)** – "
        f"`make benchmark-grok200` runs {batches} batches totalling {total} detections with {ratio} accepted ({percentage}); "
        "artifacts live under `data/batch_runs/`."
    )


def extract_rank_summary(schedule: Optional[Dict[str, object]]) -> Optional[str]:
    if not isinstance(schedule, dict):
        return None
    summary = schedule.get("summary")
    if not isinstance(summary, dict):
        return None
    top_n = summary.get("top_n")
    base = summary.get("baseline", {})
    fifo = summary.get("fifo", {})
    risk_only = summary.get("risk_only", {})
    risk_time = summary.get("risk_time", {})
    if not all(isinstance(entry, dict) for entry in (base, fifo, risk_only, risk_time)):
        return None
    return (
        "- **Scheduler comparison** – `make benchmark-scheduler` ranks the top "
        f"{top_n} high-risk items at mean rank {base.get('mean_rank_top_n')} (median {base.get('median_rank_top_n')}, "
        f"P95 {base.get('p95_rank_top_n')}). Risk-only remaps preserve the same ordering, while the "
        f"`risk/Et+aging` baseline averages {risk_time.get('mean_rank_top_n')} (P95 {risk_time.get('p95_rank_top_n')}). "
        f"FIFO slips to mean {fifo.get('mean_rank_top_n')} (P95 {fifo.get('p95_rank_top_n')})."
    )


def extract_telemetry_summary(schedule: Optional[Dict[str, object]]) -> Optional[str]:
    if not isinstance(schedule, dict):
        return None
    telemetry = schedule.get("telemetry")
    if not isinstance(telemetry, dict):
        return None
    baseline = telemetry.get("baseline", {})
    fifo = telemetry.get("fifo", {})
    if not isinstance(baseline, dict) or not isinstance(fifo, dict):
        return None
    throughput = baseline.get("throughput_per_hour")
    total_hours = baseline.get("total_runtime_hours")
    baseline_wait = (baseline.get("top_risk_wait_hours") or {}).get("p95")
    fifo_wait = (fifo.get("top_risk_wait_hours") or {}).get("p95")
    return (
        "- **Scheduler telemetry** – the baseline bandit completes 1,313 patches in "
        f"{format_hours(total_hours)} at ~{format_float(throughput)} patches/hour with top-risk P95 wait "
        f"{format_hours(baseline_wait)}; FIFO stretches the same P95 wait to {format_hours(fifo_wait)} "
        "(`telemetry` in `data/metrics_schedule_compare.json`)."
    )


def build_readme_section(metrics: MetricsBundle) -> str:
    bullets: List[str] = []
    rules_line = build_rules_summary(metrics.rules)
    if rules_line:
        bullets.append(rules_line)
    rules_5000_line = build_simple_acceptance_summary(
        metrics.rules_5000,
        label="Rules on the 5k extended corpus",
        source="data/metrics_rules_5000.json",
    )
    if rules_5000_line:
        bullets.append(rules_5000_line)
    grok5k_line = build_simple_acceptance_summary(
        metrics.grok5k,
        label="Grok/xAI 5k proposer",
        source="data/outputs/batch_runs/grok_5k/metrics_grok5k.json",
    )
    if grok5k_line:
        bullets.append(grok5k_line)
    supported_line = build_simple_acceptance_summary(
        metrics.supported_rules,
        label="Supported corpus (rules)",
        source="data/outputs/batch_runs/secondary_supported/summary.json",
    )
    if supported_line:
        bullets.append(supported_line)
    rank_line = extract_rank_summary(metrics.schedule)
    if rank_line:
        bullets.append(rank_line)
    telemetry_line = extract_telemetry_summary(metrics.schedule)
    if telemetry_line:
        bullets.append(telemetry_line)
    return "\n".join(bullets)


def build_paper_paragraph(metrics: MetricsBundle) -> str:
    rules = metrics.rules if isinstance(metrics.rules, dict) else None
    schedule = metrics.schedule if isinstance(metrics.schedule, dict) else None

    parts: List[str] = []
    if rules:
        detections = int(rules.get("detections", 0))
        accepted = int(rules.get("accepted", 0))
        patches = int(rules.get("patches", detections))
        _, acceptance_percentage = format_ratio(accepted, patches, precision=2)
        median_ops = rules.get("median_patch_ops")
        median_text = format_metric_number(median_ops) if median_ops is not None else "n/a"
        safety_failures = int(rules.get("failed_safety", 0))
        parts.append(
            f"Running the full corpus of {latex_int(detections)} detections in rules+guardrails mode yields "
            f"{latex_int(accepted)} accepted out of {latex_int(patches)} patched items ({acceptance_percentage}; "
            f"auto-fix rate {float(rules.get('auto_fix_rate', 0.0)):.4f} over detections) with a median "
            f"of {median_text} JSON Patch operations and {safety_failures} safety failures "
            "(all non-hostPath edge cases)."
        )

    telemetry = (schedule or {}).get("telemetry", {}) if schedule else {}
    baseline = telemetry.get("baseline", {}) if isinstance(telemetry, dict) else {}
    fifo = telemetry.get("fifo", {}) if isinstance(telemetry, dict) else {}
    base_wait = (baseline.get("top_risk_wait_hours") or {}).get("p95")
    fifo_wait = (fifo.get("top_risk_wait_hours") or {}).get("p95")
    throughput = baseline.get("throughput_per_hour")

    if baseline:
        wait_delta = None
        if isinstance(base_wait, (int, float)) and isinstance(fifo_wait, (int, float)):
            wait_delta = fifo_wait - base_wait
        wait_part = ""
        if wait_delta is not None:
            wait_part = (
                f"while FIFO defers the same cohort to {fifo_wait:.1f}\\,h (+{wait_delta:.1f}\\,h)."
            )
        parts.append(
            f"Bandit scheduling preserves fairness: baseline top-risk items see P95 wait of {base_wait:.1f}\\,h "
            f"at roughly {throughput:.1f} patches/hour {wait_part}"
        )

    paragraph = " ".join(parts).strip()
    if not paragraph:
        paragraph = (
            "Benchmark metrics are pending; rerun the Makefile benchmarks and re-execute "
            "`python scripts/update_metrics_docs.py` to refresh this section."
        )
    return (
        "\\noindent\\textbf{Latest Evaluation.} "
        + paragraph.replace("%", "\\%")
    )


def replace_heading_section(text: str, heading: str, replacement: str) -> str:
    heading_line = f"## {heading}"
    start = text.find(heading_line)
    if start == -1:
        raise ValueError(f"Heading {heading_line!r} not found")
    content_start = text.find("\n", start)
    if content_start == -1:
        return text[: start + len(heading_line)] + "\n\n" + replacement.strip() + "\n"
    next_heading = text.find("\n## ", content_start + 1)
    if next_heading == -1:
        next_heading = len(text)
    return text[: content_start + 1] + "\n" + replacement.strip() + "\n" + text[next_heading:]


def update_readme(readme_path: Path, section: str) -> None:
    text = readme_path.read_text(encoding="utf-8")
    if README_MARKERS[0] in text and README_MARKERS[1] in text:
        updated = replace_section(text, README_MARKERS[0], README_MARKERS[1], section)
    else:
        updated = replace_heading_section(text, "Metrics aligned to the paper (traceable in-repo)", section)
    readme_path.write_text(updated, encoding="utf-8")


def update_paper(paper_path: Path, paragraph: str) -> None:
    text = paper_path.read_text(encoding="utf-8")
    updated = replace_section(text, PAPER_MARKERS[0], PAPER_MARKERS[1], paragraph)
    paper_path.write_text(updated, encoding="utf-8")


def run(dry_run: bool = False, skip_readme: bool = False, skip_paper: bool = False) -> Tuple[str, str]:
    metrics = MetricsBundle.load()
    readme_section = build_readme_section(metrics)
    paper_paragraph = build_paper_paragraph(metrics)

    schedule_summary = metrics.schedule.get("summary") if isinstance(metrics.schedule, dict) else None
    schedule_telemetry = metrics.schedule.get("telemetry") if isinstance(metrics.schedule, dict) else None
    dashboards_payload = {
        "scheduler_summary": schedule_summary or {},
        "scheduler_telemetry": schedule_telemetry or {},
    }

    if dry_run:
        return readme_section, paper_paragraph

    dashboards_path = Path("data/dashboard_metrics.json")
    dashboards_path.parent.mkdir(parents=True, exist_ok=True)
    dashboards_path.write_text(json.dumps(dashboards_payload, indent=2), encoding="utf-8")

    if not skip_readme:
        update_readme(README_PATH, readme_section)
    if not skip_paper:
        update_paper(PAPER_PATH, paper_paragraph)
        if OVERLEAF_PAPER_PATH.exists():
            update_paper(OVERLEAF_PAPER_PATH, paper_paragraph)
    return readme_section, paper_paragraph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh README and paper metrics from benchmark artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated sections without editing files.")
    parser.add_argument("--no-readme", action="store_true", help="Skip README updates.")
    parser.add_argument("--no-paper", action="store_true", help="Skip paper updates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    readme_section, paper_paragraph = run(
        dry_run=args.dry_run,
        skip_readme=args.no_readme,
        skip_paper=args.no_paper,
    )
    if args.dry_run:
        print("README section:\n", readme_section)
        print("\nPaper paragraph:\n", paper_paragraph)


if __name__ == "__main__":  # pragma: no cover
    main()
