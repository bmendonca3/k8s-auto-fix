#!/usr/bin/env python3
"""Rebuild the reproducibility bundle (JSON + Markdown + LaTeX) from recorded metrics."""

from __future__ import annotations

import gzip
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs" / "reproducibility"


@dataclass(frozen=True)
class DatasetConfig:
    dataset: str
    mode: str
    seed: Optional[int]
    note: str
    metrics_path: Path
    patches_path: Optional[Path] = None
    verified_path: Optional[Path] = None

    def build_summary(self) -> Dict[str, Any]:
        for candidate in (self.metrics_path, self.patches_path, self.verified_path):
            if candidate is not None and not _artifact_exists(candidate):
                raise FileNotFoundError(f"Required artifact missing: {candidate}")

        metrics = _load_json(self.metrics_path)
        proposer_stats = _summarise_patches(self.patches_path)
        verifier_stats = _summarise_verified(self.verified_path)
        acceptance = _derive_acceptance(metrics)

        median_ops = metrics.get("median_patch_ops")
        if median_ops is None:
            median_ops = proposer_stats.get("median_patch_ops")

        return {
            "dataset": self.dataset,
            "mode": self.mode,
            "seed": self.seed,
            "note": self.note,
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
                "metrics": _rel_path(self.metrics_path),
                "patches": _rel_path(self.patches_path),
                "verified": _rel_path(self.verified_path),
            },
        }


def _load_json(path: Path) -> Any:
    with _open_json(path) as handle:
        return json.load(handle)


def _artifact_exists(path: Path) -> bool:
    if path.exists():
        return True
    gz_path = path.with_suffix(path.suffix + ".gz")
    return gz_path.exists()


def _open_json(path: Path):
    if path.exists():
        return path.open("r", encoding="utf-8")
    gz_path = path.with_suffix(path.suffix + ".gz")
    if gz_path.exists():
        return gzip.open(gz_path, "rt", encoding="utf-8")
    raise FileNotFoundError(path)


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
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    if lower == upper:
        return lower_value
    return lower_value + (upper_value - lower_value) * (rank - lower)


