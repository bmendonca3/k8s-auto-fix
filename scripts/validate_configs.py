#!/usr/bin/env python3
"""Validate checked-in YAML configuration files."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "configs"

ALLOWED_PROPOSER_MODES = {"rules", "grok", "vendor", "vllm"}
REMOTE_PROPOSER_MODES = {"grok", "vendor", "vllm"}
REQUIRED_BACKEND_KEYS = ("endpoint", "model", "api_key_env")
POLARIS_CONFIG_FILES = {"polaris.yaml", "polaris_webhook_values.yaml"}
LIVE_CLUSTER_FILTERS_FILE = "live_cluster_filters.yaml"


def default_config_paths() -> list[Path]:
    """Return checked-in YAML configs in a stable order."""
    return sorted(CONFIG_DIR.glob("*.yaml"))


def validate_paths(paths: Sequence[Path]) -> dict[Path, list[str]]:
    """Validate each path and return issues keyed by path."""
    return {path: validate_file(path) for path in paths}


def validate_file(path: Path) -> list[str]:
    """Validate one YAML config file."""
    data, issues = _load_yaml(path)
    if issues:
        return issues

    if path.name == LIVE_CLUSTER_FILTERS_FILE:
        return _validate_live_cluster_filters(data)
    if path.name in POLARIS_CONFIG_FILES:
        return _validate_mapping(data, "Polaris config")
    if isinstance(data, Mapping) and "proposer" in data:
        return _validate_proposer_config(data)
    return ["no validation rule matched this YAML config"]


def _load_yaml(path: Path) -> tuple[Any, list[str]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle), []
    except FileNotFoundError:
        return None, [f"file not found: {path}"]
    except yaml.YAMLError as exc:
        return None, [f"YAML parse error: {exc}"]


def _validate_mapping(data: Any, label: str) -> list[str]:
    if not isinstance(data, Mapping):
        return [f"{label} must be a YAML mapping"]
    return []


def _validate_live_cluster_filters(data: Any) -> list[str]:
    if not isinstance(data, list):
        return ["live_cluster_filters must be a YAML list"]
    return []


def _validate_proposer_config(data: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []

    proposer = data.get("proposer")
    if not isinstance(proposer, Mapping):
        issues.append("proposer must be a YAML mapping")
        mode = None
    else:
        mode = proposer.get("mode")

    mode_lower = mode.lower() if isinstance(mode, str) else None
    if mode_lower not in ALLOWED_PROPOSER_MODES:
        allowed = ", ".join(sorted(ALLOWED_PROPOSER_MODES))
        issues.append(f"proposer.mode must be one of: {allowed}")

    max_attempts = data.get("max_attempts")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        issues.append("max_attempts must be a positive integer")

    issues.extend(_validate_retry_budgets(data.get("retry_budgets"), "retry_budgets"))
    if isinstance(proposer, Mapping):
        issues.extend(
            _validate_retry_budgets(
                proposer.get("retry_budgets"), "proposer.retry_budgets"
            )
        )

    for backend_name in sorted(REMOTE_PROPOSER_MODES):
        backend = data.get(backend_name)
        selected_backend = backend_name == mode_lower
        if backend is None:
            if selected_backend:
                issues.append(f"{backend_name} backend block is required for {backend_name} mode")
            continue
        if not isinstance(backend, Mapping):
            issues.append(f"{backend_name} backend must be a YAML mapping")
            continue
        missing = [
            key
            for key in REQUIRED_BACKEND_KEYS
            if not isinstance(backend.get(key), str) or not backend.get(key).strip()
        ]
        if missing:
            issues.append(f"{backend_name} backend missing non-empty keys: {', '.join(missing)}")

    return issues


def _validate_retry_budgets(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return [f"{label} must be a YAML mapping"]

    issues: list[str] = []
    for key, budget in value.items():
        if not isinstance(key, str) or not key.strip():
            issues.append(f"{label} keys must be non-empty strings")
            continue
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            issues.append(f"{label}.{key} must be a positive integer")
    return issues


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def print_report(results: Mapping[Path, list[str]]) -> None:
    print("Config validation report")
    error_count = 0
    for path, issues in results.items():
        label = _relative(path)
        if not issues:
            print(f"OK   {label}")
            continue
        error_count += len(issues)
        print(f"FAIL {label}")
        for issue in issues:
            print(f"  - {issue}")
    if error_count:
        print(f"Result: {error_count} error(s)")
    else:
        print(f"Result: {len(results)} file(s) valid")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate checked-in YAML config structure.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional YAML config paths. Defaults to configs/*.yaml.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = list(args.paths) if args.paths else default_config_paths()
    results = validate_paths(paths)
    print_report(results)
    return 1 if any(results.values()) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
