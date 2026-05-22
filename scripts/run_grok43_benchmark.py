#!/usr/bin/env python3
"""Namespaced Grok 4.3 benchmark wrapper for exact-size slices."""

from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import verifier_report
from src.eval.metrics import run as metrics_run


DEFAULT_SOURCE_GLOB = "data/batch_runs/grok_5k/detections_grok5k_batch_*.json"
DEFAULT_CONFIG = Path("configs/run_grok.yaml")
DEFAULT_POLICIES_DIR = Path("data/policies/kyverno")
DEFAULT_KUBE_LINTER_CMD = "tmp/tool-cache/bin/kube-linter"
DEFAULT_KYVERNO_CMD = "tmp/tool-cache/bin/kyverno"
MODEL_NAME = "grok-4.3"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

CommandRunner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[Any]]


@dataclass(frozen=True)
class BenchmarkOptions:
    run_id: str
    limit: int
    batch_size: int = 50
    jobs: int = 1
    resume: bool = False
    source_glob: str = DEFAULT_SOURCE_GLOB
    config: Path = DEFAULT_CONFIG
    policies_dir: Path = DEFAULT_POLICIES_DIR
    kube_linter_cmd: str = DEFAULT_KUBE_LINTER_CMD
    kyverno_cmd: str = DEFAULT_KYVERNO_CMD


@dataclass(frozen=True)
class SourceSelection:
    path: Path
    records_taken: int


@dataclass
class BenchmarkPlan:
    run_dir: Path
    merged_detections: Path
    merged_patches: Path
    merged_verified: Path
    metrics: Path
    failure_summary: Path
    manifest: Path
    detection_batches: list[Path]
    patch_batches: list[Path]
    verified_batches: list[Path]
    source_batches: list[SourceSelection]
    scanners: dict[str, Any] = field(default_factory=dict)
    policy_bundle: dict[str, Any] = field(default_factory=dict)
    commands: list[list[str]] = field(default_factory=list)


def run_benchmark(
    options: BenchmarkOptions,
    *,
    repo_root: Path = REPO_ROOT,
    runner: CommandRunner | None = None,
) -> BenchmarkPlan:
    repo_root = repo_root.resolve()
    runner = runner or _subprocess_runner

    _validate_options(options)
    config_path = _repo_path(repo_root, options.config)
    policies_dir = _repo_path(repo_root, options.policies_dir)
    _validate_grok_config(config_path)
    if not policies_dir.is_dir():
        raise FileNotFoundError(f"Policies directory not found: {_display_path(policies_dir, repo_root)}")
    _preflight_scanners(options.kube_linter_cmd, options.kyverno_cmd, repo_root=repo_root)
    scanners = _scanner_metadata(options.kube_linter_cmd, options.kyverno_cmd, repo_root=repo_root)
    policy_bundle = _policy_bundle_metadata(policies_dir, repo_root=repo_root)

    run_dir = _run_dir(repo_root, options.run_id)
    _prepare_run_dir(run_dir, resume=options.resume)

    prefix = f"grok43_limit_{options.limit}"
    merged_detections = run_dir / f"detections_{prefix}.json"
    merged_patches = run_dir / f"patches_{prefix}.json"
    merged_verified = run_dir / f"verified_{prefix}.json"
    metrics_path = run_dir / f"metrics_{prefix}.json"
    failure_summary = run_dir / f"failure_summary_{prefix}.md"
    manifest = run_dir / f"run_manifest_{prefix}.json"

    records, source_batches = select_records(
        source_glob=options.source_glob,
        limit=options.limit,
        repo_root=repo_root,
    )
    detection_batches = write_detection_inputs(
        records,
        run_dir=run_dir,
        prefix=prefix,
        batch_size=options.batch_size,
        resume=options.resume,
    )

    patch_batches = [run_dir / path.name.replace("detections_", "patches_") for path in detection_batches]
    verified_batches = [run_dir / path.name.replace("detections_", "verified_") for path in detection_batches]

    plan = BenchmarkPlan(
        run_dir=run_dir,
        merged_detections=merged_detections,
        merged_patches=merged_patches,
        merged_verified=merged_verified,
        metrics=metrics_path,
        failure_summary=failure_summary,
        manifest=manifest,
        detection_batches=detection_batches,
        patch_batches=patch_batches,
        verified_batches=verified_batches,
        source_batches=source_batches,
        scanners=scanners,
        policy_bundle=policy_bundle,
    )

    _run_proposer_batches(
        plan,
        config_path=config_path,
        jobs=options.jobs,
        resume=options.resume,
        repo_root=repo_root,
        runner=runner,
    )
    _run_verifier_batches(
        plan,
        policies_dir=policies_dir,
        kube_linter_cmd=options.kube_linter_cmd,
        kyverno_cmd=options.kyverno_cmd,
        jobs=options.jobs,
        resume=options.resume,
        repo_root=repo_root,
        runner=runner,
    )

    _merge_json_arrays(plan.detection_batches, plan.merged_detections, run_dir=run_dir, overwrite=options.resume)
    _merge_json_arrays(plan.patch_batches, plan.merged_patches, run_dir=run_dir, overwrite=options.resume)
    _merge_json_arrays(plan.verified_batches, plan.merged_verified, run_dir=run_dir, overwrite=options.resume)

    _assert_under(plan.metrics, run_dir)
    metrics_run(
        detections=plan.merged_detections,
        patches=plan.merged_patches,
        verified=plan.merged_verified,
        out=plan.metrics,
    )
    _write_failure_summary(plan.merged_verified, plan.failure_summary, run_dir=run_dir)
    _write_manifest(plan, options=options, repo_root=repo_root)
    return plan


