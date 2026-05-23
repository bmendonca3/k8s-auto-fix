#!/usr/bin/env python3
"""Check local prerequisites for common k8s-auto-fix workflows."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MODULES = {
    "yaml": "pyyaml",
    "jsonpatch": "jsonpatch",
    "kubernetes": "kubernetes",
    "rich": "rich",
    "typer": "typer",
    "requests": "requests",
    "httpx": "httpx",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "numpy": "numpy",
    "pandas": "pandas",
    "sklearn": "scikit-learn",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "pytest": "pytest",
}

OPTIONAL_COMMANDS = {
    "kubectl": "server-side dry-run and live-cluster verification",
    "kind": "local Kubernetes fixture cluster",
    "docker": "containerized reproduction and Kind clusters",
    "kube-linter": "detector and verifier scanner checks",
    "kyverno": "Kyverno baseline and policy checks",
}

IMPORTANT_PATHS = [
    "README.md",
    "requirements.txt",
    "Makefile",
    "configs/run.yaml",
    "data/policies/kyverno",
    "infra/fixtures",
    "src/detector/cli.py",
    "src/proposer/cli.py",
    "src/verifier/cli.py",
    "src/scheduler/cli.py",
    "tests",
]


def status(ok: bool, label: str, detail: str = "") -> None:
    marker = "OK" if ok else "MISSING"
    suffix = f" - {detail}" if detail else ""
    print(f"[{marker}] {label}{suffix}")


def check_python() -> bool:
    version = sys.version_info
    ok = version >= (3, 10)
    detail = f"{platform.python_implementation()} {platform.python_version()}"
    status(ok, "Python >= 3.10", detail)
    return ok


def check_modules() -> bool:
    print("\nPython dependencies")
    missing: list[str] = []
    for module, package in REQUIRED_MODULES.items():
        ok = importlib.util.find_spec(module) is not None
        status(ok, package)
        if not ok:
            missing.append(package)
    if missing:
        print("\nInstall missing required packages with: pip install -r requirements.txt")
    return not missing


def check_commands() -> None:
    print("\nOptional external tools")
    for command, purpose in OPTIONAL_COMMANDS.items():
        found = shutil.which(command)
        status(found is not None, command, purpose if found is None else found)


def check_paths() -> bool:
    print("\nRepository paths")
    missing: list[str] = []
    for relative_path in IMPORTANT_PATHS:
        path = REPO_ROOT / relative_path
        ok = path.exists()
        status(ok, relative_path)
        if not ok:
            missing.append(relative_path)
    return not missing


def main() -> int:
    print("k8s-auto-fix environment doctor\n")
    ok = check_python()
    ok = check_modules() and ok
    check_commands()
    ok = check_paths() and ok
    print("\nResult: " + ("ready for local smoke tests" if ok else "setup needs attention"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
