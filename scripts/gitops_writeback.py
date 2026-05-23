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
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO
from urllib.parse import urlparse

import jsonpatch
import yaml


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply accepted patches as a PR")
    p.add_argument("--detections", type=Path, default=Path("data/detections.json"))
    p.add_argument("--verified", type=Path, default=Path("data/verified.json"))
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--branch", type=str, default="k8s-auto-fix/patches")
    p.add_argument("--create-pr", action="store_true", help="Open a pull request with gh after committing.")
    p.add_argument("--no-pr", action="store_true", help="Deprecated compatibility flag; PR creation is opt-in.")
    p.add_argument("--require-kubectl", action="store_true")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a writeback plan without changing files, branches, commits, or PRs.",
    )
    p.add_argument(
        "--plan-out",
        type=Path,
        help="Write the writeback plan as JSON and exit without changing git state.",
    )
    return p.parse_args(argv)


def load_json_array(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def by_id(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in records:
        rid = str(r.get("id") or r.get("patch_id") or r.get("detection_id") or "").strip()
        if rid:
            out[rid] = r
    return out


def accepted_patch(entry: Dict[str, Any]) -> bool:
    return bool(entry.get("accepted", entry.get("ok", False))) or (
        bool(entry.get("ok_policy"))
        and bool(entry.get("ok_schema"))
        and bool(entry.get("ok_safety", True))
    )


def patch_id(entry: Dict[str, Any]) -> str:
    return str(entry.get("id") or entry.get("patch_id") or "").strip()


def patch_ops(entry: Dict[str, Any]) -> Any:
    return entry.get("patch") or entry.get("patch_ops")


def yaml_document_index(entry: Dict[str, Any], detection: Dict[str, Any]) -> int:
    for source in (entry, detection):
        for key in ("document_index", "doc_index", "yaml_document_index"):
            value = source.get(key)
            if value is None:
                continue
            try:
                index = int(value)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"Invalid YAML document index {value!r}") from exc
            if index < 0:
                raise RuntimeError(f"Invalid negative YAML document index {index}")
            return index
    return 0


def render_patched_yaml(
    text: str,
    patch_ops_value: List[Dict[str, Any]],
    label: str,
    *,
    document_index: int = 0,
) -> str:
    docs = list(yaml.safe_load_all(text))
    if not docs:
        raise RuntimeError(f"No YAML documents in {label}")
    if document_index >= len(docs):
        raise RuntimeError(
            f"YAML document index {document_index} out of range for {label} ({len(docs)} document(s))"
        )
    doc = docs[document_index]
    patched = jsonpatch.apply_patch(doc, patch_ops_value, in_place=False)
    docs[document_index] = patched
    return yaml.safe_dump_all(docs, sort_keys=False)


def apply_patch_to_file(
    path: Path,
    patch_ops_value: List[Dict[str, Any]],
    *,
    document_index: int = 0,
) -> None:
    text = path.read_text(encoding="utf-8")
    patched = render_patched_yaml(
        text,
        patch_ops_value,
        str(path),
        document_index=document_index,
    )
    path.write_text(patched, encoding="utf-8")


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)


def resolve_manifest_path(repo: Path, manifest_path: str) -> tuple[Path, Path, Optional[str]]:
    raw_path = Path(manifest_path)
    candidate = raw_path if raw_path.is_absolute() else repo / raw_path
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return candidate, candidate, f"could not resolve path: {exc}"
    try:
        resolved.relative_to(repo)
    except ValueError:
        return candidate, resolved, f"resolved outside repo root: {resolved}"
    return candidate, resolved, None


