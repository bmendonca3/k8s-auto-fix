#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_step(args: List[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({' '.join(args)}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def ensure_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Expected artifact missing: {path}")


def load_json(path: Path):
    ensure_file(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    # 1. Detect violations
    detections_path = ROOT / "data" / "detections.json"
    sample_manifests = [
        "data/manifests/001.yaml",
        "data/manifests/002.yaml",
        "data/manifests/003.yaml",
    ]
    detect_args = [
        PYTHON,
        "-m",
        "src.detector.cli",
        "--out",
        str(detections_path),
    ]
    for manifest in sample_manifests:
        detect_args.extend(["--in", manifest])
    run_step(detect_args)

    # 2. Generate patches (rules mode by default)
    patches_path = ROOT / "data" / "patches.json"
    run_step(
        [
            PYTHON,
            "-m",
            "src.proposer.cli",
            "--detections",
            str(detections_path),
            "--out",
            str(patches_path),
            "--config",
            "configs/run_rules.yaml",
        ]
    )

    # 3. Verify patches
    verified_path = ROOT / "data" / "verified.json"
    run_step([
        PYTHON,
        "-m",
        "src.verifier.cli",
        "--patches",
        str(patches_path),
        "--detections",
        str(detections_path),
        "--out",
        str(verified_path),
        "--include-errors",
        "--no-require-kubectl",
    ])

    # 4. Build risk metadata
    risk_path = ROOT / "data" / "risk.json"
    run_step([
        PYTHON,
        "-m",
        "src.risk.cli",
        "--detections",
        str(detections_path),
        "--out",
        str(risk_path),
    ])

    # 5. Schedule accepted patches
    schedule_path = ROOT / "data" / "schedule.json"
    run_step([
        PYTHON,
        "-m",
        "src.scheduler.cli",
        "--verified",
        str(verified_path),
        "--detections",
        str(detections_path),
        "--risk",
        str(risk_path),
        "--out",
        str(schedule_path),
    ])

    # 6. Queue lifecycle
    db_path = ROOT / "data" / "queue.db"
    run_step([PYTHON, "-m", "src.scheduler.queue_cli", "init", "--db", str(db_path)])
    run_step([
        PYTHON,
        "-m",
        "src.scheduler.queue_cli",
        "enqueue",
        "--db",
        str(db_path),
        "--verified",
        str(verified_path),
        "--detections",
        str(detections_path),
        "--risk",
        str(risk_path),
    ])
    next_result = run_step([PYTHON, "-m", "src.scheduler.queue_cli", "next", "--db", str(db_path)])
    try:
        queue_item = json.loads(next_result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - purely diagnostic
        raise RuntimeError(f"Failed to parse queue next output: {next_result.stdout}") from exc

    # Sanity checks on outputs
    verified_records = load_json(verified_path)
    accepted = [record for record in verified_records if record.get("accepted")]
    if not accepted:
        raise RuntimeError("Smoke test failed: verifier produced zero accepted patches.")

    schedule_records = load_json(schedule_path)
    if not schedule_records:
        raise RuntimeError("Smoke test failed: scheduler produced an empty plan.")

    if not isinstance(queue_item, dict) or "id" not in queue_item:
        raise RuntimeError("Smoke test failed: scheduler queue returned malformed item.")

    print(
        json.dumps(
            {
                "detections": len(load_json(detections_path)),
                "accepted": len(accepted),
                "queue_head": queue_item.get("id"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":  # pragma: no cover
    main()
