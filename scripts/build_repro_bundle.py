#!/usr/bin/env python3
"""Generate the reproducibility bundle (JSON + Markdown + LaTeX) from source artifacts."""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOC_DIR = ROOT / "docs" / "reproducibility"


@dataclass(frozen=True)
class DatasetSpec:
    dataset: str
    mode: str
    seed: Optional[int]
    note: str
    metrics_path: Path
    verified_path: Optional[Path] = None
    patches_path: Optional[Path] = None


def _ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required artifact missing: {path}")


def _load_json(path: Path) -> Any:
    _ensure_exists(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return lower_value + (upper_value - lower_value) * (rank - lower)


def _summarise_verified(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {"count": 0, "median_ms": None, "p95_ms": None}
    data = _load_json(path)
    latencies = [
        float(entry["latency_ms"])
        for entry in data
        if isinstance(entry, dict) and isinstance(entry.get("latency_ms"), (int, float))
    ]
    if not latencies:
        return {"count": 0, "median_ms": None, "p95_ms": None}
    return {
        "count": len(latencies),
        "median_ms": round(_safe_median(latencies), 2),
        "p95_ms": round(_percentile(latencies, 95.0), 2),
    }


def _summarise_patches(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {
            "count": 0,
            "median_ms": None,
            "p95_ms": None,
            "token_usage": None,
            "median_patch_ops": None,
        }

    data = _load_json(path)
    latencies: List[float] = []
    patch_lengths: List[int] = []
    prompt_tokens = 0.0
    completion_tokens = 0.0
    total_tokens = 0.0
    usage_samples = 0

    for entry in data:
        if not isinstance(entry, dict):
            continue
        latency = entry.get("total_latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))

        patch = entry.get("patch")
        if isinstance(patch, list):
            patch_lengths.append(len(patch))

        usage = entry.get("model_usage")
        if isinstance(usage, dict):
            prompt = float(usage.get("prompt_tokens") or 0.0)
            completion = float(usage.get("completion_tokens") or 0.0)
            total = float(usage.get("total_tokens") or (prompt + completion))
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            usage_samples += 1

    token_usage = None
    if usage_samples:
        token_usage = {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
            "mean_per_patch": total_tokens / usage_samples if usage_samples else 0.0,
        }

    median_latency = round(_safe_median(latencies), 2) if latencies else None
    p95_latency = round(_percentile(latencies, 95.0), 2) if latencies else None
    median_patch_ops = (
        round(_safe_median([float(length) for length in patch_lengths]), 2)
        if patch_lengths
        else None
    )

    return {
        "count": len(latencies),
        "median_ms": median_latency,
        "p95_ms": p95_latency,
        "token_usage": token_usage,
        "median_patch_ops": median_patch_ops,
    }


def _derive_acceptance(metrics: Dict[str, Any]) -> Dict[str, Optional[float]]:
    total = metrics.get("detections") or metrics.get("total")
    accepted = metrics.get("accepted")
    if accepted is None:
        auto_fix = metrics.get("auto_fix")
        if isinstance(auto_fix, (int, float)):
            accepted = auto_fix

    rate = metrics.get("auto_fix_rate")
    if rate is None and accepted is not None and total:
        rate = float(accepted) / float(total)

    if accepted is not None and isinstance(accepted, float):
        accepted = round(accepted)

    return {
        "total": int(total) if isinstance(total, (int, float)) else None,
        "accepted": int(accepted) if isinstance(accepted, (int, float)) else None,
        "rate": float(rate) if isinstance(rate, (int, float)) else None,
    }


def _rel_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    return str(path.relative_to(ROOT))


def summarise_dataset(spec: DatasetSpec) -> Dict[str, Any]:
    metrics = _load_json(spec.metrics_path)
    acceptance = _derive_acceptance(metrics)

    proposer_stats = _summarise_patches(spec.patches_path)
    verifier_stats = _summarise_verified(spec.verified_path)

    median_ops = metrics.get("median_patch_ops")
    if median_ops is None:
        median_ops = proposer_stats.get("median_patch_ops")

    summary: Dict[str, Any] = {
        "dataset": spec.dataset,
        "mode": spec.mode,
        "seed": spec.seed,
        "note": spec.note,
        "total": acceptance["total"],
        "accepted": acceptance["accepted"],
        "acceptance_rate": acceptance["rate"],
        "median_patch_ops": median_ops,
        "proposer_latency_ms": {
            key: proposer_stats.get(key)
            for key in ("count", "median_ms", "p95_ms")
        },
        "verify_latency_ms": verifier_stats,
        "token_usage": proposer_stats.get("token_usage"),
        "sources": {
            "metrics": _rel_path(spec.metrics_path),
            "patches": _rel_path(spec.patches_path),
            "verified": _rel_path(spec.verified_path),
        },
    }

    return summary


def _format_acceptance(entry: Dict[str, Any]) -> str:
    accepted = entry.get("accepted")
    total = entry.get("total")
    rate = entry.get("acceptance_rate")
    if accepted is None or total is None:
        return "n/a"
    if rate is None or rate != rate:
        return f"{accepted}/{total}"
    return f"{accepted}/{total} ({rate * 100:.2f}%)"


def _format_latency(bucket: Optional[Dict[str, Any]]) -> str:
    if not bucket:
        return "n/a"
    median = bucket.get("median_ms")
    if median is None:
        return "n/a"
    return f"{median:.2f}"


def _format_latency_p95(bucket: Optional[Dict[str, Any]]) -> str:
    if not bucket:
        return "n/a"
    p95 = bucket.get("p95_ms")
    if p95 is None:
        return "n/a"
    return f"{p95:.2f}"


def _format_tokens(entry: Dict[str, Any]) -> str:
    usage = entry.get("token_usage")
    if not usage:
        return "n/a"
    return f"{usage['prompt']:,.0f} / {usage['completion']:,.0f}"


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    escaped = []
    for char in text:
        escaped.append(replacements.get(char, char))
    return "".join(escaped)


def _format_acceptance_latex(entry: Dict[str, Any]) -> str:
    accepted = entry.get("accepted")
    total = entry.get("total")
    rate = entry.get("acceptance_rate")
    if accepted is None or total is None:
        return "n/a"
    if rate is None or rate != rate:
        return f"{accepted}/{total}"
    percentage = f"{rate * 100:.2f}"
    return f"{accepted}/{total} ({percentage}\\%)"


def _format_note_latex(note: str) -> str:
    return _escape_latex(note)


def write_summary_json(results: List[Dict[str, Any]]) -> None:
    output_path = DATA_DIR / "eval" / "unified_eval_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)


def write_markdown(results: List[Dict[str, Any]]) -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Reproducibility Report",
        "",
        "Regenerated via `make reproducible-report`. Each row references the JSON artifacts that back the published metrics.",
        "",
        "## Dataset Summary",
        "",
        "| Dataset | Mode | Seed | Acceptance | Median proposer (ms) | Median verifier (ms) | Verifier P95 (ms) | Token usage (prompt / completion) | Artifacts |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for entry in results:
        sources: List[str] = []
        for key in ("metrics", "patches", "verified"):
            path = entry["sources"].get(key)
            if path:
                sources.append(f"`{path}`")
        artifact_cell = "<br/>".join(sources) if sources else "n/a"
        lines.append(
            "| {dataset} | {mode} | {seed} | {acceptance} | {prop} | {verify} | {p95} | {tokens} | {artifacts} |".format(
                dataset=entry["dataset"],
                mode=entry["mode"],
                seed=entry["seed"] if entry["seed"] is not None else "n/a",
                acceptance=_format_acceptance(entry),
                prop=_format_latency(entry.get("proposer_latency_ms")),
                verify=_format_latency(entry.get("verify_latency_ms")),
                p95=_format_latency_p95(entry.get("verify_latency_ms")),
                tokens=_format_tokens(entry),
                artifacts=artifact_cell,
            )
        )

    lines.extend(
        [
            "",
            "## Artifact Map",
            "",
            "- `data/eval/unified_eval_summary.json` – machine-readable summary consumed by the README and paper tables.",
            "- `docs/reproducibility/tables.tex` – LaTeX snippet mirroring Table~\\ref{tab:eval_summary}.",
            "- `docs/reproducibility/report.md` (this file) – human-readable summary linking metrics to artifacts.",
        ]
    )

    (DOC_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex_table(results: List[Dict[str, Any]]) -> None:
    lines = [
        r"\begin{tabularx}{\textwidth}{@{}l c c c c c X@{}}",
        r"\toprule",
        r"\textbf{Corpus (mode)} & \textbf{Seed} & \textbf{Acceptance} & \textbf{Median proposer (ms)} & \textbf{Median verifier (ms)} & \textbf{Verifier P95 (ms)} & \textbf{Notes} \\",  # Header row
        r"\midrule",
    ]

    for entry in results:
        dataset = _escape_latex(entry["dataset"])
        mode = _escape_latex(entry["mode"])
        seed = entry["seed"] if entry["seed"] is not None else "n/a"
        acceptance = _format_acceptance_latex(entry)
        proposer = _escape_latex(_format_latency(entry.get("proposer_latency_ms")))
        verifier = _escape_latex(_format_latency(entry.get("verify_latency_ms")))
        verifier_p95 = _escape_latex(_format_latency_p95(entry.get("verify_latency_ms")))
        note = _format_note_latex(entry["note"])

        row = f"{dataset} ({mode}) & {seed} & {acceptance} & {proposer} & {verifier} & {verifier_p95} & {note} \\\\"  # LaTeX row
        lines.append(row)

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabularx}",
        ]
    )

    (DOC_DIR / "tables.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    specs: List[DatasetSpec] = [
        DatasetSpec(
            dataset="Supported 1.264k",
            mode="rules",
            seed=1337,
            note="Curated Helm/Operator corpus with host-mount normalisation.",
            metrics_path=DATA_DIR / "batch_runs" / "secondary_supported" / "metrics_rules.json",
            verified_path=DATA_DIR / "batch_runs" / "secondary_supported" / "verified_rules.json",
            patches_path=DATA_DIR / "batch_runs" / "secondary_supported" / "patches_rules.json",
        ),
        DatasetSpec(
            dataset="Supported 5k",
            mode="rules",
            seed=1337,
            note="Extended supported corpus (5,000 curated manifests).",
            metrics_path=DATA_DIR / "metrics_rules_5000.json",
            verified_path=DATA_DIR / "verified_rules_5000.json",
            patches_path=DATA_DIR / "patches_rules_5000.json",
        ),
        DatasetSpec(
            dataset="Manifest 1.313k",
            mode="rules",
            seed=1337,
            note="Full manifest slice in deterministic rules mode.",
            metrics_path=DATA_DIR / "metrics_rules_full.json",
            verified_path=DATA_DIR / "verified_rules_full.json",
            patches_path=DATA_DIR / "patches_rules_full.json",
        ),
        DatasetSpec(
            dataset="Manifest 1.313k",
            mode="grok",
            seed=1337,
            note="Grok/xAI with guardrail merge (five TPU jobs rejected).",
            metrics_path=DATA_DIR / "batch_runs" / "grok_full" / "metrics_grok_full.json",
            verified_path=DATA_DIR / "batch_runs" / "grok_full" / "verified_grok_full.json",
            patches_path=DATA_DIR / "batch_runs" / "grok_full" / "patches_grok_full.json",
        ),
        DatasetSpec(
            dataset="Grok-5k",
            mode="grok",
            seed=1337,
            note="Five-thousand manifest sweep with telemetry instrumentation.",
            metrics_path=DATA_DIR / "batch_runs" / "grok_5k" / "metrics_grok5k.json",
            verified_path=DATA_DIR / "batch_runs" / "grok_5k" / "verified_grok5k.json",
            patches_path=DATA_DIR / "batch_runs" / "grok_5k" / "patches_grok5k.json",
        ),
    ]

    results = [summarise_dataset(spec) for spec in specs]
    write_summary_json(results)
    write_markdown(results)
    write_latex_table(results)


if __name__ == "__main__":
    main()
