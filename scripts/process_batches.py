#!/usr/bin/env python3
"""
Sequential batch runner that mirrors the manual Grok 5k workflow.

Example:

    python scripts/process_batches.py \
        --detections-glob "data/batch_runs/grok_5k/detections_grok5k_batch_*.json" \
        --patches-dir data/batch_runs/grok_5k \
        --verified-dir data/batch_runs/grok_5k \
        --config configs/run.yaml \
        --jobs 6
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional


def _build_patch_path(detections_path: Path, patches_dir: Path) -> Path:
    name = detections_path.name.replace("detections", "patches")
    return patches_dir / name


def _build_verified_path(detections_path: Path, verified_dir: Path) -> Path:
    name = detections_path.name.replace("detections", "verified")
    return verified_dir / name


def _run(cmd: List[str]) -> None:
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}")


def _iter_detections(glob: str) -> Iterable[Path]:
    paths = sorted(Path().glob(glob))
    if not paths:
        raise FileNotFoundError(f"No detection batches match {glob}")
    return paths


def process_batches(
    detections_glob: str,
    config: Path,
    patches_dir: Path,
    verified_dir: Path,
    jobs: int,
    proposer_extra: Optional[List[str]],
    verifier_extra: Optional[List[str]],
    *,
    resume: bool,
    run_proposer: bool,
    run_verifier: bool,
) -> None:
    detections_paths = list(_iter_detections(detections_glob))

    patches_dir.mkdir(parents=True, exist_ok=True)
    verified_dir.mkdir(parents=True, exist_ok=True)

    for index, detections_path in enumerate(detections_paths, start=1):
        suffix = detections_path.stem.split("_batch_")[-1]
        patch_path = _build_patch_path(detections_path, patches_dir)
        verified_path = _build_verified_path(detections_path, verified_dir)

        if run_proposer:
            if resume and patch_path.exists():
                print(f"[skip] proposer batch {suffix} -> {patch_path}")
            else:
                print(f"[propose] ({index}/{len(detections_paths)}) batch {suffix}")
                cmd = [
                    sys.executable,
                    "-m",
                    "src.proposer.cli",
                    "--detections",
                    str(detections_path),
                    "--out",
                    str(patch_path),
                    "--config",
                    str(config),
                    "--jobs",
                    str(jobs),
                ]
                if proposer_extra:
                    cmd.extend(proposer_extra)
                _run(cmd)

        if run_verifier:
            if resume and verified_path.exists():
                print(f"[skip] verifier batch {suffix} -> {verified_path}")
                continue
            if not patch_path.exists():
                raise FileNotFoundError(f"Patches missing for batch {suffix}: {patch_path}")
            print(f"[verify] ({index}/{len(detections_paths)}) batch {suffix}")
            cmd = [
                sys.executable,
                "-m",
                "src.verifier.cli",
                "--patches",
                str(patch_path),
                "--detections",
                str(detections_path),
                "--out",
                str(verified_path),
            ]
            if verifier_extra:
                cmd.extend(verifier_extra)
            _run(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sequential proposer/verifier batch runner.")
    parser.add_argument("--detections-glob", type=str, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--patches-dir", type=Path, required=True)
    parser.add_argument("--verified-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume", action="store_true", help="Skip batches whose outputs exist.")
    parser.add_argument(
        "--proposer-extra",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed after '--' to the proposer CLI.",
    )
    parser.add_argument(
        "--verifier-extra",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed after '--' to the verifier CLI.",
    )
    parser.add_argument("--propose-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.propose_only and args.verify_only:
        raise ValueError("Cannot pass both --propose-only and --verify-only")

    proposer_extra = []
    if args.proposer_extra:
        proposer_extra.extend(args.proposer_extra)

    verifier_extra = []
    if args.verifier_extra:
        verifier_extra.extend(args.verifier_extra)

    run_proposer = not args.verify_only
    run_verifier = not args.propose_only

    process_batches(
        detections_glob=args.detections_glob,
        config=args.config,
        patches_dir=args.patches_dir,
        verified_dir=args.verified_dir,
        jobs=args.jobs,
        proposer_extra=proposer_extra,
        verifier_extra=verifier_extra,
        resume=args.resume,
        run_proposer=run_proposer,
        run_verifier=run_verifier,
    )


if __name__ == "__main__":  # pragma: no cover
    main()

