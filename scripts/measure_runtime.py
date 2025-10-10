#!/usr/bin/env python3
"""Measure proposer and verifier runtime/token usage for a detection batch."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

app = typer.Typer(help="Benchmark proposer/verifier latency and token usage.")


def _load_count(path: Path) -> int:
    records = json.loads(path.read_text(encoding="utf-8"))
    return len(records)


def _aggregate_tokens(patches_path: Path) -> dict[str, float]:
    records = json.loads(patches_path.read_text(encoding="utf-8"))
    prompt = 0.0
    completion = 0.0
    total = 0.0
    for record in records:
        usage: Optional[dict[str, float]] = record.get("model_usage")
        if not usage:
            continue
        prompt += float(usage.get("prompt_tokens", 0.0))
        completion += float(usage.get("completion_tokens", 0.0))
        total += float(usage.get("total_tokens", 0.0))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


@app.command()
def measure(
    detections: Path = typer.Option(Path("data/detections_sampled.json"), help="Input detections JSON."),
    config: Path = typer.Option(Path("configs/run_rules.yaml"), help="Proposer configuration file."),
    patches_out: Path = typer.Option(Path("tmp/patches_benchmark.json"), help="Where to write patches."),
    verified_out: Path = typer.Option(Path("tmp/verified_benchmark.json"), help="Where to write verifier results."),
    jobs: int = typer.Option(4, help="Parallel workers for proposer/verifier."),
    require_kubectl: bool = typer.Option(False, help="Pass through to verifier."),
    include_errors: bool = typer.Option(True, help="Include errors in verifier output."),
) -> None:
    detections = detections.resolve()
    config = config.resolve()
    patches_out = patches_out.resolve()
    verified_out = verified_out.resolve()

    patches_out.parent.mkdir(parents=True, exist_ok=True)
    verified_out.parent.mkdir(parents=True, exist_ok=True)

    det_count = _load_count(detections)

    start = time.perf_counter()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "src.proposer.cli",
            "--detections",
            str(detections),
            "--out",
            str(patches_out),
            "--config",
            str(config),
            "--jobs",
            str(jobs),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    proposer_duration = time.perf_counter() - start

    start = time.perf_counter()
    cmd = [
        sys.executable,
        "-m",
        "src.verifier.cli",
        "--patches",
        str(patches_out),
        "--out",
        str(verified_out),
        "--detections",
        str(detections),
        "--jobs",
        str(jobs),
    ]
    if not require_kubectl:
        cmd.append("--no-require-kubectl")
    if include_errors:
        cmd.append("--include-errors")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    verifier_duration = time.perf_counter() - start

    proposer_per_item = proposer_duration / det_count if det_count else 0.0
    verifier_per_item = verifier_duration / det_count if det_count else 0.0
    token_usage = _aggregate_tokens(patches_out)

    metrics = {
        "detections": det_count,
        "proposer_seconds": round(proposer_duration, 4),
        "proposer_seconds_per_item": round(proposer_per_item, 4),
        "verifier_seconds": round(verifier_duration, 4),
        "verifier_seconds_per_item": round(verifier_per_item, 4),
        "token_usage": token_usage,
    }

    typer.echo(json.dumps(metrics, indent=2))


if __name__ == "__main__":  # pragma: no cover
    app()
