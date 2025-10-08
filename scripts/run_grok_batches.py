#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def iter_batches(detections_glob: str) -> List[Path]:
    return sorted(Path().glob(detections_glob))


def proposer_cmd(detections: Path, out: Path, jobs: int, config: Path) -> List[str]:
    return [
        PYTHON,
        "-m",
        "src.proposer.cli",
        "--detections",
        str(detections),
        "--out",
        str(out),
        "--config",
        str(config),
        "--jobs",
        str(jobs),
    ]


def run_batches(
    detections_glob: str,
    patches_pattern: str,
    *,
    jobs: int,
    config: Path,
    start_after: str | None,
) -> None:
    batches = iter_batches(detections_glob)
    if not batches:
        print(f"[grok-batches] No detection batches match {detections_glob}", file=sys.stderr)
        sys.exit(1)

    skip = bool(start_after)
    for index, detections in enumerate(batches, start=1):
        suffix = "".join(filter(str.isdigit, detections.stem)) or f"{index:05d}"
        if skip:
            if suffix == start_after:
                skip = False
            continue

        patches_path = Path(patches_pattern.format(index=suffix, suffix=suffix))
        if patches_path.exists():
            print(f"[grok-batches] Skipping batch {suffix} (patches already exist)")
            continue

        print(f"[grok-batches] ({index}/{len(batches)}) Proposing batch {suffix} -> {patches_path}")
        patches_path.parent.mkdir(parents=True, exist_ok=True)
        command = proposer_cmd(detections, patches_path, jobs=jobs, config=config)

        completed = subprocess.run(command)
        if completed.returncode != 0:
            raise RuntimeError(
                f"[grok-batches] Batch {suffix} failed with exit code {completed.returncode}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream Grok proposer batches with resume support."
    )
    parser.add_argument(
        "--detections-glob",
        type=str,
        default="data/batch_runs/grok_5k/detections_grok5k_batch_*.json",
        help="Glob for detection batch files.",
    )
    parser.add_argument(
        "--patches-pattern",
        type=str,
        default="data/batch_runs/grok_5k/patches_grok5k_batch_{suffix}.json",
        help="Format string for patch output files (use {suffix}).",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=2,
        help="Parallel workers for proposer CLI (default: 2).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/run.yaml"),
        help="Run configuration file.",
    )
    parser.add_argument(
        "--start-after",
        type=str,
        default=None,
        help="Resume after the given batch suffix (e.g., 5003).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_batches(
        detections_glob=args.detections_glob,
        patches_pattern=args.patches_pattern,
        jobs=args.jobs,
        config=args.config,
        start_after=args.start_after,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
