import io
import hashlib
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import run_pipeline


class RunPipelineTests(unittest.TestCase):
    def test_default_plan_is_dry_run_and_cluster_safe(self) -> None:
        args = run_pipeline.parse_args([])
        plan = run_pipeline.build_plan(args, python="python")

        self.assertFalse(args.run)
        self.assertEqual([step.name for step in plan], ["detect", "propose", "verify", "risk", "schedule"])

        rendered = run_pipeline.format_plan(plan)
        self.assertIn("configs/run_rules.yaml", rendered)
        self.assertIn("--no-require-kubectl", rendered)
        self.assertNotIn("make cti", rendered)
        self.assertNotIn("--enable-rescan", rendered)

    def test_custom_paths_are_threaded_through_plan(self) -> None:
        args = run_pipeline.parse_args(
            [
                "--manifests",
                "fixtures/one",
                "--manifests",
                "fixtures/two.yaml",
                "--detections",
                "tmp/d.json",
                "--patches",
                "tmp/p.json",
                "--verified",
                "tmp/v.json",
                "--risk",
                "tmp/r.json",
                "--schedule",
                "tmp/s.json",
                "--config",
                "configs/custom.yaml",
                "--jobs",
                "2",
                "--epss-csv",
                "tmp/epss.csv",
                "--kev-json",
                "tmp/kev.json",
                "--policy-metrics",
                "tmp/policy_metrics.json",
            ]
        )

        plan = run_pipeline.build_plan(args, python="python")
        commands = {step.name: step.command for step in plan}

        self.assertEqual(commands["detect"].count("--in"), 2)
        self.assertIn("fixtures/one", commands["detect"])
        self.assertIn("fixtures/two.yaml", commands["detect"])
        self.assertIn("tmp/d.json", commands["propose"])
        self.assertIn("tmp/p.json", commands["verify"])
        self.assertIn("tmp/r.json", commands["schedule"])
        self.assertIn("configs/custom.yaml", commands["propose"])
        self.assertIn("2", commands["detect"])
        self.assertIn("tmp/epss.csv", commands["risk"])
        self.assertIn("tmp/kev.json", commands["risk"])
        self.assertIn("tmp/policy_metrics.json", commands["schedule"])

    def test_run_plan_delegates_commands_in_order(self) -> None:
        plan = [
            run_pipeline.PipelineStep("one", ("python", "-m", "one")),
            run_pipeline.PipelineStep("two", ("python", "-m", "two")),
        ]
        calls = []

        def fake_runner(command, check):
            calls.append((command, check))
            return subprocess.CompletedProcess(command, 0)

        run_pipeline.run_plan(plan, runner=fake_runner)

        self.assertEqual(
            calls,
            [
                (["python", "-m", "one"], True),
                (["python", "-m", "two"], True),
            ],
        )

    def test_manifest_out_writes_reproducibility_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "pipeline-manifest.json"

            with redirect_stdout(io.StringIO()):
                result = run_pipeline.main(
                    [
                        "--dry-run",
                        "--manifest-out",
                        str(manifest_path),
                        "--manifests",
                        "fixtures/one",
                        "--jobs",
                        "2",
                        "--require-kubectl",
                        "--enable-rescan",
                        "--epss-csv",
                        "tmp/epss.csv",
                        "--kev-json",
                        "tmp/kev.json",
                        "--policy-metrics",
                        "tmp/policy_metrics.json",
                    ]
                )

            self.assertEqual(result, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["mode"], "dry-run")
        self.assertIn("timestamp", manifest)
        self.assertEqual(manifest["config_path"], "configs/run_rules.yaml")
        self.assertEqual(manifest["jobs"], 2)
        self.assertTrue(manifest["flags"]["dry_run"])
        self.assertTrue(manifest["flags"]["require_kubectl"])
        self.assertTrue(manifest["flags"]["enable_rescan"])
        self.assertEqual(manifest["input_paths"]["manifests"], ["fixtures/one"])
        self.assertEqual(manifest["input_paths"]["policies_dir"], "data/policies/kyverno")
        self.assertEqual(manifest["input_paths"]["epss_csv"], "tmp/epss.csv")
        self.assertEqual(manifest["input_paths"]["kev_json"], "tmp/kev.json")
        self.assertEqual(manifest["input_paths"]["policy_metrics"], "tmp/policy_metrics.json")
        self.assertEqual(manifest["output_paths"]["detections"], "data/detections.json")
        expected_stages = ["detect", "propose", "verify", "risk", "schedule"]
        self.assertEqual([stage["name"] for stage in manifest["stages"]], expected_stages)
        self.assertEqual(manifest["python_executable"], manifest["stages"][0]["command"][0])
        self.assertIn("src.detector.cli", manifest["stages"][0]["command"])
        self.assertIn("command_string", manifest["stages"][0])
        self.assertEqual(manifest["stages"][0]["remediation_hint"]["key"], "detect:*")
        self.assertIn("manifest inputs", manifest["stages"][0]["remediation_hint"]["message"])
        self.assertEqual(manifest["stages"][2]["remediation_hint"]["key"], "verify:*")
        self.assertIn("dry-run errors", manifest["stages"][2]["remediation_hint"]["message"])

    def test_manifest_out_is_written_before_run_mode_delegates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = Path(tmp_dir) / "pipeline-manifest.json"
            manifest_exists_when_run_starts = []

            def fake_run_plan(_plan, **_kwargs):
                manifest_exists_when_run_starts.append(manifest_path.exists())

            with mock.patch.object(run_pipeline, "run_plan", side_effect=fake_run_plan):
                with redirect_stdout(io.StringIO()):
                    result = run_pipeline.main(["--run", "--manifest-out", str(manifest_path)])

            self.assertEqual(result, 0)
            self.assertEqual(manifest_exists_when_run_starts, [True])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["mode"], "run")
        self.assertTrue(manifest["flags"]["run"])

    def test_manifest_out_records_existing_and_missing_stage_input_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_input = tmp_path / "pod.yaml"
            manifest_bytes = b"apiVersion: v1\nkind: Pod\n"
            manifest_input.write_bytes(manifest_bytes)
            missing_kev = tmp_path / "missing-kev.json"
            manifest_path = tmp_path / "pipeline-manifest.json"

            with redirect_stdout(io.StringIO()):
                result = run_pipeline.main(
                    [
                        "--dry-run",
                        "--manifest-out",
                        str(manifest_path),
                        "--manifests",
                        str(manifest_input),
                        "--no-policies-dir",
                        "--kev-json",
                        str(missing_kev),
                    ]
                )

            self.assertEqual(result, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        detect_stage = manifest["stages"][0]
        detect_input = detect_stage["input_metadata"][0]
        risk_stage = next(stage for stage in manifest["stages"] if stage["name"] == "risk")
        missing_input = next(record for record in risk_stage["input_metadata"] if record["path"] == str(missing_kev))
        self.assertEqual(detect_stage["input_paths"], [str(manifest_input)])
        self.assertTrue(detect_input["exists"])
        self.assertEqual(detect_input["type"], "file")
        self.assertEqual(detect_input["sha256"], hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(detect_input["size_bytes"], len(manifest_bytes))
        self.assertIn("output_metadata", detect_stage)
        self.assertFalse(missing_input["exists"])
        self.assertEqual(missing_input["type"], "missing")
        self.assertNotIn("sha256", missing_input)
        self.assertNotIn("size_bytes", missing_input)

    def test_status_out_writes_planned_stages_for_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "pipeline-status.json"

            with redirect_stdout(io.StringIO()):
                result = run_pipeline.main(["--dry-run", "--status-out", str(status_path)])

            self.assertEqual(result, 0)
            status = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(status["schema_version"], 1)
        self.assertEqual(status["mode"], "dry-run")
        self.assertFalse(status["resume"])
        self.assertEqual([stage["status"] for stage in status["stages"]], ["planned"] * 5)
        self.assertEqual([stage["name"] for stage in status["stages"]], ["detect", "propose", "verify", "risk", "schedule"])
        self.assertEqual(status["stages"][0]["output_paths"], ["data/detections.json"])
        self.assertEqual(status["stages"][1]["output_paths"], ["data/patches.json"])
        self.assertEqual(status["stages"][2]["output_paths"], ["data/verified.json"])
        self.assertEqual(status["stages"][3]["output_paths"], ["data/risk.json"])
        self.assertEqual(status["stages"][4]["output_paths"], ["data/schedule.json"])
        self.assertIn("command", status["stages"][0])
        self.assertIn("command_string", status["stages"][0])
        self.assertIn("output_metadata", status["stages"][0])
        self.assertIn("input_metadata", status["stages"][0])

    def test_status_out_records_existing_output_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            detections = tmp_path / "detections.json"
            detections.write_text('{"ok": true}\n', encoding="utf-8")
            status_path = tmp_path / "pipeline-status.json"

            with redirect_stdout(io.StringIO()):
                result = run_pipeline.main(
                    [
                        "--dry-run",
                        "--status-out",
                        str(status_path),
                        "--detections",
                        str(detections),
                        "--patches",
                        str(tmp_path / "missing-patches.json"),
                    ]
                )

            self.assertEqual(result, 0)
            status = json.loads(status_path.read_text(encoding="utf-8"))

        metadata = status["stages"][0]["output_metadata"][0]
        expected_hash = hashlib.sha256(b'{"ok": true}\n').hexdigest()
        self.assertEqual(status["stages"][0]["output_paths"], [str(detections)])
        self.assertTrue(metadata["exists"])
        self.assertEqual(metadata["path"], str(detections))
        self.assertEqual(metadata["sha256"], expected_hash)
        self.assertEqual(metadata["size_bytes"], len(b'{"ok": true}\n'))
        self.assertEqual(status["stages"][1]["output_metadata"][0]["exists"], False)

    def test_status_out_records_existing_and_missing_input_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = tmp_path / "run_rules.yaml"
            config_bytes = b"rules: []\n"
            config.write_bytes(config_bytes)
            missing_detections = tmp_path / "missing-detections.json"
            status_path = tmp_path / "pipeline-status.json"

            with redirect_stdout(io.StringIO()):
                result = run_pipeline.main(
                    [
                        "--dry-run",
                        "--status-out",
                        str(status_path),
                        "--detections",
                        str(missing_detections),
                        "--config",
                        str(config),
                    ]
                )

            self.assertEqual(result, 0)
            status = json.loads(status_path.read_text(encoding="utf-8"))

        propose_stage = status["stages"][1]
        metadata_by_path = {record["path"]: record for record in propose_stage["input_metadata"]}
        self.assertEqual(propose_stage["input_paths"], [str(missing_detections), str(config)])
        self.assertFalse(metadata_by_path[str(missing_detections)]["exists"])
        self.assertEqual(metadata_by_path[str(missing_detections)]["type"], "missing")
        self.assertNotIn("sha256", metadata_by_path[str(missing_detections)])
        self.assertNotIn("size_bytes", metadata_by_path[str(missing_detections)])
        self.assertTrue(metadata_by_path[str(config)]["exists"])
        self.assertEqual(metadata_by_path[str(config)]["type"], "file")
        self.assertEqual(metadata_by_path[str(config)]["sha256"], hashlib.sha256(config_bytes).hexdigest())
        self.assertEqual(metadata_by_path[str(config)]["size_bytes"], len(config_bytes))

    def test_run_mode_status_records_completed_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "pipeline-status.json"

            def fake_runner(command, check, **_kwargs):
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(run_pipeline.subprocess, "run", side_effect=fake_runner):
                with redirect_stdout(io.StringIO()):
                    result = run_pipeline.main(["--run", "--status-out", str(status_path)])

            self.assertEqual(result, 0)
            status = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(status["mode"], "run")
        self.assertEqual([stage["status"] for stage in status["stages"]], ["completed"] * 5)
        self.assertEqual([stage["returncode"] for stage in status["stages"]], [0] * 5)
        self.assertEqual(status["stages"][0]["output_paths"], ["data/detections.json"])

    def test_run_mode_status_records_concise_failure_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "pipeline-status.json"

            def fake_runner(command, check, **_kwargs):
                raise subprocess.CalledProcessError(
                    23,
                    command,
                    output="very long stdout",
                    stderr="very long stderr",
                )

            with mock.patch.object(run_pipeline.subprocess, "run", side_effect=fake_runner):
                with redirect_stdout(io.StringIO()):
                    with self.assertRaises(subprocess.CalledProcessError):
                        run_pipeline.main(["--run", "--status-out", str(status_path)])

            status = json.loads(status_path.read_text(encoding="utf-8"))

        failed_stage = status["stages"][0]
        self.assertEqual(failed_stage["status"], "failed")
        self.assertEqual(failed_stage["returncode"], 23)
        failure_summary = failed_stage["failure_summary"]
        self.assertEqual(failure_summary["command_string"], failed_stage["command_string"])
        self.assertEqual(failure_summary["returncode"], 23)
        self.assertEqual(
            failure_summary["diagnostics"],
            {
                "stdout": {
                    "tail": "very long stdout",
                    "total_bytes": len("very long stdout".encode("utf-8")),
                    "total_chars": len("very long stdout"),
                    "truncated": False,
                },
                "stderr": {
                    "tail": "very long stderr",
                    "total_bytes": len("very long stderr".encode("utf-8")),
                    "total_chars": len("very long stderr"),
                    "truncated": False,
                },
            },
        )
        self.assertEqual(failed_stage["remediation_hint"]["key"], "detect:23")
        self.assertIn("manifest inputs", failed_stage["remediation_hint"]["message"])

    def test_run_mode_status_bounds_large_failure_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "pipeline-status.json"
            stdout = (
                "stdout-head:"
                + ("x" * (run_pipeline.FAILURE_DIAGNOSTIC_TAIL_CHARS + 20))
                + ":stdout-tail"
            )
            stderr = (
                b"stderr-head:"
                + (b"y" * (run_pipeline.FAILURE_DIAGNOSTIC_TAIL_CHARS + 20))
                + b":stderr-tail"
            )

            def fake_runner(command, check, **_kwargs):
                raise subprocess.CalledProcessError(24, command, output=stdout, stderr=stderr)

            with mock.patch.object(run_pipeline.subprocess, "run", side_effect=fake_runner):
                with redirect_stdout(io.StringIO()):
                    with self.assertRaises(subprocess.CalledProcessError):
                        run_pipeline.main(["--run", "--status-out", str(status_path)])

            status = json.loads(status_path.read_text(encoding="utf-8"))

        failure_summary = status["stages"][0]["failure_summary"]
        stdout_summary = failure_summary["diagnostics"]["stdout"]
        stderr_summary = failure_summary["diagnostics"]["stderr"]
        self.assertEqual(failure_summary["returncode"], 24)
        self.assertEqual(stdout_summary["total_chars"], len(stdout))
        self.assertEqual(stdout_summary["total_bytes"], len(stdout.encode("utf-8")))
        self.assertEqual(stderr_summary["total_chars"], len(stderr.decode("utf-8")))
        self.assertEqual(stderr_summary["total_bytes"], len(stderr))
        self.assertTrue(stdout_summary["truncated"])
        self.assertTrue(stderr_summary["truncated"])
        self.assertLessEqual(
            len(stdout_summary["tail"]),
            run_pipeline.FAILURE_DIAGNOSTIC_TAIL_CHARS,
        )
        self.assertLessEqual(
            len(stderr_summary["tail"]),
            run_pipeline.FAILURE_DIAGNOSTIC_TAIL_CHARS,
        )
        self.assertTrue(stdout_summary["tail"].endswith(":stdout-tail"))
        self.assertTrue(stderr_summary["tail"].endswith(":stderr-tail"))
        self.assertNotIn("stdout-head", stdout_summary["tail"])
        self.assertNotIn("stderr-head", stderr_summary["tail"])

    def test_run_plan_records_stage_return_code_specific_remediation_hint(self) -> None:
        plan = [run_pipeline.PipelineStep("verify", ("python", "-m", "src.verifier.cli"))]
        args = run_pipeline.parse_args(["--run", "--status-out", "status.json"])
        status = run_pipeline.build_status(args, plan)

        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "pipeline-status.json"

            def fake_runner(command, check):
                raise subprocess.CalledProcessError(127, command)

            with self.assertRaises(subprocess.CalledProcessError):
                run_pipeline.run_plan(plan, runner=fake_runner, status_out=status_path, status=status)

            status = json.loads(status_path.read_text(encoding="utf-8"))

        failed_stage = status["stages"][0]
        self.assertEqual(failed_stage["status"], "failed")
        self.assertEqual(failed_stage["returncode"], 127)
        self.assertNotIn("diagnostics", failed_stage["failure_summary"])
        self.assertEqual(failed_stage["remediation_hint"]["key"], "verify:127")
        self.assertIn("kubectl", failed_stage["remediation_hint"]["message"])

    def test_run_plan_writes_running_status_before_command_completes(self) -> None:
        plan = [run_pipeline.PipelineStep("one", ("python", "-m", "one"))]
        args = run_pipeline.parse_args(["--run", "--status-out", "status.json"])
        status = run_pipeline.build_status(args, plan)
        observed_statuses = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            status_path = Path(tmp_dir) / "pipeline-status.json"

            def fake_runner(command, check):
                current_status = json.loads(status_path.read_text(encoding="utf-8"))
                observed_statuses.append(current_status["stages"][0]["status"])
                return subprocess.CompletedProcess(command, 0)

            run_pipeline.run_plan(plan, runner=fake_runner, status_out=status_path, status=status)
            final_status = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(observed_statuses, ["running"])
        self.assertEqual(final_status["stages"][0]["status"], "completed")

    def test_resume_skips_previously_completed_matching_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            one_output = tmp_path / "one.json"
            one_output_bytes = b'{"one": true}\n'
            one_output.write_bytes(one_output_bytes)
            two_output = tmp_path / "two.json"
            plan = [
                run_pipeline.PipelineStep("one", ("python", "-m", "one")),
                run_pipeline.PipelineStep("two", ("python", "-m", "two")),
            ]
            args = run_pipeline.parse_args(["--run", "--status-out", "status.json", "--resume"])
            resume_status = {
                "schema_version": 1,
                "stages": [
                    {
                        "command": ["python", "-m", "one"],
                        "command_string": "python -m one",
                        "name": "one",
                        "output_metadata": [
                            {
                                "exists": True,
                                "path": str(one_output),
                                "sha256": hashlib.sha256(one_output_bytes).hexdigest(),
                                "size_bytes": len(one_output_bytes),
                            }
                        ],
                        "output_paths": [str(one_output)],
                        "returncode": 0,
                        "status": "completed",
                    },
                    {
                        "command": ["python", "-m", "two", "--old"],
                        "command_string": "python -m two --old",
                        "name": "two",
                        "output_metadata": [
                            {"exists": False, "path": str(two_output)}
                        ],
                        "output_paths": [str(two_output)],
                        "returncode": 0,
                        "status": "completed",
                    },
                ],
            }
            status = run_pipeline.build_status(args, plan, resume_status=resume_status)
            calls = []

            def fake_runner(command, check):
                calls.append((command, check))
                return subprocess.CompletedProcess(command, 0)

            status_path = Path(tmp_dir) / "pipeline-status.json"
            run_pipeline.run_plan(plan, runner=fake_runner, status_out=status_path, status=status)
            final_status = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(calls, [(["python", "-m", "two"], True)])
        self.assertEqual([stage["status"] for stage in final_status["stages"]], ["skipped", "completed"])
        self.assertEqual(final_status["stages"][0]["skip_reason"], "already satisfied by resume status")

    def test_resume_keeps_previously_skipped_matching_stage_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "one.json"
            output_bytes = b'{"one": true}\n'
            output.write_bytes(output_bytes)
            plan = [run_pipeline.PipelineStep("one", ("python", "-m", "one"))]
            args = run_pipeline.parse_args(["--run", "--status-out", "status.json", "--resume"])
            resume_status = {
                "schema_version": 1,
                "stages": [
                    {
                        "command": ["python", "-m", "one"],
                        "command_string": "python -m one",
                        "name": "one",
                        "output_metadata": [
                            {
                                "exists": True,
                                "path": str(output),
                                "sha256": hashlib.sha256(output_bytes).hexdigest(),
                                "size_bytes": len(output_bytes),
                            }
                        ],
                        "output_paths": [str(output)],
                        "skip_reason": "already satisfied by resume status",
                        "status": "skipped",
                    },
                ],
            }

            status = run_pipeline.build_status(args, plan, resume_status=resume_status)

        self.assertEqual(status["stages"][0]["status"], "skipped")

    def test_resume_does_not_skip_when_prior_output_hash_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "one.json"
            output.write_text('{"changed": true}\n', encoding="utf-8")
            plan = [run_pipeline.PipelineStep("one", ("python", "-m", "one"))]
            args = run_pipeline.parse_args(["--run", "--status-out", "status.json", "--resume"])
            resume_status = {
                "schema_version": 1,
                "stages": [
                    {
                        "command": ["python", "-m", "one"],
                        "command_string": "python -m one",
                        "name": "one",
                        "output_metadata": [
                            {
                                "exists": True,
                                "path": str(output),
                                "sha256": "0" * 64,
                            }
                        ],
                        "output_paths": [str(output)],
                        "returncode": 0,
                        "status": "completed",
                    }
                ],
            }

            status = run_pipeline.build_status(args, plan, resume_status=resume_status)

        self.assertEqual(status["stages"][0]["status"], "planned")

    def test_resume_does_not_skip_when_prior_input_hash_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest = tmp_path / "pod.yaml"
            original_manifest_bytes = b"apiVersion: v1\nkind: Pod\nmetadata:\n  name: old\n"
            changed_manifest_bytes = b"apiVersion: v1\nkind: Pod\nmetadata:\n  name: new\n"
            manifest.write_bytes(original_manifest_bytes)
            detections = tmp_path / "detections.json"
            detections_bytes = b'{"detections": []}\n'
            detections.write_bytes(detections_bytes)
            args = run_pipeline.parse_args(
                [
                    "--run",
                    "--status-out",
                    "status.json",
                    "--resume",
                    "--manifests",
                    str(manifest),
                    "--no-policies-dir",
                    "--detections",
                    str(detections),
                ]
            )
            plan = run_pipeline.build_plan(args, python="python")
            resume_status = {
                "schema_version": 1,
                "stages": [
                    {
                        "command": list(plan[0].command),
                        "command_string": " ".join(plan[0].command),
                        "input_metadata": [
                            {
                                "exists": True,
                                "path": str(manifest),
                                "sha256": hashlib.sha256(original_manifest_bytes).hexdigest(),
                                "size_bytes": len(original_manifest_bytes),
                                "type": "file",
                            }
                        ],
                        "input_paths": [str(manifest)],
                        "name": "detect",
                        "output_metadata": [
                            {
                                "exists": True,
                                "path": str(detections),
                                "sha256": hashlib.sha256(detections_bytes).hexdigest(),
                                "size_bytes": len(detections_bytes),
                            }
                        ],
                        "output_paths": [str(detections)],
                        "returncode": 0,
                        "status": "completed",
                    }
                ],
            }
            manifest.write_bytes(changed_manifest_bytes)

            status = run_pipeline.build_status(args, plan, resume_status=resume_status)

        self.assertEqual(status["stages"][0]["status"], "planned")
        self.assertNotIn("skip_reason", status["stages"][0])

    def test_resume_requires_status_out(self) -> None:
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                run_pipeline.parse_args(["--resume"])


if __name__ == "__main__":
    unittest.main()
