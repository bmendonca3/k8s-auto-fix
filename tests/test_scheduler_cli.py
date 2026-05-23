import json
from pathlib import Path

from typer.testing import CliRunner

from src.scheduler.cli import app


runner = CliRunner()


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_schedule_cli_keeps_default_schedule_output_unchanged(tmp_path: Path) -> None:
    verified = tmp_path / "verified.json"
    detections = tmp_path / "detections.json"
    out = tmp_path / "schedule.json"
    _write_json(
        verified,
        [
            {"id": "low", "accepted": True},
            {"id": "high", "accepted": True},
            {"id": "rejected", "accepted": False},
        ],
    )
    _write_json(
        detections,
        [
            {"id": "low", "policy_id": "no_latest_tag", "namespace": "dev"},
            {"id": "high", "policy_id": "no_privileged", "namespace": "prod"},
        ],
    )

    result = runner.invoke(
        app,
        [
            "--verified",
            str(verified),
            "--detections",
            str(detections),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    schedule = json.loads(out.read_text(encoding="utf-8"))
    assert [entry["id"] for entry in schedule] == ["high", "low"]
    assert set(schedule[0]) == {"id", "score", "R", "p", "Et", "wait", "kev"}
    assert "batch" not in result.output.lower()


def test_schedule_cli_writes_batch_summaries_from_scheduled_output(
    tmp_path: Path,
) -> None:
    verified = tmp_path / "verified.json"
    detections = tmp_path / "detections.json"
    out = tmp_path / "schedule.json"
    batches_out = tmp_path / "batches.json"
    _write_json(
        verified,
        [
            {"id": "prod-high", "accepted": True},
            {"id": "prod-low", "accepted": True},
            {"id": "dev", "accepted": True},
        ],
    )
    _write_json(
        detections,
        [
            {
                "id": "prod-high",
                "policy_id": "no_privileged",
                "namespace": "prod",
                "owner": "platform",
                "root_cause": "security_context",
            },
            {
                "id": "prod-low",
                "policy_id": "run_as_non_root",
                "namespace": "prod",
                "team": "platform",
                "root_cause": "security_context",
            },
            {
                "id": "dev",
                "policy_id": "no_latest_tag",
                "namespace": "dev",
                "owner": "apps",
                "root_cause": "image_tag",
            },
        ],
    )

    result = runner.invoke(
        app,
        [
            "--verified",
            str(verified),
            "--detections",
            str(detections),
            "--out",
            str(out),
            "--batch-group-by",
            "namespace",
            "--batch-max-size",
            "2",
            "--batches-out",
            str(batches_out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    batches = json.loads(batches_out.read_text(encoding="utf-8"))
    assert [batch["id"] for batch in batches] == ["namespace:prod", "namespace:dev"]
    assert batches[0]["ids"] == ["prod-high", "prod-low"]
    assert batches[0]["count"] == 2
    assert batches[0]["policies"] == ["no_privileged", "run_as_non_root"]
    assert batches[0]["owners"] == ["platform"]
    assert batches[0]["root_causes"] == ["security_context"]


def test_schedule_cli_emits_batches_to_stdout_when_no_batch_path(
    tmp_path: Path,
) -> None:
    verified = tmp_path / "verified.json"
    detections = tmp_path / "detections.json"
    out = tmp_path / "schedule.json"
    _write_json(verified, [{"id": "fix", "accepted": True}])
    _write_json(
        detections,
        [{"id": "fix", "policy_id": "no_host_path", "root_cause": "volume"}],
    )

    result = runner.invoke(
        app,
        [
            "--verified",
            str(verified),
            "--detections",
            str(detections),
            "--out",
            str(out),
            "--batch-group-by",
            "root_cause",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"group_by": "root_cause"' in result.output
    assert '"group_key": "volume"' in result.output


def test_schedule_cli_rejects_bad_batch_size(tmp_path: Path) -> None:
    verified = tmp_path / "verified.json"
    detections = tmp_path / "detections.json"
    out = tmp_path / "schedule.json"
    _write_json(verified, [{"id": "fix", "accepted": True}])
    _write_json(detections, [{"id": "fix", "policy_id": "no_host_path"}])

    result = runner.invoke(
        app,
        [
            "--verified",
            str(verified),
            "--detections",
            str(detections),
            "--out",
            str(out),
            "--batch-group-by",
            "policy",
            "--batch-max-size",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "max_batch_size must be a positive integer" in result.output
