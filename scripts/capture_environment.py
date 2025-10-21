#!/usr/bin/env python3
"""Capture python packages and versions for reproducibility (task C15)."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture environment metadata")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/repro/environment.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pip_list = subprocess.run(
        ["python", "-m", "pip", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    packages = json.loads(pip_list.stdout)
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
