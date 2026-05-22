import hashlib
import io
import json
from pathlib import Path

from scripts import build_evidence_manifest


def test_json_manifest_combines_spec_and_cli_artifacts(tmp_path: Path, monkeypatch) -> None:
    metrics = tmp_path / "data" / "metrics.json"
    patches = tmp_path / "data" / "patches.json"
    metrics.parent.mkdir()
    metrics_content = b'{"auto_fix_rate": 0.9}\n'
    patches_content = b'[{"id": "001"}]\n'
    metrics.write_bytes(metrics_content)
    patches.write_bytes(patches_content)
    spec = tmp_path / "evidence-spec.json"
    spec.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": "data/metrics.json",
                        "producer_command": "make metrics",
                        "claim_labels": ["paper:table-1", "claim:auto-fix-rate"],
                        "category": "metric",
                        "note": "main reported metric",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--spec",
        "evidence-spec.json",
        "--artifact",
        "data/patches.json",
        "--producer-command",
        "make propose",
        "--claim",
        "claim:patch-output",
        "--category",
        "pipeline-output",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["schema_version"] == 1
    assert payload["record_count"] == 2
    assert payload["claim_count"] == 3
    assert "claim_table_coverage" not in payload
    assert "pipeline_sources" not in payload
    assert "pipeline_stages" not in payload
    assert payload["claims"] == [
        {
            "claim": "claim:auto-fix-rate",
            "artifact_count": 1,
            "present_count": 1,
            "missing_count": 0,
            "paths": ["data/metrics.json"],
        },
        {
            "claim": "claim:patch-output",
            "artifact_count": 1,
            "present_count": 1,
            "missing_count": 0,
            "paths": ["data/patches.json"],
        },
        {
            "claim": "paper:table-1",
            "artifact_count": 1,
            "present_count": 1,
            "missing_count": 0,
            "paths": ["data/metrics.json"],
        },
    ]
    assert payload["artifacts"][0] == {
        "absolute_path": str(metrics.resolve()),
        "category": "metric",
        "claim_labels": ["paper:table-1", "claim:auto-fix-rate"],
        "exists": True,
        "kind": "file",
        "note": "main reported metric",
        "path": "data/metrics.json",
        "producer_command": "make metrics",
        "sha256": hashlib.sha256(metrics_content).hexdigest(),
        "size_bytes": len(metrics_content),
    }
    assert payload["artifacts"][1]["path"] == "data/patches.json"
    assert payload["artifacts"][1]["producer_command"] == "make propose"
    assert payload["artifacts"][1]["claim_labels"] == ["claim:patch-output"]
    assert payload["artifacts"][1]["category"] == "pipeline-output"
    assert payload["artifacts"][1]["sha256"] == hashlib.sha256(
        patches_content
    ).hexdigest()


