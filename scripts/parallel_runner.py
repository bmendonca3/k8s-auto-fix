#!/usr/bin/env python3
"""
Utility helpers to run proposer / verifier workloads in parallel chunks.

Usage examples:

  # Rules-mode proposer across 8 workers.
  python scripts/parallel_runner.py propose \
      --detections data/detections.json \
      --config configs/run.yaml \
      --out data/patches_parallel.json \
      --jobs 8

  # Parallel verifier (no kubectl) with the merged patches.
  python scripts/parallel_runner.py verify \
      --patches data/patches_parallel.json \
      --detections data/detections.json \
      --out data/verified_parallel.json \
      --jobs 8 \
      --extra-args --include-errors --no-require-kubectl

"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass
class ChunkMeta:
    index: int
    detections_path: Path
    patches_path: Optional[Path]
    output_path: Path


def _chunk_list(data: Sequence, jobs: int) -> Iterable[Tuple[int, Sequence]]:
    if jobs <= 1:
        yield 0, data
        return
    step = math.ceil(len(data) / jobs)
    for idx in range(jobs):
        start = idx * step
        end = min(len(data), start + step)
        if start >= end:
            break
        yield idx, data[start:end]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_subprocess(args: List[str]) -> Tuple[int, str, str, float]:
    start = time.perf_counter()
    proc = subprocess.run(args, capture_output=True, text=True)
    duration = time.perf_counter() - start
    return proc.returncode, proc.stdout, proc.stderr, duration


def _parallel_map(commands: List[List[str]], jobs: int) -> None:
    if jobs <= 1:
        for cmd in commands:
            code, out, err, duration = _run_subprocess(cmd)
            if code != 0:
                raise RuntimeError(f"Command failed ({duration:.2f}s): {' '.join(cmd)}\n{err}")
        return

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        future_map = {
            executor.submit(_run_subprocess, cmd): cmd for cmd in commands
        }
        for future in as_completed(future_map):
            cmd = future_map[future]
            code, out, err, duration = future.result()
            if code != 0:
                raise RuntimeError(
                    f"Command failed ({duration:.2f}s) -> {' '.join(cmd)}\n{err}"
                )


def run_parallel_proposer(
    detections_path: Path,
    config_path: Path,
    out_path: Path,
    jobs: int,
    extra_args: Optional[List[str]],
    workdir: Path,
) -> None:
    detections = json.loads(detections_path.read_text())
    if not detections:
        out_path.write_text("[]", encoding="utf-8")
        return

    temp_root = Path(tempfile.mkdtemp(prefix="parallel_propose_", dir=workdir))
    chunk_meta: List[ChunkMeta] = []
    commands: List[List[str]] = []

    for chunk_index, chunk in _chunk_list(detections, jobs):
        det_file = temp_root / f"detections_chunk_{chunk_index:04d}.json"
        out_file = temp_root / f"patches_chunk_{chunk_index:04d}.json"
        _write_json(det_file, chunk)
        cmd = [
            "python",
            "-m",
            "src.proposer.cli",
            "--detections",
            str(det_file),
            "--out",
            str(out_file),
            "--config",
            str(config_path),
        ]
        if extra_args:
            cmd.extend(extra_args)
        commands.append(cmd)
        chunk_meta.append(ChunkMeta(chunk_index, det_file, None, out_file))

    _parallel_map(commands, jobs)

    merged: List[dict] = []
    for meta in sorted(chunk_meta, key=lambda c: c.index):
        chunk_data = json.loads(meta.output_path.read_text())
        merged.extend(chunk_data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out_path, merged)


def run_parallel_verifier(
    patches_path: Path,
    detections_path: Path,
    out_path: Path,
    jobs: int,
    extra_args: Optional[List[str]],
    workdir: Path,
) -> None:
    patches = json.loads(patches_path.read_text())
    detections = json.loads(detections_path.read_text())
    if not patches:
        out_path.write_text("[]", encoding="utf-8")
        return

    patch_map = {str(p["id"]): p for p in patches if isinstance(p, dict)}
    temp_root = Path(tempfile.mkdtemp(prefix="parallel_verify_", dir=workdir))

    chunk_meta: List[ChunkMeta] = []
    commands: List[List[str]] = []

    for chunk_index, det_chunk in _chunk_list(detections, jobs):
        patch_chunk = [patch_map[str(d["id"])] for d in det_chunk if str(d["id"]) in patch_map]
        det_file = temp_root / f"detections_chunk_{chunk_index:04d}.json"
        patch_file = temp_root / f"patches_chunk_{chunk_index:04d}.json"
        out_file = temp_root / f"verified_chunk_{chunk_index:04d}.json"
        _write_json(det_file, det_chunk)
        _write_json(patch_file, patch_chunk)
        cmd = [
            "python",
            "-m",
            "src.verifier.cli",
            "--patches",
            str(patch_file),
            "--detections",
            str(det_file),
            "--out",
            str(out_file),
        ]
        if extra_args:
            cmd.extend(extra_args)
        commands.append(cmd)
        chunk_meta.append(ChunkMeta(chunk_index, det_file, patch_file, out_file))

    _parallel_map(commands, jobs)

    merged: List[dict] = []
    for meta in sorted(chunk_meta, key=lambda c: c.index):
        chunk_data = json.loads(meta.output_path.read_text())
        merged.extend(chunk_data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out_path, merged)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel runner for proposer/verifier.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    propose_parser = subparsers.add_parser("propose", help="Parallel proposer wrapper.")
    propose_parser.add_argument("--detections", type=Path, required=True)
    propose_parser.add_argument("--config", type=Path, required=True)
    propose_parser.add_argument("--out", type=Path, required=True)
    propose_parser.add_argument("--jobs", type=int, default=4)
    propose_parser.add_argument("--extra-args", nargs=argparse.REMAINDER, default=None)
    propose_parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("./data/batch_runs"),
        help="Working directory for temporary chunk files.",
    )

    verify_parser = subparsers.add_parser("verify", help="Parallel verifier wrapper.")
    verify_parser.add_argument("--patches", type=Path, required=True)
    verify_parser.add_argument("--detections", type=Path, required=True)
    verify_parser.add_argument("--out", type=Path, required=True)
    verify_parser.add_argument("--jobs", type=int, default=4)
    verify_parser.add_argument("--extra-args", nargs=argparse.REMAINDER, default=None)
    verify_parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("./data/batch_runs"),
        help="Working directory for temporary chunk files.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workdir: Path = args.workdir
    workdir.mkdir(parents=True, exist_ok=True)

    if args.command == "propose":
        start = time.perf_counter()
        run_parallel_proposer(
            detections_path=args.detections,
            config_path=args.config,
            out_path=args.out,
            jobs=args.jobs,
            extra_args=args.extra_args,
            workdir=workdir,
        )
        duration = time.perf_counter() - start
        print(f"Proposer finished in {duration:.2f}s -> {args.out}")
    elif args.command == "verify":
        start = time.perf_counter()
        run_parallel_verifier(
            patches_path=args.patches,
            detections_path=args.detections,
            out_path=args.out,
            jobs=args.jobs,
            extra_args=args.extra_args,
            workdir=workdir,
        )
        duration = time.perf_counter() - start
        print(f"Verifier finished in {duration:.2f}s -> {args.out}")
    else:  # pragma: no cover
        raise SystemExit(f"Unknown command {args.command}")


if __name__ == "__main__":  # pragma: no cover
    main()