def select_records(
    *,
    source_glob: str,
    limit: int,
    repo_root: Path = REPO_ROOT,
) -> tuple[list[dict[str, Any]], list[SourceSelection]]:
    if limit < 1:
        raise ValueError("--limit must be at least 1")

    records: list[dict[str, Any]] = []
    source_batches: list[SourceSelection] = []
    remaining = limit

    for path in _source_batch_paths(source_glob, repo_root=repo_root):
        batch = _load_json_array(path)
        take = min(remaining, len(batch))
        if take:
            for record in batch[:take]:
                records.append(_self_contained_record(record, source_path=path, repo_root=repo_root))
            source_batches.append(SourceSelection(path=path, records_taken=take))
            remaining -= take
        if remaining == 0:
            break

    if len(records) != limit:
        available = limit - remaining
        raise ValueError(f"Requested --limit {limit}, but only {available} detection records were available")
    return records, source_batches


def write_detection_inputs(
    records: Sequence[dict[str, Any]],
    *,
    run_dir: Path,
    prefix: str,
    batch_size: int,
    resume: bool,
) -> list[Path]:
    if batch_size < 1:
        raise ValueError("--batch-size must be at least 1")

    detection_batches: list[Path] = []
    for index, start in enumerate(range(0, len(records), batch_size)):
        chunk = list(records[start : start + batch_size])
        path = run_dir / f"detections_{prefix}_batch_{index:03d}.json"
        _write_or_validate_json_array(path, chunk, run_dir=run_dir, resume=resume)
        detection_batches.append(path)

    return detection_batches


def _run_proposer_batches(
    plan: BenchmarkPlan,
    *,
    config_path: Path,
    jobs: int,
    resume: bool,
    repo_root: Path,
    runner: CommandRunner,
) -> None:
    for detections_path, patch_path in zip(plan.detection_batches, plan.patch_batches):
        _assert_under(patch_path, plan.run_dir)
        if patch_path.exists() and resume:
            continue
        if patch_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing artifact: {_display_path(patch_path, repo_root)}")
        command = [
            sys.executable,
            "-m",
            "src.proposer.cli",
            "--detections",
            _display_path(detections_path, repo_root),
            "--out",
            _display_path(patch_path, repo_root),
            "--config",
            _display_path(config_path, repo_root),
            "--jobs",
            str(jobs),
        ]
        _execute(command, repo_root=repo_root, runner=runner)
        plan.commands.append(command)
        if not patch_path.exists():
            raise FileNotFoundError(f"Proposer did not create expected artifact: {_display_path(patch_path, repo_root)}")