def test_claims_table_marks_expected_claim_coverage(
    tmp_path: Path, monkeypatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text("# evidence\n", encoding="utf-8")
    claims_table = tmp_path / "claims.json"
    claims_table.write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "id": "claim:auto-fix-rate",
                        "title": "Auto-fix rate",
                        "description": "Reported acceptance metric",
                    },
                    {
                        "id": "claim:paper-table",
                        "label": "paper:table-1",
                        "title": "Paper table row",
                    },
                    {
                        "label": "claim:uncovered",
                        "title": "Uncovered claim",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "report.md",
        "--claim",
        "claim:auto-fix-rate",
        "--claim",
        "paper:table-1",
        "--claims-table",
        "claims.json",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["claim_count"] == 2
    assert payload["claims"] == [
        {
            "claim": "claim:auto-fix-rate",
            "artifact_count": 1,
            "present_count": 1,
            "missing_count": 0,
            "paths": ["report.md"],
        },
        {
            "claim": "paper:table-1",
            "artifact_count": 1,
            "present_count": 1,
            "missing_count": 0,
            "paths": ["report.md"],
        },
    ]
    assert payload["claim_table_coverage"] == {
        "source_path": "claims.json",
        "claim_count": 3,
        "covered_count": 2,
        "uncovered_count": 1,
        "claims": [
            {
                "id": "claim:auto-fix-rate",
                "label": None,
                "title": "Auto-fix rate",
                "description": "Reported acceptance metric",
                "match_labels": ["claim:auto-fix-rate"],
                "matched_claim_labels": ["claim:auto-fix-rate"],
                "has_evidence": True,
                "artifact_count": 1,
                "present_count": 1,
                "missing_count": 0,
                "paths": ["report.md"],
            },
            {
                "id": "claim:paper-table",
                "label": "paper:table-1",
                "title": "Paper table row",
                "description": None,
                "match_labels": ["claim:paper-table", "paper:table-1"],
                "matched_claim_labels": ["paper:table-1"],
                "has_evidence": True,
                "artifact_count": 1,
                "present_count": 1,
                "missing_count": 0,
                "paths": ["report.md"],
            },
            {
                "id": None,
                "label": "claim:uncovered",
                "title": "Uncovered claim",
                "description": None,
                "match_labels": ["claim:uncovered"],
                "matched_claim_labels": [],
                "has_evidence": False,
                "artifact_count": 0,
                "present_count": 0,
                "missing_count": 0,
                "paths": [],
            },
        ],
    }


def test_markdown_manifest_renders_claims_and_missing_records(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "report.md"
    content = b"# report\n"
    artifact.write_bytes(content)
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "report.md",
        "--artifact",
        "missing.json",
        "--producer-command",
        "python scripts/report.py",
        "--claim",
        "claim:operator-review",
        "--allow-missing",
        "--format",
        "markdown",
    )

    assert code == 0
    assert stderr == ""
    assert stdout.startswith("# Evidence Manifest\n\n")
    assert "Artifact records: 2" in stdout
    assert "| Path | Status | Producer command | Claims | Category | Size bytes | SHA-256 | Note |" in stdout
    assert (
        "`report.md` | present | `python scripts/report.py` | claim:operator-review"
        in stdout
    )
    assert hashlib.sha256(content).hexdigest() in stdout
    assert "`missing.json` | missing | `python scripts/report.py` | claim:operator-review" in stdout
    assert "## Claim Coverage" in stdout
    assert (
        "| claim:operator-review | 2 | 1 | 1 | `missing.json`, `report.md` |"
        in stdout
    )
    assert "## Claim Table Coverage" not in stdout


def test_markdown_manifest_summarizes_claim_table_coverage(
    tmp_path: Path, monkeypatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text("# evidence\n", encoding="utf-8")
    claims_table = tmp_path / "claims.json"
    claims_table.write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "id": "claim:covered",
                        "title": "Covered claim",
                    },
                    {
                        "id": "claim:missing",
                        "title": "Missing claim",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "report.md",
        "--claim",
        "claim:covered",
        "--claims-table",
        "claims.json",
        "--format",
        "markdown",
    )

    assert code == 0
    assert stderr == ""
    assert "## Claim Table Coverage" in stdout
    assert "Claims table: `claims.json`" in stdout
    assert "Expected claims: 2; covered: 1; uncovered: 1" in stdout
    assert (
        "| Claim | Title | Evidence | Artifacts | Present | Missing | Paths |"
        in stdout
    )
    assert "| claim:covered | Covered claim | covered | 1 | 1 | 0 | `report.md` |" in stdout
    assert "| claim:missing | Missing claim | uncovered | 0 | 0 | 0 |  |" in stdout


def test_fail_on_uncovered_claims_exits_nonzero_after_rendering_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text("# evidence\n", encoding="utf-8")
    claims_table = tmp_path / "claims.json"
    claims_table.write_text(
        json.dumps(
            {
                "claims": [
                    {"id": "claim:covered", "title": "Covered claim"},
                    {"id": "claim:missing", "title": "Missing claim"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "report.md",
        "--claim",
        "claim:covered",
        "--claims-table",
        "claims.json",
        "--fail-on-uncovered-claims",
    )

    assert code == 1
    assert "error: uncovered expected claims: claim:missing" in stderr
    payload = json.loads(stdout)
    assert payload["claim_table_coverage"]["uncovered_count"] == 1


def test_fail_on_uncovered_claims_passes_when_claims_table_is_fully_covered(
    tmp_path: Path, monkeypatch
) -> None:
    report = tmp_path / "report.md"
    report.write_text("# evidence\n", encoding="utf-8")
    claims_table = tmp_path / "claims.json"
    claims_table.write_text(
        json.dumps(
            {
                "claims": [
                    {"id": "claim:covered", "title": "Covered claim"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "report.md",
        "--claim",
        "claim:covered",
        "--claims-table",
        "claims.json",
        "--fail-on-uncovered-claims",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["claim_table_coverage"]["uncovered_count"] == 0


def test_invalid_claims_table_reports_clear_error(tmp_path: Path) -> None:
    artifact = tmp_path / "report.md"
    artifact.write_text("# evidence\n", encoding="utf-8")
    claims_table = tmp_path / "claims.json"
    claims_table.write_text('{"claimz": []}', encoding="utf-8")

    code, stdout, stderr = _run(
        "--artifact",
        str(artifact),
        "--claims-table",
        str(claims_table),
    )

    assert code == 2
    assert stdout == ""
    assert f"claims table {claims_table} must include a claims array" in stderr


def test_pipeline_manifest_adds_stage_metadata_without_rehashing(
    tmp_path: Path, monkeypatch
) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text('{"ok": true}\n', encoding="utf-8")
    manifest_input = tmp_path / "inputs" / "pod.yaml"
    manifest_input.parent.mkdir()
    manifest_input.write_text("actual input bytes\n", encoding="utf-8")
    declared_input_hash = "a" * 64
    declared_output_hash = "b" * 64
    pipeline_manifest = tmp_path / "pipeline-manifest.json"
    pipeline_manifest.write_text(
        json.dumps(
            {
                "mode": "dry-run",
                "timestamp": "2026-05-21T00:00:00Z",
                "stages": [
                    {
                        "name": "detect",
                        "command_string": "python -m src.detector.cli",
                        "input_paths": ["inputs/pod.yaml"],
                        "input_metadata": [
                            {
                                "exists": True,
                                "path": "inputs/pod.yaml",
                                "sha256": declared_input_hash,
                                "size_bytes": 123,
                                "type": "file",
                            }
                        ],
                        "output_paths": ["data/detections.json"],
                        "output_metadata": [
                            {
                                "exists": True,
                                "path": "data/detections.json",
                                "sha256": declared_output_hash,
                                "size_bytes": 456,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "evidence.json",
        "--pipeline-manifest",
        "pipeline-manifest.json",
    )

    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["pipeline_sources"] == [
        {
            "kind": "pipeline_manifest",
            "mode": "dry-run",
            "path": "pipeline-manifest.json",
            "stage_count": 1,
            "timestamp": "2026-05-21T00:00:00Z",
        }
    ]
    assert payload["pipeline_stages"] == [
        {
            "command_string": "python -m src.detector.cli",
            "inputs": [
                {
                    "exists": True,
                    "path": "inputs/pod.yaml",
                    "sha256": declared_input_hash,
                    "size_bytes": 123,
                    "type": "file",
                }
            ],
            "name": "detect",
            "outputs": [
                {
                    "exists": True,
                    "path": "data/detections.json",
                    "sha256": declared_output_hash,
                    "size_bytes": 456,
                }
            ],
            "source_kind": "pipeline_manifest",
            "source_path": "pipeline-manifest.json",
        }
    ]
    assert payload["pipeline_stages"][0]["inputs"][0]["sha256"] != hashlib.sha256(
        manifest_input.read_bytes()
    ).hexdigest()


def test_pipeline_status_markdown_summarizes_stages(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "report.md"
    artifact.write_text("# report\n", encoding="utf-8")
    status_path = tmp_path / "pipeline-status.json"
    status_path.write_text(
        json.dumps(
            {
                "mode": "run",
                "resume": False,
                "schema_version": 1,
                "stages": [
                    {
                        "name": "verify",
                        "status": "failed",
                        "returncode": 23,
                        "command_string": "python -m src.verifier.cli",
                        "input_paths": ["data/patches.json"],
                        "input_metadata": [
                            {
                                "exists": True,
                                "path": "data/patches.json",
                                "sha256": "c" * 64,
                                "size_bytes": 17,
                                "type": "file",
                            }
                        ],
                        "output_paths": ["data/verified.json"],
                        "output_metadata": [
                            {
                                "exists": False,
                                "path": "data/verified.json",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "report.md",
        "--pipeline-status",
        "pipeline-status.json",
        "--format",
        "markdown",
    )

    assert code == 0
    assert stderr == ""
    assert "## Pipeline Stages" in stdout
    assert "| Source | Stage | Status | Inputs | Outputs | Command |" in stdout
    assert (
        "| `pipeline_status:pipeline-status.json` | verify | failed | "
        "`data/patches.json` (present, sha256 `cccccccccccc`, 17 bytes) | "
        "`data/verified.json` (missing) | `python -m src.verifier.cli` |"
        in stdout
    )


def test_missing_artifact_without_allow_missing_is_clear_error(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run("--artifact", "missing.json")

    assert code == 2
    assert stdout == ""
    assert "error: artifact not found: missing.json" in stderr


def test_invalid_spec_reports_clear_error(tmp_path: Path) -> None:
    spec = tmp_path / "bad.json"
    spec.write_text('{"artifacts": [{}]}', encoding="utf-8")

    code, stdout, stderr = _run("--spec", str(spec))

    assert code == 2
    assert stdout == ""
    assert "evidence artifact record must include a non-empty path" in stderr


def test_out_writes_parent_dirs_and_suppresses_stdout(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("evidence\n", encoding="utf-8")
    out_path = tmp_path / "nested" / "manifest.json"
    monkeypatch.chdir(tmp_path)

    code, stdout, stderr = _run(
        "--artifact",
        "artifact.txt",
        "--out",
        str(out_path),
    )

    assert code == 0
    assert stdout == ""
    assert stderr == ""
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["artifacts"][0]["path"] == "artifact.txt"


def _run(*args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = build_evidence_manifest.main(list(args), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()
