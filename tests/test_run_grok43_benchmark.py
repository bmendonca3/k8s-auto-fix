import json
import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from scripts.run_grok43_benchmark import BenchmarkOptions, parse_args, run_benchmark


def test_grok43_benchmark_writes_namespaced_exact_limit_and_commands(tmp_path: Path) -> None:
    _write_repo_scaffold(tmp_path)
    _write_source_batches(
        tmp_path,
        [
            [
                _record("001", manifest_yaml=None),
                _record("002"),
                _record("003"),
            ],
            [
                _record("004"),
                _record("005"),
                _record("006"),
            ],
        ],
    )

    calls: list[list[str]] = []

    def fake_runner(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        _fake_pipeline_command(command, cwd)
        return subprocess.CompletedProcess(list(command), 0)

    plan = run_benchmark(
        _options(tmp_path, run_id="bench-50", limit=5, batch_size=3, jobs=2),
        repo_root=tmp_path,
        runner=fake_runner,
    )

    run_dir = tmp_path / "data" / "batch_runs" / "bench-50"
    expected_outputs = [
        plan.merged_detections,
        plan.merged_patches,
        plan.merged_verified,
        plan.metrics,
        plan.failure_summary,
        plan.manifest,
        *plan.detection_batches,
        *plan.patch_batches,
        *plan.verified_batches,
    ]
    for path in expected_outputs:
        path.resolve().relative_to(run_dir.resolve())
        assert path.exists(), path

    assert [len(_load(path)) for path in plan.detection_batches] == [3, 2]
    detections = _load(plan.merged_detections)
    assert len(detections) == 5
    assert detections[0]["manifest_yaml"].startswith("apiVersion: v1")

    proposer_commands = [command for command in calls if "src.proposer.cli" in command]
    verifier_commands = [command for command in calls if "src.verifier.cli" in command]
    assert len(proposer_commands) == 2
    assert len(verifier_commands) == 2
    for command in proposer_commands:
        assert command[command.index("--config") + 1] == "configs/run_grok.yaml"
        assert command[command.index("--out") + 1].startswith("data/batch_runs/bench-50/")
    for command in verifier_commands:
        assert "--include-errors" in command
        assert "--enable-rescan" in command
        assert "--no-require-kubectl" in command
        assert command[command.index("--policies-dir") + 1] == "data/policies/kyverno"
        assert command[command.index("--kube-linter-cmd") + 1].endswith("kube-linter")
        assert command[command.index("--kyverno-cmd") + 1].endswith("kyverno")
        assert command[command.index("--out") + 1].startswith("data/batch_runs/bench-50/")

    metrics = json.loads(plan.metrics.read_text(encoding="utf-8"))
    assert metrics["detections"] == 5
    assert metrics["patches"] == 5
    assert metrics["verified"] == 5
    assert metrics["accepted"] == 3
    assert "Verifier Failure Report" in plan.failure_summary.read_text(encoding="utf-8")

    manifest = json.loads(plan.manifest.read_text(encoding="utf-8"))
    assert manifest["scanners"]["kube_linter"]["requested_command"].endswith("kube-linter")
    assert manifest["scanners"]["kube_linter"]["resolved_path"].endswith("bin/kube-linter")
    assert manifest["scanners"]["kube_linter"]["version_output"] == "kube-linter test 1.0"
    assert len(manifest["scanners"]["kube_linter"]["sha256"]) == 64
    assert manifest["scanners"]["kyverno"]["version_output"] == "kyverno test 1.0"
    assert manifest["policy_bundle"]["file_count"] == 1
    assert len(manifest["policy_bundle"]["sha256"]) == 64


def test_grok43_benchmark_refuses_existing_namespace_without_resume(tmp_path: Path) -> None:
    _write_repo_scaffold(tmp_path)
    _write_source_batches(tmp_path, [[_record("001")]])
    run_dir = tmp_path / "data" / "batch_runs" / "bench-existing"
    run_dir.mkdir(parents=True)
    (run_dir / "existing.txt").write_text("owned by another run", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--resume"):
        run_benchmark(
            _options(tmp_path, run_id="bench-existing", limit=1),
            repo_root=tmp_path,
            runner=lambda command, cwd: subprocess.CompletedProcess(list(command), 0),
        )


def test_grok43_benchmark_resume_reuses_existing_namespace(tmp_path: Path) -> None:
    _write_repo_scaffold(tmp_path)
    _write_source_batches(tmp_path, [[_record("001")]])
    run_dir = tmp_path / "data" / "batch_runs" / "bench-resume"
    run_dir.mkdir(parents=True)
    marker = run_dir / "existing.txt"
    marker.write_text("keep me", encoding="utf-8")

    def fake_runner(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        _fake_pipeline_command(command, cwd)
        return subprocess.CompletedProcess(list(command), 0)

    plan = run_benchmark(
        _options(tmp_path, run_id="bench-resume", limit=1, resume=True),
        repo_root=tmp_path,
        runner=fake_runner,
    )

    assert marker.read_text(encoding="utf-8") == "keep me"
    assert len(_load(plan.merged_detections)) == 1


def test_grok43_benchmark_preflights_scanner_binaries(tmp_path: Path) -> None:
    _write_repo_scaffold(tmp_path)
    _write_source_batches(tmp_path, [[_record("001")]])

    with pytest.raises(FileNotFoundError, match="kube-linter"):
        run_benchmark(
            BenchmarkOptions(
                run_id="bench-missing-scanner",
                limit=1,
                kube_linter_cmd=str(tmp_path / "missing-kube-linter"),
                kyverno_cmd=str(tmp_path / "bin" / "kyverno"),
            ),
            repo_root=tmp_path,
            runner=lambda command, cwd: subprocess.CompletedProcess(list(command), 0),
        )


def test_grok43_cli_defaults_to_ignored_tool_cache() -> None:
    args = parse_args(["--run-id", "bench-defaults", "--limit", "1"])
    assert args.kube_linter_cmd == "tmp/tool-cache/bin/kube-linter"
    assert args.kyverno_cmd == "tmp/tool-cache/bin/kyverno"


def _options(root: Path, **kwargs: object) -> BenchmarkOptions:
    return BenchmarkOptions(
        kube_linter_cmd=str(root / "bin" / "kube-linter"),
        kyverno_cmd=str(root / "bin" / "kyverno"),
        **kwargs,
    )


def _write_repo_scaffold(root: Path) -> None:
    (root / "configs").mkdir(parents=True)
    (root / "configs" / "run_grok.yaml").write_text(
        "\n".join(
            [
                "grok:",
                "  model: grok-4.3",
                "proposer:",
                "  mode: grok",
            ]
        ),
        encoding="utf-8",
    )
    (root / "data" / "policies" / "kyverno").mkdir(parents=True)
    (root / "data" / "policies" / "kyverno" / "policy.yaml").write_text(
        "apiVersion: kyverno.io/v1\nkind: ClusterPolicy\nmetadata:\n  name: test\n",
        encoding="utf-8",
    )
    manifests = root / "data" / "manifests"
    manifests.mkdir(parents=True)
    (manifests / "pod.yaml").write_text("apiVersion: v1\nkind: Pod\nmetadata:\n  name: sample\n", encoding="utf-8")
    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name in ("kube-linter", "kyverno"):
        binary = bin_dir / name
        binary.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    'if [ "$1" = "version" ]; then',
                    f"  echo \"{name} test 1.0\"",
                    "  exit 0",
                    "fi",
                    "exit 0",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        binary.chmod(0o755)


def _write_source_batches(root: Path, batches: list[list[dict[str, str]]]) -> None:
    source_dir = root / "data" / "batch_runs" / "grok_5k"
    source_dir.mkdir(parents=True)
    for index, records in enumerate(batches):
        (source_dir / f"detections_grok5k_batch_{index:03d}.json").write_text(
            json.dumps(records, indent=2),
            encoding="utf-8",
        )


def _record(identifier: str, *, manifest_yaml: str | None = "apiVersion: v1\nkind: Pod\n") -> dict[str, str]:
    record = {
        "id": identifier,
        "policy_id": "latest-tag",
        "violation_text": "image uses latest",
        "manifest_path": "data/manifests/pod.yaml",
    }
    if manifest_yaml is not None:
        record["manifest_yaml"] = manifest_yaml
    return record


def _fake_pipeline_command(command: Sequence[str], cwd: Path) -> None:
    command = list(command)
    out_path = cwd / command[command.index("--out") + 1]
    if "src.proposer.cli" in command:
        detections_path = cwd / command[command.index("--detections") + 1]
        detections = _load(detections_path)
        patches = [
            {
                "id": record["id"],
                "policy_id": record["policy_id"],
                "patch": [{"op": "add", "path": "/metadata/labels/bench", "value": "grok43"}],
                "source": "grok",
            }
            for record in detections
        ]
        out_path.write_text(json.dumps(patches, indent=2), encoding="utf-8")
        return

    if "src.verifier.cli" in command:
        patches_path = cwd / command[command.index("--patches") + 1]
        patches = _load(patches_path)
        verified = []
        for index, patch in enumerate(patches):
            accepted = index % 2 == 0
            verified.append(
                {
                    "id": patch["id"],
                    "policy_id": patch["policy_id"],
                    "accepted": accepted,
                    "ok_schema": True,
                    "ok_policy": accepted,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "patched_yaml": "apiVersion: v1\nkind: Pod\n",
                    "errors": [] if accepted else ["policy still failed"],
                }
            )
        out_path.write_text(json.dumps(verified, indent=2), encoding="utf-8")
        return

    raise AssertionError(f"unexpected command: {command}")


def _load(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))