def relative_display_path(repo: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def skip_entry(
    entry: Dict[str, Any],
    reason: str,
    *,
    manifest_path: Optional[str] = None,
    path: Optional[str] = None,
    detail: Optional[str] = None,
    index: Optional[int] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": patch_id(entry) or None,
        "status": "skipped",
        "reason": reason,
    }
    if index is not None:
        out["verified_index"] = index
    if manifest_path is not None:
        out["manifest_path"] = manifest_path
    if path is not None:
        out["path"] = path
    if detail:
        out["detail"] = detail
    return out


def build_writeback_plan(
    repo: Path,
    detections: List[Dict[str, Any]],
    verified: List[Dict[str, Any]],
) -> Dict[str, Any]:
    repo = repo.resolve()
    det_index = by_id(detections)
    entries: List[Dict[str, Any]] = []
    virtual_files: Dict[Path, str] = {}

    for index, entry in enumerate(verified):
        rid = patch_id(entry)
        det = det_index.get(rid) or {}
        detected_manifest_path = det.get("manifest_path")
        manifest_path = detected_manifest_path if isinstance(detected_manifest_path, str) else None

        if not accepted_patch(entry):
            entries.append(
                skip_entry(
                    entry,
                    "rejected_patch",
                    manifest_path=manifest_path,
                    index=index,
                )
            )
            continue

        ops = patch_ops(entry)
        if not rid:
            entries.append(skip_entry(entry, "missing_patch_id", index=index))
            continue
        if not isinstance(ops, list):
            entries.append(
                skip_entry(
                    entry,
                    "invalid_patch",
                    detail="patch must be a JSON Patch operation list",
                    index=index,
                )
            )
            continue
        if not manifest_path or not manifest_path.strip():
            entries.append(skip_entry(entry, "missing_manifest_path", index=index))
            continue

        candidate, resolved, unsafe_reason = resolve_manifest_path(repo, manifest_path)
        display_path = relative_display_path(repo, resolved)
        if unsafe_reason:
            entries.append(
                skip_entry(
                    entry,
                    "unsafe_outside_repo_path",
                    manifest_path=manifest_path,
                    path=display_path,
                    detail=unsafe_reason,
                    index=index,
                )
            )
            continue
        if not candidate.exists():
            entries.append(
                skip_entry(
                    entry,
                    "missing_file",
                    manifest_path=manifest_path,
                    path=display_path,
                    detail="file does not exist",
                    index=index,
                )
            )
            continue

        try:
            current_text = virtual_files.get(resolved)
            if current_text is None:
                current_text = candidate.read_text(encoding="utf-8")
            document_index = yaml_document_index(entry, det)
            virtual_files[resolved] = render_patched_yaml(
                current_text,
                ops,
                display_path,
                document_index=document_index,
            )
        except Exception as exc:  # noqa: BLE001
            entries.append(
                skip_entry(
                    entry,
                    "invalid_patch_application",
                    manifest_path=manifest_path,
                    path=display_path,
                    detail=str(exc),
                    index=index,
                )
            )
            continue

        entries.append(
            {
                "id": rid,
                "status": "would_modify",
                "manifest_path": manifest_path,
                "path": display_path,
                "abs_path": str(resolved),
                "document_index": document_index,
                "verified_index": index,
            }
        )

    would_modify = [entry for entry in entries if entry["status"] == "would_modify"]
    skipped = [entry for entry in entries if entry["status"] == "skipped"]
    files_would_modify = sorted({entry["path"] for entry in would_modify})
    return {
        "repo_root": str(repo),
        "summary": {
            "would_modify": len(would_modify),
            "skipped": len(skipped),
            "files_would_modify": len(files_would_modify),
        },
        "files_would_modify": files_would_modify,
        "would_modify": would_modify,
        "skipped": skipped,
        "entries": entries,
    }


def print_plan(plan: Dict[str, Any], stdout: TextIO) -> None:
    summary = plan["summary"]
    stdout.write("GitOps writeback plan (dry run)\n")
    stdout.write(f"Repo root: {plan['repo_root']}\n")
    stdout.write(
        f"Would modify {summary['files_would_modify']} file(s) "
        f"across {summary['would_modify']} patch(es).\n"
    )
    for item in plan["would_modify"]:
        stdout.write(f"  - {item['path']} (id={item['id']})\n")
    stdout.write(f"Skipped {summary['skipped']} patch(es).\n")
    for item in plan["skipped"]:
        target = item.get("path") or item.get("manifest_path") or "<unknown>"
        detail = f": {item['detail']}" if item.get("detail") else ""
        stdout.write(f"  - {target} (id={item.get('id') or '<missing>'}): {item['reason']}{detail}\n")


def print_skips(plan: Dict[str, Any], stdout: TextIO) -> None:
    for item in plan["skipped"]:
        target = item.get("path") or item.get("manifest_path") or "<unknown>"
        detail = f": {item['detail']}" if item.get("detail") else ""
        stdout.write(f"[skip] {target} (id={item.get('id') or '<missing>'}): {item['reason']}{detail}\n")


def target_file_is_clean(repo: Path, path: Path) -> tuple[bool, Optional[str]]:
    relative = relative_display_path(repo, path)
    worktree = run(["git", "diff", "--quiet", "--", relative], cwd=repo, check=False)
    if worktree.returncode != 0:
        return False, "unstaged changes"
    staged = run(["git", "diff", "--cached", "--quiet", "--", relative], cwd=repo, check=False)
    if staged.returncode != 0:
        return False, "staged changes"
    return True, None


def filter_dirty_targets(plan: Dict[str, Any], repo: Path) -> Dict[str, Any]:
    clean_would_modify: List[Dict[str, Any]] = []
    skipped = list(plan["skipped"])
    entries: List[Dict[str, Any]] = []
    dirty_by_verified_index: set[int] = set()

    for item in plan["would_modify"]:
        clean, detail = target_file_is_clean(repo, Path(item["abs_path"]))
        if clean:
            clean_would_modify.append(item)
            continue
        dirty_by_verified_index.add(int(item["verified_index"]))
        skipped.append(
            {
                "id": item["id"],
                "status": "skipped",
                "reason": "dirty_target_file",
                "manifest_path": item["manifest_path"],
                "path": item["path"],
                "detail": detail,
                "verified_index": item["verified_index"],
            }
        )

    for item in plan["entries"]:
        if item.get("status") == "would_modify" and item.get("verified_index") in dirty_by_verified_index:
            continue
        entries.append(item)
    entries.extend(item for item in skipped if item.get("reason") == "dirty_target_file")
    files_would_modify = sorted({entry["path"] for entry in clean_would_modify})
    updated = dict(plan)
    updated["summary"] = {
        "would_modify": len(clean_would_modify),
        "skipped": len(skipped),
        "files_would_modify": len(files_would_modify),
    }
    updated["files_would_modify"] = files_would_modify
    updated["would_modify"] = clean_would_modify
    updated["skipped"] = skipped
    updated["entries"] = entries
    return updated


def verify_modified_files_with_kubectl(repo: Path, modified: Sequence[Path]) -> None:
    for path in modified:
        run(
            ["kubectl", "apply", "--dry-run=server", "-f", str(path)],
            cwd=repo,
        )


def github_host_from_remote(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    remote_url = completed.stdout.strip()
    parsed = urlparse(remote_url)
    host = parsed.hostname
    if host is None:
        match = re.match(r"^(?:[^@]+@)?([^:/]+):", remote_url)
        host = match.group(1) if match else None
    if host in {"github.com", "github.gatech.edu"}:
        return host
    raise RuntimeError(f"Unsupported GitHub remote host for PR creation: {remote_url}")


def create_pull_request(repo: Path, stdout: TextIO) -> None:
    gh = os.environ.get("GH_CLI", "gh")
    try:
        host = github_host_from_remote(repo)
        env = os.environ.copy()
        if host != "github.com":
            env["GH_HOST"] = host
        subprocess.run([gh, "pr", "create", "--fill"], cwd=str(repo), check=False, env=env)
    except FileNotFoundError:
        stdout.write("GitHub CLI not found; push branch and open PR manually.\n")


def main(argv: Optional[Sequence[str]] = None, stdout: TextIO = sys.stdout) -> int:
    args = parse_args(argv)
    repo = args.repo_root.resolve()
    dets = load_json_array(args.detections)
    ver = load_json_array(args.verified)

    plan = build_writeback_plan(repo, dets, ver)

    if args.dry_run or args.plan_out:
        if args.plan_out:
            args.plan_out.parent.mkdir(parents=True, exist_ok=True)
            args.plan_out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print_plan(plan, stdout)
        return 0

    # Ensure we are in a git repo
    run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    plan = filter_dirty_targets(plan, repo)
    if not plan["would_modify"]:
        print_skips(plan, stdout)
        stdout.write("No files modified; exiting\n")
        return 0

    # Create branch
    run(["git", "checkout", "-B", args.branch], cwd=repo)

    print_skips(plan, stdout)
    modified: List[Path] = []
    for plan_entry in plan["would_modify"]:
        entry = ver[plan_entry["verified_index"]]
        ops = patch_ops(entry)
        file_path = Path(plan_entry["abs_path"])
        try:
            apply_patch_to_file(
                file_path,
                ops,
                document_index=int(plan_entry.get("document_index", 0)),
            )
            modified.append(file_path)
        except Exception as exc:  # noqa: BLE001
            stdout.write(f"[skip] {plan_entry['path']} (id={plan_entry['id']}): invalid_patch_application: {exc}\n")

    if not modified:
        stdout.write("No files modified; exiting\n")
        return 0

    if args.require_kubectl:
        verify_modified_files_with_kubectl(repo, modified)

    # Stage and commit
    run(["git", "add"] + [str(p) for p in modified], cwd=repo)
    run(["git", "commit", "-m", "k8s-auto-fix: apply verified patches"], cwd=repo)

    # Try to open PR via gh only when explicitly requested.
    if args.create_pr and not args.no_pr:
        create_pull_request(repo, stdout)
    stdout.write(f"Modified {len(modified)} file(s). Branch {args.branch} is ready.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