def _run_verifier_batches(
    plan: BenchmarkPlan,
    *,
    policies_dir: Path,
    kube_linter_cmd: str,
    kyverno_cmd: str,
    jobs: int,
    resume: bool,
    repo_root: Path,
    runner: CommandRunner,
) -> None:
    for detections_path, patch_path, verified_path in zip(
        plan.detection_batches,
        plan.patch_batches,
        plan.verified_batches,
    ):
        _assert_under(verified_path, plan.run_dir)
        if verified_path.exists() and resume:
            continue
        if verified_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing artifact: {_display_path(verified_path, repo_root)}")
        if not patch_path.exists():
            raise FileNotFoundError(f"Patches missing for verifier: {_display_path(patch_path, repo_root)}")
        command = [
            sys.executable,
            "-m",
            "src.verifier.cli",
            "--patches",
            _display_path(patch_path, repo_root),
            "--detections",
            _display_path(detections_path, repo_root),
            "--out",
            _display_path(verified_path, repo_root),
            "--include-errors",
            "--enable-rescan",
            "--policies-dir",
            _display_path(policies_dir, repo_root),
            "--kube-linter-cmd",
            kube_linter_cmd,
            "--kyverno-cmd",
            kyverno_cmd,
            "--no-require-kubectl",
            "--jobs",
            str(jobs),
        ]
        _execute(command, repo_root=repo_root, runner=runner)
        plan.commands.append(command)
        if not verified_path.exists():
            raise FileNotFoundError(f"Verifier did not create expected artifact: {_display_path(verified_path, repo_root)}")


def _write_failure_summary(verified_path: Path, out_path: Path, *, run_dir: Path) -> None:
    _assert_under(out_path, run_dir)
    records = verifier_report.load_records(verified_path)
    report = verifier_report.build_report(records, source=verified_path)
    out_path.write_text(verifier_report.render_markdown(report), encoding="utf-8")


def _write_manifest(plan: BenchmarkPlan, *, options: BenchmarkOptions, repo_root: Path) -> None:
    _assert_under(plan.manifest, plan.run_dir)
    payload = {
        "run_id": options.run_id,
        "model": MODEL_NAME,
        "limit": options.limit,
        "batch_size": options.batch_size,
        "jobs": options.jobs,
        "resume": options.resume,
        "source_glob": options.source_glob,
        "config": _display_path(_repo_path(repo_root, options.config), repo_root),
        "policies_dir": _display_path(_repo_path(repo_root, options.policies_dir), repo_root),
        "kube_linter_cmd": options.kube_linter_cmd,
        "kyverno_cmd": options.kyverno_cmd,
        "scanners": plan.scanners,
        "policy_bundle": plan.policy_bundle,
        "source_batches": [
            {
                "path": _display_path(selection.path, repo_root),
                "records_taken": selection.records_taken,
            }
            for selection in plan.source_batches
        ],
        "outputs": {
            "detections": _display_path(plan.merged_detections, repo_root),
            "patches": _display_path(plan.merged_patches, repo_root),
            "verified": _display_path(plan.merged_verified, repo_root),
            "metrics": _display_path(plan.metrics, repo_root),
            "failure_summary": _display_path(plan.failure_summary, repo_root),
        },
        "commands": plan.commands,
    }
    plan.manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _merge_json_arrays(paths: Sequence[Path], out_path: Path, *, run_dir: Path, overwrite: bool) -> None:
    _assert_under(out_path, run_dir)
    merged: list[Any] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Cannot merge missing artifact: {path}")
        merged.extend(_load_json_array(path))
    _write_json_array(out_path, merged, run_dir=run_dir, overwrite=overwrite)


def _source_batch_paths(source_glob: str, *, repo_root: Path) -> list[Path]:
    pattern = _repo_path(repo_root, Path(source_glob))
    paths = sorted(Path(match).resolve() for match in glob.glob(str(pattern)))
    if not paths:
        raise FileNotFoundError(f"No Grok-5k detection batches match {source_glob}")
    return paths


def _preflight_scanners(kube_linter_cmd: str, kyverno_cmd: str, *, repo_root: Path) -> None:
    missing = [
        name
        for name, command in (
            ("kube-linter", kube_linter_cmd),
            ("kyverno", kyverno_cmd),
        )
        if not _command_available(command, repo_root=repo_root)
    ]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(
            f"Missing verifier rescan binary/binaries before live Grok calls: {missing_text}"
        )


def _command_available(command: str, *, repo_root: Path) -> bool:
    resolved = _resolve_command(command, repo_root=repo_root)
    return bool(resolved is not None and resolved.is_file() and resolved.stat().st_mode & 0o111 != 0)


