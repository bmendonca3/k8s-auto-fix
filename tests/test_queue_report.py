import io
import json
import sqlite3
from pathlib import Path

from scripts import queue_report
from src.scheduler.queue import DB_SCHEMA


def test_markdown_report_includes_health_signals(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    db_path = tmp_path / "queue.db"
    _write_queue_db(
        db_path,
        [
            {
                "id": "kev-old",
                "policy_id": "critical_policy",
                "state": "queued",
                "attempts": 0,
                "max_attempts": 3,
                "enqueued_at": now - 3 * 3600,
                "risk": 50.0,
                "probability": 0.8,
                "expected_time": 10.0,
                "kev": 1,
            },
            {
                "id": "high-risk",
                "policy_id": "risky_policy",
                "state": "queued",
                "attempts": 2,
                "max_attempts": 3,
                "enqueued_at": now - 30 * 60,
                "risk": 90.0,
                "probability": 0.9,
                "expected_time": 10.0,
                "kev": 0,
            },
            {
                "id": "retry-risk",
                "policy_id": "retry_policy",
                "state": "queued",
                "attempts": 3,
                "max_attempts": 3,
                "enqueued_at": now - 10 * 60,
                "risk": 10.0,
                "probability": 0.5,
                "expected_time": 10.0,
                "kev": 0,
            },
            {
                "id": "complete",
                "policy_id": "done_policy",
                "state": "done",
                "attempts": 1,
                "max_attempts": 3,
                "enqueued_at": now - 60,
                "risk": 20.0,
                "probability": 0.4,
                "expected_time": 5.0,
                "kev": 0,
            },
        ],
    )

    report = queue_report.build_report(db_path, now=now, top=2, kev_weight=5.0)
    markdown = queue_report.render_markdown(report)

    assert "# Scheduler Queue Report" in markdown
    assert "| done | 1 |" in markdown
    assert "| queued | 3 |" in markdown
    assert "| Items with attempts | 3 |" in markdown
    assert "| Items one attempt from max | 1 |" in markdown
    assert "| Queued items at or over max attempts | 1 |" in markdown
    assert "`kev-old` has been queued for 3h" in markdown
    assert "| 1 | `kev-old` | critical_policy |" in markdown
    assert "| 2 | `high-risk` | risky_policy |" in markdown
    assert "retry-risk" not in markdown


def test_json_cli_reports_queue_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.db"
    _write_queue_db(
        db_path,
        [
            {
                "id": "older-slow",
                "policy_id": "old_policy",
                "state": "queued",
                "attempts": 0,
                "max_attempts": 3,
                "enqueued_at": 1_700_000_000.0,
                "risk": 10.0,
                "probability": 0.5,
                "expected_time": 30.0,
                "kev": 0,
            },
            {
                "id": "newer-fast",
                "policy_id": "fast_policy",
                "state": "queued",
                "attempts": 1,
                "max_attempts": 2,
                "enqueued_at": 1_700_003_000.0,
                "risk": 100.0,
                "probability": 1.0,
                "expected_time": 1.0,
                "kev": 0,
            },
            {
                "id": "failed",
                "policy_id": "failed_policy",
                "state": "failed",
                "attempts": 3,
                "max_attempts": 3,
                "enqueued_at": 1_700_002_000.0,
                "risk": 50.0,
                "probability": 0.5,
                "expected_time": 5.0,
                "kev": 0,
            },
        ],
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = queue_report.main([str(db_path), "--json", "--top", "1"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    data = json.loads(stdout.getvalue())
    assert data["summary"]["total_items"] == 3
    assert data["summary"]["state_counts"] == {"failed": 1, "queued": 2}
    assert data["attempts"]["items_one_attempt_from_max"] == 1
    assert data["attempts"]["items_at_or_over_max_attempts"] == 1
    assert data["oldest_queued"]["id"] == "older-slow"
    assert data["top_queued"][0]["id"] == "newer-fast"
    assert data["top_queued"][0]["attempts"] == 1
    assert data["top_queued"][0]["max_attempts"] == 2


def test_markdown_report_escapes_pipe_in_queued_ids(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    db_path = tmp_path / "queue.db"
    _write_queue_db(
        db_path,
        [
            {
                "id": "queued|pipe",
                "policy_id": "policy|pipe",
                "state": "queued",
                "attempts": 0,
                "max_attempts": 3,
                "enqueued_at": now,
                "risk": 20.0,
                "probability": 0.8,
                "expected_time": 4.0,
                "kev": 0,
            },
        ],
    )

    markdown = queue_report.render_markdown(queue_report.build_report(db_path, now=now))

    assert "`queued\\|pipe`" in markdown
    assert "policy\\|pipe" in markdown


def test_missing_db_and_missing_items_table_fail_clearly(tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.db"
    stdout = io.StringIO()
    stderr = io.StringIO()

    missing_exit = queue_report.main([str(missing_db)], stdout=stdout, stderr=stderr)

    assert missing_exit == 2
    assert stdout.getvalue() == ""
    assert "database not found" in stderr.getvalue()

    empty_db = tmp_path / "empty.db"
    sqlite3.connect(empty_db).close()
    stdout = io.StringIO()
    stderr = io.StringIO()

    table_exit = queue_report.main([str(empty_db)], stdout=stdout, stderr=stderr)

    assert table_exit == 2
    assert stdout.getvalue() == ""
    assert "missing required table: items" in stderr.getvalue()


def test_missing_required_column_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "partial.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE items (id TEXT PRIMARY KEY, state TEXT)")
        conn.commit()
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = queue_report.main([str(db_path)], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "items table missing required column(s):" in stderr.getvalue()
    assert "policy_id" in stderr.getvalue()


def test_report_does_not_modify_database(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.db"
    _write_queue_db(
        db_path,
        [
            {
                "id": "queued",
                "policy_id": "stable_policy",
                "state": "queued",
                "attempts": 0,
                "max_attempts": 3,
                "enqueued_at": 1_700_000_000.0,
                "risk": 20.0,
                "probability": 0.8,
                "expected_time": 4.0,
                "kev": 0,
            },
        ],
    )
    before_bytes = db_path.read_bytes()
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = queue_report.main([str(db_path), "--json"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert db_path.read_bytes() == before_bytes
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
        assert conn.execute("SELECT state FROM items WHERE id='queued'").fetchone()[0] == "queued"


def _write_queue_db(db_path: Path, rows: list[dict[str, object]]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(DB_SCHEMA)
        for row in rows:
            conn.execute(
                """
                INSERT INTO items (
                    id, policy_id, state, attempts, max_attempts, enqueued_at,
                    last_update, risk, probability, expected_time, kev, wait
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["policy_id"],
                    row["state"],
                    row["attempts"],
                    row["max_attempts"],
                    row["enqueued_at"],
                    row.get("last_update", row["enqueued_at"]),
                    row["risk"],
                    row["probability"],
                    row["expected_time"],
                    row["kev"],
                    row.get("wait", 0.0),
                ),
            )
        conn.commit()
