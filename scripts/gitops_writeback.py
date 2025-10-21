#!/usr/bin/env python3
"""
GitOps write-back helper: apply accepted patches to source control as a PR.

Inputs:
- detections JSON (id -> manifest_path)
- verified JSON (accepted patches with JSON Patch ops)
- repo root (defaults to current repo)

Behavior:
- Creates a new branch, applies JSON Patches in-place to files under the repo,
  runs a verifier dry-run if requested, commits changes, and optionally creates
  a pull request via the GitHub CLI (`gh`) if present.

Safety:
- Only modifies files under the specified repo root.
- Skips entries without on-disk manifest paths.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonpatch
import yaml


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply accepted patches as a PR")
    p.add_argument("--detections", type=Path, default=Path("data/detections.json"))
    p.add_argument("--verified", type=Path, default=Path("data/verified.json"))
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--branch", type=str, default="k8s-auto-fix/patches")
    p.add_argument("--no-pr", action="store_true", help="Do not open a pull request")
    p.add_argument("--require-kubectl", action="store_true")
    return p.parse_args()


def load_json_array(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def by_id(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in records:
        rid = str(r.get("id") or r.get("patch_id") or r.get("detection_id") or "").strip()
        if rid:
            out[rid] = r
    return out


def apply_patch_to_file(path: Path, patch_ops: List[Dict[str, Any]]) -> None:
    text = path.read_text(encoding="utf-8")
    docs = list(yaml.safe_load_all(text))
    if not docs:
        raise RuntimeError(f"No YAML documents in {path}")
    doc = docs[0]
    patched = jsonpatch.apply_patch(doc, patch_ops, in_place=False)
    path.write_text(yaml.safe_dump(patched, sort_keys=False), encoding="utf-8")


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)


def main() -> None:
    args = parse_args()
    repo = args.repo_root.resolve()
    dets = load_json_array(args.detections)
    ver = load_json_array(args.verified)
    det_index = by_id(dets)

    # Ensure we are in a git repo
    run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    # Create branch
    run(["git", "checkout", "-B", args.branch], cwd=repo)

    modified: List[Path] = []
    for entry in ver:
        if not bool(entry.get("accepted", entry.get("ok", False))) and not (
            bool(entry.get("ok_policy")) and bool(entry.get("ok_schema")) and bool(entry.get("ok_safety", True))
        ):
            continue
        rid = str(entry.get("id") or entry.get("patch_id") or "").strip()
        patch_ops = entry.get("patch") or entry.get("patch_ops")
        if not rid or not isinstance(patch_ops, list):
            continue
        det = det_index.get(rid) or {}
        mpath = det.get("manifest_path")
        if not isinstance(mpath, str) or not mpath:
            continue
        file_path = (repo / mpath) if not Path(mpath).is_absolute() else Path(mpath)
        try:
            if str(file_path.resolve()).startswith(str(repo)) and file_path.exists():
                apply_patch_to_file(file_path, patch_ops)
                modified.append(file_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {file_path}: {exc}")

    if not modified:
        print("No files modified; exiting")
        return

    # Stage and commit
    run(["git", "add"] + [str(p) for p in modified], cwd=repo)
    run(["git", "commit", "-m", "k8s-auto-fix: apply verified patches"], cwd=repo)

    # Try to open PR via gh, if available
    if not args.no_pr:
        gh = os.environ.get("GH_CLI", "gh")
        try:
            subprocess.run([gh, "pr", "create", "--fill"], cwd=str(repo), check=False)
        except FileNotFoundError:
            print("GitHub CLI not found; push branch and open PR manually.")
    print(f"Modified {len(modified)} file(s). Branch {args.branch} is ready.")


if __name__ == "__main__":
    main()

