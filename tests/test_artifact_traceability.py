import hashlib
import json
from pathlib import Path

from scripts import artifact_traceability


def test_json_records_include_hash_size_and_global_metadata(tmp_path, monkeypatch, capsys):
    artifact = tmp_path / "reports" / "artifact.json"
    artifact.parent.mkdir()
    content = b'{"ok": true}\n'
    artifact.write_bytes(content)
    monkeypatch.chdir(tmp_path)

    exit_code = artifact_traceability.main(
        [
            "--artifact",
            "reports/artifact.json",
            "--producer",
            "pipeline",
            "--category",
            "generated-output",
            "--note",
            "paper table",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {
        "artifacts": [
            {
                "absolute_path": str(artifact.resolve()),
                "category": "generated-output",
                "exists": True,
                "kind": "file",
                "note": "paper table",
                "path": "reports/artifact.json",
                "producer": "pipeline",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        ]
    }
    assert captured.err == ""


def test_markdown_output_reports_traceability_table(tmp_path, monkeypatch, capsys):
    artifact = tmp_path / "data" / "metrics.json"
    artifact.parent.mkdir()
    content = b"metrics\n"
    artifact.write_bytes(content)
    monkeypatch.chdir(tmp_path)

    exit_code = artifact_traceability.main(
        [
            "--artifact",
            "data/metrics.json",
            "--producer",
            "metrics",
            "--category",
            "report",
            "--note",
            "reviewed",
            "--format",
            "markdown",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("# Artifact Traceability\n\n")
    assert "| Path | Status | Kind | Producer | Category | Size bytes | SHA-256 | Note |" in captured.out
    assert "`data/metrics.json` | present | file | metrics | report | 8 |" in captured.out
    assert "`{}`".format(hashlib.sha256(content).hexdigest()) in captured.out
    assert "| reviewed |" in captured.out


def test_missing_artifact_is_clear_error_without_allow_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = artifact_traceability.main(["--artifact", "missing.json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "artifact not found: missing.json" in captured.err
    assert str(tmp_path / "missing.json") in captured.err


def test_allow_missing_includes_missing_record(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = artifact_traceability.main(
        [
            "--artifact",
            "missing.json",
            "--producer",
            "dry-run",
            "--category",
            "generated-output",
            "--allow-missing",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {
        "artifacts": [
            {
                "absolute_path": str((tmp_path / "missing.json").resolve(strict=False)),
                "category": "generated-output",
                "exists": False,
                "kind": "missing",
                "note": None,
                "path": "missing.json",
                "producer": "dry-run",
                "sha256": None,
                "size_bytes": None,
            }
        ]
    }
    assert captured.err == ""


def test_hashing_is_deterministic(tmp_path):
    artifact = tmp_path / "artifact.bin"
    content = b"same bytes produce the same digest\n"
    artifact.write_bytes(content)
    expected_sha256 = hashlib.sha256(content).hexdigest()

    first = artifact_traceability.trace_artifacts(
        paths=[Path("artifact.bin")],
        cwd=tmp_path,
        producer=None,
        category=None,
        note=None,
        allow_missing=False,
    )[0]
    second = artifact_traceability.trace_artifacts(
        paths=[Path("artifact.bin")],
        cwd=tmp_path,
        producer=None,
        category=None,
        note=None,
        allow_missing=False,
    )[0]

    assert first == second
    assert first.size_bytes == len(content)
    assert first.sha256 == expected_sha256


def test_symlink_record_hashes_the_link_entry(tmp_path, monkeypatch, capsys):
    target = tmp_path.parent / f"{tmp_path.name}-outside-artifact.txt"
    target.write_text("target bytes should not be hashed\n", encoding="utf-8")
    link = tmp_path / "linked-artifact"
    link.symlink_to(target)
    monkeypatch.chdir(tmp_path)

    exit_code = artifact_traceability.main(["--artifact", "linked-artifact"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    link_target = str(target)
    assert payload["artifacts"][0]["path"] == "linked-artifact"
    assert payload["artifacts"][0]["absolute_path"] == str(link)
    assert payload["artifacts"][0]["kind"] == "symlink"
    assert payload["artifacts"][0]["size_bytes"] == len(link_target.encode("utf-8"))
    assert payload["artifacts"][0]["sha256"] == hashlib.sha256(
        link_target.encode("utf-8")
    ).hexdigest()


def test_broken_symlink_record_hashes_the_link_entry(tmp_path, monkeypatch, capsys):
    target = tmp_path / "missing-target.txt"
    link = tmp_path / "broken-link"
    link.symlink_to(target)
    monkeypatch.chdir(tmp_path)

    exit_code = artifact_traceability.main(["--artifact", "broken-link"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    link_target = str(target)
    assert payload["artifacts"][0]["exists"] is True
    assert payload["artifacts"][0]["kind"] == "symlink"
    assert payload["artifacts"][0]["sha256"] == hashlib.sha256(
        link_target.encode("utf-8")
    ).hexdigest()
