import hashlib
import io
import json
from pathlib import Path

from scripts import build_review_packet


POD_MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  name: demo
spec:
  containers:
  - name: web
    image: nginx:latest
"""


SECOND_POD_MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  name: worker
spec:
  containers:
  - name: worker
    image: busybox:latest
"""


CONFIG_MAP_MANIFEST = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: settings
data:
  mode: unsafe
"""


def test_markdown_output_combines_core_sections_and_schedule(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(
        json.dumps(
            [
                {
                    "id": "001",
                    "score": 2.0,
                    "R": 20.0,
                    "p": 0.5,
                    "Et": 5.0,
                },
                {
                    "id": "002",
                    "score": 4.0,
                    "R": 50.0,
                    "p": 0.8,
                    "Et": 10.0,
                },
            ]
        ),
        encoding="utf-8",
    )

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--schedule",
        str(schedule_path),
    )

    assert code == 0
    assert stderr == ""
    assert stdout.startswith("# Operator Review Packet\n")
    assert "## Summary Counts" in stdout
    assert "| Detections | 3 |" in stdout
    assert "| Verifier rejected | 1 |" in stdout
    assert "## Verifier Report Summary" in stdout
    assert "### Verifier Failure Report" in stdout
    assert "## Selected Patch Diffs" in stdout
    assert "--- 001-no_latest_tag:before.yaml" in stdout
    assert "+    image: nginx:stable" in stdout
    assert "## Schedule Summary" in stdout
    assert "### Scheduler Priority Explanation" in stdout
    assert "| 1 | 002 |" in stdout
    assert "## Rollout Batch Summary" not in stdout


def test_json_output_is_machine_readable(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--format",
        "json",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["counts"]["detections"] == 3
    assert payload["counts"]["patch_records"] == 3
    assert payload["counts"]["accepted_patch_records"] == 1
    assert payload["counts"]["selected_patch_records"] == 1
    assert payload["counts"]["verifier_records"] == 2
    assert payload["verifier_report"]["summary"] == {
        "total": 2,
        "accepted": 1,
        "rejected": 1,
    }
    assert "selected_patch_ids" not in payload
    assert [item["id"] for item in payload["patch_diffs"]] == ["001"]
    assert payload["schedule"]["status"] == "not_requested"
    assert payload["queue"]["status"] == "not_requested"
    assert payload["artifacts"]["status"] == "not_requested"
    assert "batches" not in payload["sources"]
    assert "rollout" not in payload
    assert all(not key.startswith("rollout_") for key in payload["counts"])


def test_concise_markdown_output_summarises_pr_release_fields(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(
        json.dumps(
            [
                {
                    "id": "001",
                    "score": 2.0,
                    "R": 20.0,
                    "p": 0.5,
                    "Et": 5.0,
                },
                {
                    "id": "002",
                    "score": 4.0,
                    "R": 50.0,
                    "p": 0.8,
                    "Et": 10.0,
                },
            ]
        ),
        encoding="utf-8",
    )
    artifact = tmp_path / "review" / "artifact.txt"
    artifact.parent.mkdir()
    content = b"packet evidence\n"
    artifact.write_bytes(content)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--schedule",
        str(schedule_path),
        "--artifact",
        str(artifact),
        "--markdown-mode",
        "concise",
    )

    assert code == 0
    assert stderr == ""
    assert stdout.startswith("# PR / Release Review Summary\n")
    assert "## Counts" in stdout
    assert "| Verifier rejected | 1 |" in stdout
    assert "## Verifier Rejects" in stdout
    assert "| ok_policy | 1 | 002 |" in stdout
    assert "## Selected Patch IDs" in stdout
    assert "Selected patch IDs: `001`" in stdout
    assert "## Schedule Top Entries" in stdout
    assert "| 1 | 002 | 4 |" in stdout
    assert "## Artifact Hashes" in stdout
    assert hashlib.sha256(content).hexdigest() in stdout
    assert "```diff" not in stdout
    assert "--- 001-no_latest_tag:before.yaml" not in stdout


def test_json_output_includes_rollout_annotations_when_batches_supplied(
    tmp_path: Path,
) -> None:
    inputs = _write_core_inputs(tmp_path)
    batches_path = _write_rollout_batches(tmp_path)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--batches",
        str(batches_path),
        "--rollout-max-count",
        "1",
        "--rollout-max-total-risk",
        "10",
        "--rollout-max-policies",
        "1",
        "--format",
        "json",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["sources"]["batches"] == str(batches_path)
    assert payload["filters"]["rollout"] == {
        "default_window": "standard",
        "max_count": 1,
        "max_total_risk": 10.0,
        "max_namespaces": None,
        "max_policies": 1,
    }
    assert payload["counts"]["rollout_batches"] == 2
    assert payload["counts"]["rollout_selected_batches"] == 1
    assert payload["counts"]["rollout_blocked_batches"] == 1

    rollout = payload["rollout"]
    assert rollout["status"] == "included"
    assert rollout["batch_count"] == 2
    assert [batch["id"] for batch in rollout["selected_batches"]] == ["namespace:dev"]
    assert [batch["id"] for batch in rollout["blocked_batches"]] == ["namespace:prod"]
    blocked = rollout["blocked_batches"][0]
    assert blocked["change_window"] == "standard"
    assert blocked["blast_radius"] == {
        "count": 2,
        "total_risk": 12.5,
        "namespace_count": 1,
        "policy_count": 2,
        "owner_count": 1,
    }
    assert blocked["rollout_allowed"] is False
    assert blocked["rollout_reasons"] == [
        "count>1",
        "total_risk>10",
        "policies>1",
    ]


def test_concise_markdown_surfaces_rollout_blockers_and_selected_batches(
    tmp_path: Path,
) -> None:
    inputs = _write_core_inputs(tmp_path)
    batches_path = _write_rollout_batches(tmp_path)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--batches",
        str(batches_path),
        "--rollout-max-count",
        "1",
        "--rollout-max-total-risk",
        "10",
        "--rollout-max-policies",
        "1",
        "--markdown-mode",
        "concise",
    )

    assert code == 0
    assert stderr == ""
    assert "## Rollout Batch Summary" in stdout
    assert "| Rollout batches | 2 |" in stdout
    assert "| Rollout selected batches | 1 |" in stdout
    assert "| Rollout blocked batches | 1 |" in stdout
    assert "Selected rollout batches: 1 of 2" in stdout
    assert "Blocked rollout batches: 1" in stdout
    assert "| Blocked batch | Reasons | Count | Total risk |" in stdout
    assert "| namespace:prod | count>1, total_risk>10, policies>1 | 2 | 12.5 |" in stdout
    assert "| Selected batch | Window | Count | Total risk | IDs |" in stdout
    assert "| namespace:dev | standard | 1 | 2 | 003 |" in stdout
    assert "```diff" not in stdout


def test_id_filter_and_max_diffs_limit_selected_patch_diffs(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--id",
        "001",
        "--id",
        "002",
        "--max-diffs",
        "1",
        "--format",
        "json",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["filters"]["ids"] == ["001", "002"]
    assert payload["counts"]["selected_patch_records"] == 1
    assert payload["counts"]["patch_diffs_included"] == 1
    assert [item["id"] for item in payload["patch_diffs"]] == ["001"]
    assert "nginx:stable" in payload["patch_diffs"][0]["diff"]


def test_missing_optional_schedule_and_queue_are_skipped(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    missing_schedule = tmp_path / "missing-schedule.json"
    missing_queue = tmp_path / "missing-queue.db"

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--schedule",
        str(missing_schedule),
        "--queue-db",
        str(missing_queue),
    )

    assert code == 0
    assert stderr == ""
    assert "## Schedule Summary" in stdout
    assert f"Skipped: `{missing_schedule}` does not exist." in stdout
    assert "## Queue Report" in stdout
    assert f"Skipped: `{missing_queue}` does not exist." in stdout


def test_artifact_records_are_included_in_json(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    artifact = tmp_path / "review" / "artifact.txt"
    artifact.parent.mkdir()
    content = b"packet evidence\n"
    artifact.write_bytes(content)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--artifact",
        str(artifact),
        "--format",
        "json",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["counts"]["artifact_records"] == 1
    assert payload["artifacts"]["status"] == "included"
    record = payload["artifacts"]["records"][0]
    assert record["path"] == str(artifact)
    assert record["absolute_path"] == str(artifact)
    assert record["exists"] is True
    assert record["size_bytes"] == len(content)
    assert record["sha256"] == hashlib.sha256(content).hexdigest()


def test_out_writes_parent_dirs_and_suppresses_stdout(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    out_path = tmp_path / "packets" / "operator-review.md"

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--out",
        str(out_path),
    )

    assert code == 0
    assert stdout == ""
    assert stderr == ""
    assert out_path.read_text(encoding="utf-8").startswith("# Operator Review Packet\n")


def test_missing_required_input_reports_clear_error(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    missing_detections = tmp_path / "missing-detections.json"

    code, stdout, stderr = _run(
        "--detections",
        str(missing_detections),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
    )

    assert code == 2
    assert stdout == ""
    assert f"detections file not found: {missing_detections}" in stderr


def test_schedule_output_fields_are_normalised_for_explanation() -> None:
    records = [
        {"id": "cli-schedule", "score": 1.0, "R": 40.0, "p": 0.5, "Et": 2.0},
    ]

    normalised = build_review_packet._normalise_schedule_candidates(records)

    assert normalised[0]["risk"] == 40.0
    assert normalised[0]["probability"] == 0.5
    assert normalised[0]["expected_time"] == 2.0


def test_malformed_required_input_reports_clear_error(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    inputs["patches"].write_text("[not-json", encoding="utf-8")

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
    )

    assert code == 2
    assert stdout == ""
    assert "error: failed to parse patches file" in stderr


def test_rollout_limit_errors_are_reported(tmp_path: Path) -> None:
    inputs = _write_core_inputs(tmp_path)
    batches_path = _write_rollout_batches(tmp_path)

    code, stdout, stderr = _run(
        "--detections",
        str(inputs["detections"]),
        "--patches",
        str(inputs["patches"]),
        "--verified",
        str(inputs["verified"]),
        "--batches",
        str(batches_path),
        "--rollout-max-count",
        "0",
    )

    assert code == 2
    assert stdout == ""
    assert "error: max_count must be a positive integer" in stderr


def _run(*args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = build_review_packet.main(list(args), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _write_core_inputs(tmp_path: Path) -> dict[str, Path]:
    detections_path = tmp_path / "detections.json"
    patches_path = tmp_path / "patches.json"
    verified_path = tmp_path / "verified.json"

    detections_path.write_text(
        json.dumps(
            [
                {
                    "id": "001",
                    "manifest_yaml": POD_MANIFEST,
                    "policy_id": "no_latest_tag",
                },
                {
                    "id": "002",
                    "manifest_yaml": SECOND_POD_MANIFEST,
                    "policy_id": "no_latest_tag",
                },
                {
                    "id": "003",
                    "manifest_yaml": CONFIG_MAP_MANIFEST,
                    "policy_id": "config_mode",
                },
            ]
        ),
        encoding="utf-8",
    )
    patches_path.write_text(
        json.dumps(
            [
                {
                    "id": "001",
                    "policy_id": "no_latest_tag",
                    "accepted": True,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/0/image",
                            "value": "nginx:stable",
                        }
                    ],
                },
                {
                    "id": "002",
                    "policy_id": "no_latest_tag",
                    "accepted": True,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/spec/containers/0/image",
                            "value": "busybox:1.36",
                        }
                    ],
                },
                {
                    "id": "003",
                    "policy_id": "config_mode",
                    "accepted": True,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/data/mode",
                            "value": "safe",
                        }
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )
    verified_path.write_text(
        json.dumps(
            [
                {
                    "id": "001",
                    "policy_id": "no_latest_tag",
                    "accepted": True,
                    "ok_schema": True,
                    "ok_policy": True,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "errors": [],
                },
                {
                    "id": "002",
                    "policy_id": "no_latest_tag",
                    "accepted": False,
                    "ok_schema": True,
                    "ok_policy": False,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "errors": ["container still uses latest tag"],
                },
            ]
        ),
        encoding="utf-8",
    )

    return {
        "detections": detections_path,
        "patches": patches_path,
        "verified": verified_path,
    }


def _write_rollout_batches(tmp_path: Path) -> Path:
    batches_path = tmp_path / "batches.json"
    batches_path.write_text(
        json.dumps(
            [
                {
                    "id": "namespace:prod",
                    "group_by": "namespace",
                    "group_key": "prod",
                    "ids": ["001", "002"],
                    "count": 2,
                    "total_risk": 12.5,
                    "max_score": 9.0,
                    "policies": ["no_latest_tag", "run_as_non_root"],
                    "namespaces": ["prod"],
                    "owners": ["platform"],
                    "root_causes": ["image_tag"],
                },
                {
                    "id": "namespace:dev",
                    "group_by": "namespace",
                    "group_key": "dev",
                    "ids": ["003"],
                    "count": 1,
                    "total_risk": 2.0,
                    "max_score": 4.0,
                    "policies": ["config_mode"],
                    "namespaces": ["dev"],
                    "owners": ["apps"],
                    "root_causes": ["config"],
                },
            ]
        ),
        encoding="utf-8",
    )
    return batches_path