def _summarise_verified(path: Optional[Path]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"count": 0, "median_ms": None, "p95_ms": None}
    if path is None or not path.exists():
        return summary

    data = _load_json(path)
    if not isinstance(data, Iterable):
        return summary

    latencies: List[float] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        latency = entry.get("total_latency_ms")
        if latency is None:
            latency = entry.get("latency_ms")
        if latency is None:
            latency = entry.get("verify_latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))

    if latencies:
        summary["median_ms"] = round(_safe_median(latencies), 2)
        summary["p95_ms"] = round(_percentile(latencies, 95.0), 2)
    summary["count"] = len(latencies)
    return summary


def _summarise_patches(path: Optional[Path]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "count": 0,
        "median_ms": None,
        "p95_ms": None,
        "token_usage": None,
        "median_patch_ops": None,
    }
    if path is None or not path.exists():
        return summary

    data = _load_json(path)
    if not isinstance(data, Iterable):
        return summary

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
        if latency is None:
            latency = entry.get("latency_ms")
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

    if latencies:
        summary["median_ms"] = round(_safe_median(latencies), 2)
        summary["p95_ms"] = round(_percentile(latencies, 95.0), 2)
    summary["count"] = len(latencies)

    if patch_lengths:
        summary["median_patch_ops"] = round(
            _safe_median([float(length) for length in patch_lengths]),
            2,
        )

    if usage_samples:
        summary["token_usage"] = {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
            "mean_per_patch": total_tokens / usage_samples if usage_samples else 0.0,
        }

    return summary


def _derive_acceptance(metrics: Dict[str, Any]) -> Dict[str, Optional[float]]:
    total = metrics.get("detections") or metrics.get("total")
    accepted = metrics.get("accepted")
    if accepted is None:
        accepted = metrics.get("auto_fix")

    rate = metrics.get("auto_fix_rate")
    if rate is None and accepted is not None and total:
        rate = float(accepted) / float(total)

    return {
        "total": int(total) if isinstance(total, (int, float)) else None,
        "accepted": int(accepted) if isinstance(accepted, (int, float)) else None,
        "rate": float(rate) if isinstance(rate, (int, float)) else None,
    }


def _rel_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    return str(path.relative_to(ROOT))


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
    return "".join(replacements.get(char, char) for char in text)


def _format_acceptance_latex(entry: Dict[str, Any]) -> str:
    accepted = entry.get("accepted")
    total = entry.get("total")
    rate = entry.get("acceptance_rate")
    if accepted is None or total is None:
        return "n/a"
    if rate is None or rate != rate:
        return f"{accepted}/{total}"
    percentage = f"{rate * 100:.2f}"
    return rf"{accepted}/{total} ({percentage}\%)"


def _format_note_latex(note: str) -> str:
    return _escape_latex(note)


def _write_summary_json(results: List[Dict[str, Any]]) -> None:
    output_path = DATA_DIR / "eval" / "unified_eval_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def _write_markdown(results: List[Dict[str, Any]]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
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
        sources = [
            f"`{path}`"
            for key, path in entry["sources"].items()
            if path is not None
        ]
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

    (DOCS_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_latex(results: List[Dict[str, Any]]) -> None:
    lines = [
        r"\begin{tabularx}{\textwidth}{@{}l c c c c c X@{}}",
        r"\toprule",
        r"\textbf{Corpus (mode)} & \textbf{Seed} & \textbf{Acceptance} & \textbf{Median proposer (ms)} & \textbf{Median verifier (ms)} & \textbf{Verifier P95 (ms)} & \textbf{Notes} \\",
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

        row = rf"{dataset} ({mode}) & {seed} & {acceptance} & {proposer} & {verifier} & {verifier_p95} & {note} \\"
        lines.append(row)

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabularx}",
        ]
    )

    (DOCS_DIR / "tables.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_results() -> List[Dict[str, Any]]:
    configs: List[DatasetConfig] = [
        DatasetConfig(
            dataset="Supported 1.264k",
            mode="rules",
            seed=1337,
            note="Curated Helm/Operator corpus with host-mount normalisation.",
            metrics_path=DATA_DIR / "batch_runs" / "secondary_supported" / "metrics_rules.json",
            patches_path=DATA_DIR / "batch_runs" / "secondary_supported" / "patches_rules.json",
            verified_path=DATA_DIR / "batch_runs" / "secondary_supported" / "verified_rules.json",
        ),
        DatasetConfig(
            dataset="Supported 5k",
            mode="rules",
            seed=1337,
            note="Extended supported corpus (5,000 curated manifests).",
            metrics_path=DATA_DIR / "metrics_rules_5000.json",
            patches_path=DATA_DIR / "patches_rules_5000.json",
            verified_path=DATA_DIR / "verified_rules_5000.json",
        ),
        DatasetConfig(
            dataset="Manifest 1.313k",
            mode="rules",
            seed=1337,
            note="Full manifest slice in deterministic rules mode.",
            metrics_path=DATA_DIR / "metrics_rules_full.json",
            patches_path=DATA_DIR / "patches_rules_full.json",
            verified_path=DATA_DIR / "verified_rules_full.json",
        ),
        DatasetConfig(
            dataset="Manifest 1.313k",
            mode="grok",
            seed=1337,
            note="Grok/xAI with guardrail merge (five TPU jobs rejected).",
            metrics_path=DATA_DIR / "batch_runs" / "grok_full" / "metrics_grok_full.json",
            patches_path=DATA_DIR / "batch_runs" / "grok_full" / "patches_grok_full.json",
            verified_path=DATA_DIR / "batch_runs" / "grok_full" / "verified_grok_full.json",
        ),
        DatasetConfig(
            dataset="Grok-5k",
            mode="grok",
            seed=1337,
            note="Five-thousand manifest sweep with telemetry instrumentation.",
            metrics_path=DATA_DIR / "batch_runs" / "grok_5k" / "metrics_grok5k.json",
            patches_path=DATA_DIR / "batch_runs" / "grok_5k" / "patches_grok5k.json",
            verified_path=DATA_DIR / "batch_runs" / "grok_5k" / "verified_grok5k.json",
        ),
    ]

    return [config.build_summary() for config in configs]


def main() -> None:
    results = _build_results()
    _write_summary_json(results)
    _write_markdown(results)
    _write_latex(results)


if __name__ == "__main__":
    main()