def _resolve_command(command: str, *, repo_root: Path) -> Path | None:
    candidate = Path(command)
    if candidate.is_absolute():
        return candidate.resolve() if candidate.is_file() else None
    if candidate.parent != Path("."):
        resolved = (repo_root / candidate).resolve()
        return resolved if resolved.is_file() else None
    found = shutil.which(command)
    return Path(found).resolve() if found else None


def _scanner_metadata(kube_linter_cmd: str, kyverno_cmd: str, *, repo_root: Path) -> dict[str, Any]:
    scanners = {
        "kube_linter": _single_scanner_metadata(
            requested_command=kube_linter_cmd,
            version_args=("version",),
            repo_root=repo_root,
        ),
        "kyverno": _single_scanner_metadata(
            requested_command=kyverno_cmd,
            version_args=("version",),
            repo_root=repo_root,
        ),
    }
    for name, payload in scanners.items():
        if payload.get("version_error") or payload.get("version_returncode") != 0 or not payload.get("version_output"):
            detail = payload.get("version_error") or payload.get("version_output") or "empty version output"
            raise RuntimeError(f"{name} version probe failed before live Grok calls: {detail}")
    return scanners


def _single_scanner_metadata(
    *,
    requested_command: str,
    version_args: Sequence[str],
    repo_root: Path,
) -> dict[str, Any]:
    resolved = _resolve_command(requested_command, repo_root=repo_root)
    payload: dict[str, Any] = {
        "requested_command": requested_command,
        "resolved_path": str(resolved) if resolved else None,
        "sha256": None,
        "size_bytes": None,
        "mtime_ns": None,
        "version_command": [str(resolved) if resolved else requested_command, *version_args],
        "version_returncode": None,
        "version_output": "",
        "version_error": None,
    }
    if resolved is None:
        payload["version_error"] = "command not found"
        return payload

    stat = resolved.stat()
    payload["sha256"] = _file_sha256(resolved)
    payload["size_bytes"] = stat.st_size
    payload["mtime_ns"] = stat.st_mtime_ns
    try:
        completed = subprocess.run(
            [str(resolved), *version_args],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        payload["version_error"] = str(exc)
        return payload

    payload["version_returncode"] = completed.returncode
    payload["version_output"] = (completed.stdout or "").strip()
    return payload


def _policy_bundle_metadata(policies_dir: Path, *, repo_root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    bundle_hash = hashlib.sha256()
    for path in sorted(candidate for candidate in policies_dir.rglob("*") if candidate.is_file()):
        relative = _display_path(path, repo_root)
        digest = _file_sha256(path)
        stat = path.stat()
        files.append(
            {
                "path": relative,
                "sha256": digest,
                "size_bytes": stat.st_size,
            }
        )
        bundle_hash.update(relative.encode("utf-8"))
        bundle_hash.update(b"\0")
        bundle_hash.update(digest.encode("ascii"))
        bundle_hash.update(b"\0")

    return {
        "path": _display_path(policies_dir, repo_root),
        "sha256": bundle_hash.hexdigest(),
        "file_count": len(files),
        "files": files,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _self_contained_record(record: Any, *, source_path: Path, repo_root: Path) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"{source_path} contains a non-object detection record")
    result = copy.deepcopy(record)
    if result.get("manifest_yaml") is not None:
        return result

    manifest_path = result.get("manifest_path")
    if not manifest_path:
        raise ValueError(f"Detection {result.get('id', '<missing id>')} missing manifest_yaml and manifest_path")

    candidate = Path(str(manifest_path))
    candidates = [candidate] if candidate.is_absolute() else [
        (source_path.parent / candidate).resolve(),
        (repo_root / candidate).resolve(),
    ]
    for path in candidates:
        if path.exists():
            result["manifest_yaml"] = path.read_text(encoding="utf-8")
            return result
    raise FileNotFoundError(f"Could not resolve manifest_path for detection {result.get('id', '<missing id>')}: {manifest_path}")


def _write_or_validate_json_array(
    path: Path,
    data: Sequence[dict[str, Any]],
    *,
    run_dir: Path,
    resume: bool,
) -> None:
    if not path.exists():
        _write_json_array(path, list(data), run_dir=run_dir, overwrite=False)
        return
    if not resume:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")

    existing = _load_json_array(path)
    if _ids(existing) != _ids(data):
        raise ValueError(f"Existing detection batch does not match requested slice: {path}")


def _write_json_array(path: Path, data: list[Any], *, run_dir: Path, overwrite: bool) -> None:
    _assert_under(path, run_dir)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _ids(records: Sequence[Any]) -> list[str]:
    return [str(record.get("id")) if isinstance(record, dict) else "" for record in records]


def _load_json_array(path: Path) -> list[Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def _execute(command: list[str], *, repo_root: Path, runner: CommandRunner) -> None:
    completed = runner(command, repo_root)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}")


def _subprocess_runner(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(list(command), cwd=cwd)


def _validate_options(options: BenchmarkOptions) -> None:
    if not RUN_ID_RE.match(options.run_id):
        raise ValueError("--run-id must contain only letters, numbers, dots, underscores, and dashes, and must start with a letter or number")
    if options.limit < 1:
        raise ValueError("--limit must be at least 1")
    if options.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if options.jobs < 1:
        raise ValueError("--jobs must be at least 1")


def _validate_grok_config(config_path: Path) -> None:
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    proposer = data.get("proposer") if isinstance(data, dict) else {}
    grok = data.get("grok") if isinstance(data, dict) else {}
    if not isinstance(proposer, dict) or proposer.get("mode") != "grok":
        raise ValueError(f"{config_path} must set proposer.mode to grok")
    if not isinstance(grok, dict) or grok.get("model") != MODEL_NAME:
        raise ValueError(f"{config_path} must set grok.model to {MODEL_NAME}")


def _run_dir(repo_root: Path, run_id: str) -> Path:
    batch_runs_dir = repo_root / "data" / "batch_runs"
    run_dir = batch_runs_dir / run_id
    _assert_under(run_dir, batch_runs_dir)
    return run_dir


def _prepare_run_dir(run_dir: Path, *, resume: bool) -> None:
    if run_dir.exists() and any(run_dir.iterdir()) and not resume:
        raise FileExistsError(f"Run namespace already exists; pass --resume to reuse it: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)


def _repo_path(repo_root: Path, path: Path | str) -> Path:
    candidate = path if isinstance(path, Path) else Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def _assert_under(path: Path, parent: Path) -> None:
    path.resolve().relative_to(parent.resolve())


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an exact-size Grok 4.3 benchmark slice in data/batch_runs/<run-id>/.",
    )
    parser.add_argument("--run-id", required=True, help="Namespace under data/batch_runs/ for this run.")
    parser.add_argument("--limit", type=int, required=True, help="Exact number of Grok-5k detections to benchmark, e.g. 50 or 200.")
    parser.add_argument("--batch-size", type=int, default=50, help="Selected detections per generated batch (default: 50).")
    parser.add_argument("--jobs", type=int, default=1, help="Jobs passed to proposer and verifier (default: 1).")
    parser.add_argument("--resume", action="store_true", help="Reuse an existing run namespace and skip completed batch artifacts.")
    parser.add_argument("--source-glob", default=DEFAULT_SOURCE_GLOB, help="Existing Grok-5k detection batch glob to read.")
    parser.add_argument("--policies-dir", type=Path, default=DEFAULT_POLICIES_DIR, help="Verifier Kyverno policies directory.")
    parser.add_argument("--kube-linter-cmd", default=DEFAULT_KUBE_LINTER_CMD, help="kube-linter command for verifier re-scan.")
    parser.add_argument("--kyverno-cmd", default=DEFAULT_KYVERNO_CMD, help="Kyverno command for verifier re-scan.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    options = BenchmarkOptions(
        run_id=args.run_id,
        limit=args.limit,
        batch_size=args.batch_size,
        jobs=args.jobs,
        resume=args.resume,
        source_glob=args.source_glob,
        policies_dir=args.policies_dir,
        kube_linter_cmd=args.kube_linter_cmd,
        kyverno_cmd=args.kyverno_cmd,
    )
    plan = run_benchmark(options)
    print(f"Wrote Grok 4.3 benchmark artifacts to {_display_path(plan.run_dir, REPO_ROOT)}")
    print(f"Metrics: {_display_path(plan.metrics, REPO_ROOT)}")
    print(f"Failure summary: {_display_path(plan.failure_summary, REPO_ROOT)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
