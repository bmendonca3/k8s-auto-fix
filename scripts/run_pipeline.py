#!/usr/bin/env python3
"""Print or run the lightweight k8s-auto-fix pipeline plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, List, Sequence


DEFAULT_MANIFESTS = (Path("data/manifests"),)


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: tuple[str, ...]


STAGE_OUTPUT_ARGS = {
    "detect": ("detections",),
    "propose": ("patches",),
    "verify": ("verified",),
    "risk": ("risk",),
    "schedule": ("schedule",),
}

STAGE_REMEDIATION_HINTS = {
    "detect": (
        "Confirm manifest inputs and the policies directory exist, then rerun detect on one known-good manifest."
    ),
    "propose": (
        "Confirm detections JSON and proposer config are valid and from the same run, then rerun propose."
    ),
    "verify": (
        "Confirm patches and detections are paired; for dry-run errors, check kubectl/cluster fixtures or rerun without "
        "--require-kubectl for a cluster-free smoke check."
    ),
    "risk": "Confirm detections JSON exists and optional EPSS/KEV files are readable local CSV/JSON inputs.",
    "schedule": (
        "Confirm verified, detections, risk, and optional policy metrics artifacts are valid JSON from the same run."
    ),
}

RETURN_CODE_REMEDIATION_HINTS = {
    2: "Check the stage CLI arguments and config syntax, then rerun the printed command.",
    126: "Check executable permissions for the Python or tool binary used by this stage.",
    127: "Check that the Python executable and required stage tools are installed and on PATH.",
    130: "The stage was interrupted; rerun when ready, using --resume if prior completed outputs are intact.",
    137: "The stage may have exceeded memory; reduce --jobs or rerun a smaller manifest slice.",
}

STAGE_RETURN_CODE_REMEDIATION_HINTS = {
    ("detect", 127): "Install or expose detector scanner dependencies such as kube-linter/kyverno, then rerun detect.",
    ("verify", 127): "Install or expose kubectl when required, or rerun without --require-kubectl for local smoke checks.",
    ("risk", 2): "Check optional --epss-csv and --kev-json paths and formats before rerunning risk scoring.",
    ("schedule", 2): "Check scheduler inputs, especially --policy-metrics JSON when provided, before rerunning schedule.",
}

FAILURE_DIAGNOSTIC_TAIL_CHARS = 1200


def _declared_input_paths(args: argparse.Namespace, step: PipelineStep) -> list[Path]:
    manifests = tuple(args.manifests or DEFAULT_MANIFESTS)
    policies_dir = None if args.no_policies_dir else args.policies_dir

    if step.name == "detect":
        return [*manifests, *([] if policies_dir is None else [policies_dir])]
    if step.name == "propose":
        return [args.detections, args.config]
    if step.name == "verify":
        paths = [args.patches, args.detections]
        if args.enable_rescan and policies_dir is not None:
            paths.append(policies_dir)
        return paths
    if step.name == "risk":
        return [args.detections, *[path for path in (args.epss_csv, args.kev_json) if path is not None]]
    if step.name == "schedule":
        return [
            args.verified,
            args.detections,
            args.risk,
            *([] if args.policy_metrics is None else [args.policy_metrics]),
        ]
    return []


def build_plan(args: argparse.Namespace, *, python: str | None = None) -> List[PipelineStep]:
    """Build the detector -> proposer -> verifier -> risk -> scheduler command plan."""
    python_bin = python or sys.executable
    manifests = tuple(args.manifests or DEFAULT_MANIFESTS)
    policies_dir = None if args.no_policies_dir else args.policies_dir

    detect_cmd = [python_bin, "-m", "src.detector.cli"]
    for path in manifests:
        detect_cmd.extend(["--in", str(path)])
    detect_cmd.extend(["--out", str(args.detections)])
    if policies_dir is not None:
        detect_cmd.extend(["--policies-dir", str(policies_dir)])
    detect_cmd.extend(["--jobs", str(args.jobs)])

    propose_cmd = [
        python_bin,
        "-m",
        "src.proposer.cli",
        "--detections",
        str(args.detections),
        "--out",
        str(args.patches),
        "--config",
        str(args.config),
        "--jobs",
        str(args.jobs),
    ]

    verify_cmd = [
        python_bin,
        "-m",
        "src.verifier.cli",
        "--patches",
        str(args.patches),
        "--detections",
        str(args.detections),
        "--out",
        str(args.verified),
        "--include-errors",
        "--jobs",
        str(args.jobs),
    ]
    verify_cmd.append("--require-kubectl" if args.require_kubectl else "--no-require-kubectl")
    if args.enable_rescan:
        verify_cmd.append("--enable-rescan")
        if policies_dir is not None:
            verify_cmd.extend(["--policies-dir", str(policies_dir)])

    risk_cmd = [
        python_bin,
        "-m",
        "src.risk.cli",
        "--detections",
        str(args.detections),
        "--out",
        str(args.risk),
    ]
    if args.epss_csv is not None:
        risk_cmd.extend(["--epss-csv", str(args.epss_csv)])
    if args.kev_json is not None:
        risk_cmd.extend(["--kev-json", str(args.kev_json)])

    schedule_cmd = [
        python_bin,
        "-m",
        "src.scheduler.cli",
        "--verified",
        str(args.verified),
        "--detections",
        str(args.detections),
        "--risk",
        str(args.risk),
        "--out",
        str(args.schedule),
    ]
    if args.policy_metrics is not None:
        schedule_cmd.extend(["--policy-metrics", str(args.policy_metrics)])

    return [
        PipelineStep("detect", tuple(detect_cmd)),
        PipelineStep("propose", tuple(propose_cmd)),
        PipelineStep("verify", tuple(verify_cmd)),
        PipelineStep("risk", tuple(risk_cmd)),
        PipelineStep("schedule", tuple(schedule_cmd)),
    ]


def format_plan(plan: Iterable[PipelineStep]) -> str:
    lines = []
    for index, step in enumerate(plan, start=1):
        lines.append(f"{index}. {step.name}: {shlex.join(step.command)}")
    return "\n".join(lines)


def _path_or_none(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path)


def build_manifest(
    args: argparse.Namespace,
    plan: Iterable[PipelineStep],
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable reproducibility manifest for a pipeline plan."""
    steps = list(plan)
    manifests = tuple(args.manifests or DEFAULT_MANIFESTS)
    policies_dir = None if args.no_policies_dir else args.policies_dir
    python_executable = steps[0].command[0] if steps else sys.executable

    return {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "run" if args.run else "dry-run",
        "python_executable": python_executable,
        "config_path": str(args.config),
        "jobs": args.jobs,
        "flags": {
            "run": args.run,
            "dry_run": not args.run,
            "require_kubectl": args.require_kubectl,
            "enable_rescan": args.enable_rescan,
            "no_policies_dir": args.no_policies_dir,
        },
        "input_paths": {
            "manifests": [str(path) for path in manifests],
            "policies_dir": _path_or_none(policies_dir),
            "epss_csv": _path_or_none(args.epss_csv),
            "kev_json": _path_or_none(args.kev_json),
            "policy_metrics": _path_or_none(args.policy_metrics),
        },
        "output_paths": {
            "detections": str(args.detections),
            "patches": str(args.patches),
            "verified": str(args.verified),
            "risk": str(args.risk),
            "schedule": str(args.schedule),
        },
        "stages": [
            {
                "name": step.name,
                "command": list(step.command),
                "command_string": shlex.join(step.command),
                "remediation_hint": _remediation_hint(step),
                "input_paths": _stage_input_paths(args, step),
                "input_metadata": [_input_metadata(path) for path in _stage_input_paths(args, step)],
                "output_paths": _stage_output_paths(args, step),
                "output_metadata": [_output_metadata(path) for path in _stage_output_paths(args, step)],
            }
            for step in steps
        ],
    }


def write_manifest(path: Path, args: argparse.Namespace, plan: Iterable[PipelineStep]) -> None:
    manifest = build_manifest(args, plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    path.write_text(manifest_text, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_metadata(path: str) -> dict[str, Any]:
    input_path = Path(path)
    exists = input_path.exists()
    is_file = input_path.is_file()
    is_dir = input_path.is_dir()
    record: dict[str, Any] = {
        "exists": exists,
        "path": path,
        "type": "file" if is_file else "directory" if is_dir else "missing" if not exists else "other",
    }
    if is_file:
        record["sha256"] = _sha256(input_path)
        record["size_bytes"] = input_path.stat().st_size
    return record


def _output_metadata(path: str) -> dict[str, Any]:
    output_path = Path(path)
    record: dict[str, Any] = {
        "exists": output_path.is_file(),
        "path": path,
    }
    if record["exists"]:
        record["sha256"] = _sha256(output_path)
        record["size_bytes"] = output_path.stat().st_size
    return record


def _stage_output_paths(args: argparse.Namespace, step: PipelineStep) -> list[str]:
    return [str(getattr(args, name)) for name in STAGE_OUTPUT_ARGS.get(step.name, ())]


def _stage_input_paths(args: argparse.Namespace, step: PipelineStep) -> list[str]:
    return [str(path) for path in _declared_input_paths(args, step)]


def _remediation_hint_key(step: PipelineStep, returncode: int | None = None) -> str:
    return f"{step.name}:{returncode if returncode is not None else '*'}"


def _remediation_hint(step: PipelineStep, returncode: int | None = None) -> dict[str, str]:
    hint = ""
    if returncode is not None:
        hint = STAGE_RETURN_CODE_REMEDIATION_HINTS.get((step.name, returncode), "")
        hint = hint or RETURN_CODE_REMEDIATION_HINTS.get(returncode, "")
    hint = hint or STAGE_REMEDIATION_HINTS.get(
        step.name,
        "Inspect this stage's declared inputs and rerun the printed command with the same Python executable.",
    )
    return {
        "key": _remediation_hint_key(step, returncode),
        "message": hint,
    }


def _stage_status_record(
    step: PipelineStep,
    status: str,
    *,
    input_paths: Sequence[str] | None = None,
    output_paths: Sequence[str] | None = None,
    returncode: int | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "command": list(step.command),
        "command_string": shlex.join(step.command),
        "name": step.name,
        "status": status,
    }
    if input_paths is not None:
        record["input_paths"] = list(input_paths)
        record["input_metadata"] = [_input_metadata(path) for path in input_paths]
    if output_paths is not None:
        record["output_paths"] = list(output_paths)
        record["output_metadata"] = [_output_metadata(path) for path in output_paths]
    if returncode is not None:
        record["returncode"] = returncode
    return record


def _diagnostic_summary(value: str | bytes) -> dict[str, Any]:
    if isinstance(value, bytes):
        total_bytes = len(value)
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
        total_bytes = len(text.encode("utf-8", errors="replace"))

    total_chars = len(text)
    truncated = total_chars > FAILURE_DIAGNOSTIC_TAIL_CHARS
    tail = text[-FAILURE_DIAGNOSTIC_TAIL_CHARS:] if truncated else text
    return {
        "tail": tail,
        "total_bytes": total_bytes,
        "total_chars": total_chars,
        "truncated": truncated,
    }


def _failure_summary(
    step: PipelineStep,
    returncode: int,
    *,
    stdout: str | bytes | None = None,
    stderr: str | bytes | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "command_string": shlex.join(step.command),
        "returncode": returncode,
    }
    diagnostics: dict[str, Any] = {}
    if stdout is not None:
        diagnostics["stdout"] = _diagnostic_summary(stdout)
    if stderr is not None:
        diagnostics["stderr"] = _diagnostic_summary(stderr)
    if diagnostics:
        summary["diagnostics"] = diagnostics
    return summary


def _write_status(path: Path, status: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _resume_output_metadata_matches(stage: dict[str, Any]) -> bool:
    metadata = stage.get("output_metadata")
    if not isinstance(metadata, list) or not metadata:
        return False
    for record in metadata:
        if not isinstance(record, dict):
            return False
        path_value = record.get("path")
        if not isinstance(path_value, str):
            return False
        path = Path(path_value)
        if record.get("exists") is not True:
            return False
        if not path.is_file():
            return False
        if "sha256" in record and record["sha256"] != _sha256(path):
            return False
        if "size_bytes" in record and record["size_bytes"] != path.stat().st_size:
            return False
    return True


def _resume_input_metadata_matches(stage: dict[str, Any], input_paths: Sequence[str]) -> bool:
    current_metadata = [_input_metadata(path) for path in input_paths]
    metadata = stage.get("input_metadata")
    if metadata is None and not current_metadata:
        return True
    if not isinstance(metadata, list):
        return False
    return metadata == current_metadata


def _resumable_stages(resume_status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    resumable: dict[str, dict[str, Any]] = {}
    for stage in resume_status.get("stages", []):
        if stage.get("status") in {"completed", "skipped"} and _resume_output_metadata_matches(stage):
            name = stage.get("name")
            if isinstance(name, str):
                resumable[name] = stage
    return resumable


def build_status(
    args: argparse.Namespace,
    plan: Iterable[PipelineStep],
    *,
    resume_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build deterministic per-stage status for the current pipeline plan."""
    resumable = _resumable_stages(resume_status or {}) if args.resume else {}
    stages = []
    for step in plan:
        input_paths = _stage_input_paths(args, step)
        output_paths = _stage_output_paths(args, step)
        resume_stage = resumable.get(step.name)
        if (
            resume_stage is not None
            and resume_stage.get("command") == list(step.command)
            and _resume_input_metadata_matches(resume_stage, input_paths)
        ):
            record = _stage_status_record(step, "skipped", input_paths=input_paths, output_paths=output_paths)
            record["skip_reason"] = "already satisfied by resume status"
        else:
            record = _stage_status_record(step, "planned", input_paths=input_paths, output_paths=output_paths)
        stages.append(record)

    return {
        "mode": "run" if args.run else "dry-run",
        "resume": args.resume,
        "schema_version": 1,
        "stages": stages,
    }


def run_plan(
    plan: Iterable[PipelineStep],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    status_out: Path | None = None,
    status: dict[str, Any] | None = None,
) -> None:
    steps = list(plan)
    command_runner = runner
    stage_records = status["stages"] if status is not None else []
    for index, step in enumerate(steps):
        if index < len(stage_records) and stage_records[index].get("status") == "skipped":
            print(f"[{step.name}] skipped")
            continue

        print(f"[{step.name}] {shlex.join(step.command)}")
        if status_out is not None and status is not None:
            input_paths = stage_records[index].get("input_paths", [])
            output_paths = stage_records[index].get("output_paths", [])
            stage_records[index] = _stage_status_record(
                step,
                "running",
                input_paths=input_paths,
                output_paths=output_paths,
            )
            _write_status(status_out, status)
        try:
            if command_runner is None:
                completed = subprocess.run(
                    list(step.command),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if completed.stdout:
                    sys.stdout.write(completed.stdout)
                if completed.stderr:
                    sys.stderr.write(completed.stderr)
            else:
                completed = command_runner(list(step.command), check=True)
        except subprocess.CalledProcessError as exc:
            if status_out is not None and status is not None:
                input_paths = stage_records[index].get("input_paths", [])
                output_paths = stage_records[index].get("output_paths", [])
                stage_records[index] = _stage_status_record(
                    step,
                    "failed",
                    input_paths=input_paths,
                    output_paths=output_paths,
                    returncode=exc.returncode,
                )
                stdout = getattr(exc, "stdout", None)
                if stdout is None:
                    stdout = getattr(exc, "output", None)
                stage_records[index]["failure_summary"] = _failure_summary(
                    step,
                    exc.returncode,
                    stdout=stdout,
                    stderr=getattr(exc, "stderr", None),
                )
                stage_records[index]["remediation_hint"] = _remediation_hint(step, exc.returncode)
                _write_status(status_out, status)
            raise
        if status_out is not None and status is not None:
            input_paths = stage_records[index].get("input_paths", [])
            output_paths = stage_records[index].get("output_paths", [])
            stage_records[index] = _stage_status_record(
                step,
                "completed",
                input_paths=input_paths,
                output_paths=output_paths,
                returncode=completed.returncode,
            )
            _write_status(status_out, status)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print or run the k8s-auto-fix detector -> proposer -> verifier -> "
            "risk -> scheduler pipeline. Defaults are dry-run, rules-mode, and "
            "no kubectl requirement."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="run", action="store_false", help="Print commands without running them.")
    mode.add_argument("--run", dest="run", action="store_true", help="Run each command in order.")
    parser.set_defaults(run=False)

    parser.add_argument(
        "--manifests",
        action="append",
        type=Path,
        help="Manifest file or directory to scan. Repeat for multiple inputs.",
    )
    parser.add_argument("--detections", type=Path, default=Path("data/detections.json"))
    parser.add_argument("--patches", type=Path, default=Path("data/patches.json"))
    parser.add_argument("--verified", type=Path, default=Path("data/verified.json"))
    parser.add_argument("--risk", type=Path, default=Path("data/risk.json"))
    parser.add_argument("--schedule", type=Path, default=Path("data/schedule.json"))
    parser.add_argument("--config", type=Path, default=Path("configs/run_rules.yaml"))
    parser.add_argument("--policies-dir", type=Path, default=Path("data/policies/kyverno"))
    parser.add_argument(
        "--no-policies-dir",
        action="store_true",
        help="Do not pass a Kyverno policies directory to detector or rescan verification.",
    )
    parser.add_argument("--jobs", type=int, default=4, help="Parallel workers for supported stages.")
    parser.add_argument(
        "--require-kubectl",
        action="store_true",
        help="Require kubectl during verification. Off by default to avoid a cluster dependency.",
    )
    parser.add_argument(
        "--enable-rescan",
        action="store_true",
        help="Enable verifier policy rescan. Off by default for the lightweight path.",
    )
    parser.add_argument("--epss-csv", type=Path, default=None, help="Optional local EPSS CSV for risk scoring.")
    parser.add_argument("--kev-json", type=Path, default=None, help="Optional local CISA KEV JSON for risk scoring.")
    parser.add_argument(
        "--policy-metrics",
        type=Path,
        default=None,
        help="Optional policy metrics JSON for scheduler scoring.",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Optional JSON path for a reproducibility manifest of the planned pipeline.",
    )
    parser.add_argument(
        "--status-out",
        type=Path,
        default=None,
        help="Optional JSON path for deterministic per-stage pipeline status.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip stages already completed in --status-out when their commands still match.",
    )

    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be >= 1")
    if args.resume and args.status_out is None:
        parser.error("--resume requires --status-out")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_plan(args)
    print(format_plan(plan))
    status = None
    if args.status_out is not None:
        status = build_status(args, plan, resume_status=_load_status(args.status_out))
        _write_status(args.status_out, status)
    if args.manifest_out is not None:
        write_manifest(args.manifest_out, args, plan)
    if args.run:
        run_plan(plan, status_out=args.status_out, status=status)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
