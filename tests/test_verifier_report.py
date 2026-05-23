import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import verifier_report


class VerifierReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "verified.json"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write_records(self, records: list[dict[str, object]]) -> None:
        self.path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def _run_report(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = verifier_report.main([str(self.path), *args], stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_markdown_groups_rejections_and_actions(self) -> None:
        self._write_records(
            [
                {
                    "id": "accepted",
                    "policy_id": "no_latest_tag",
                    "accepted": True,
                    "ok_schema": True,
                    "ok_policy": True,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "errors": [],
                },
                {
                    "id": "schema-1",
                    "policy_id": "no_latest_tag",
                    "accepted": False,
                    "ok_schema": False,
                    "ok_policy": True,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "errors": ["kubectl dry-run failed: invalid field"],
                },
                {
                    "id": "safety-1",
                    "policy_id": "no_host_path",
                    "accepted": False,
                    "ok_schema": True,
                    "ok_policy": True,
                    "ok_safety": False,
                    "ok_rescan": True,
                    "errors": ["hostPath '/tmp' not in allowlist"],
                },
                {
                    "id": "safety-2",
                    "policy_id": "no_host_path",
                    "accepted": False,
                    "ok_schema": True,
                    "ok_policy": True,
                    "ok_safety": False,
                    "ok_rescan": True,
                    "errors": ["hostPath '/tmp' not in allowlist"],
                },
                {
                    "id": "policy-1",
                    "policy_id": "no_privileged",
                    "accepted": False,
                    "ok_schema": True,
                    "ok_policy": False,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "errors": ["container remains privileged"],
                },
            ]
        )

        code, stdout, stderr = self._run_report()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("# Verifier Failure Report", stdout)
        self.assertIn("Total: 5 | Accepted: 1 | Rejected: 4", stdout)
        self.assertIn("| ok_safety | 2 | safety-1, safety-2 |", stdout)
        self.assertIn("| no_host_path | 2 | safety-1, safety-2 |", stdout)
        self.assertIn("| hostPath '/tmp' not in allowlist | 2 | safety-1, safety-2 |", stdout)
        self.assertIn("`ok_schema=false` (1):", stdout)
        self.assertIn("`ok_policy=false` (1):", stdout)
        self.assertIn("`ok_safety=false` (2):", stdout)

    def test_json_output_is_machine_readable(self) -> None:
        self._write_records(
            [
                {
                    "id": "rescan-1",
                    "policy_id": "run_as_non_root",
                    "accepted": False,
                    "ok_schema": True,
                    "ok_policy": True,
                    "ok_safety": True,
                    "ok_rescan": False,
                    "errors": ["rescan failed: residual violation"],
                }
            ]
        )

        code, stdout, stderr = self._run_report("--json")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["summary"], {"total": 1, "accepted": 0, "rejected": 1})
        self.assertEqual(payload["by_failing_gates"][0]["gates"], ["ok_rescan"])
        self.assertEqual(payload["by_policy_id"][0]["policy_id"], "run_as_non_root")
        self.assertEqual(payload["by_error"][0]["error"], "rescan failed: residual violation")
        self.assertEqual(payload["next_actions"][0]["gate"], "ok_rescan")

    def test_markdown_reports_when_no_rejections_exist(self) -> None:
        self._write_records(
            [
                {
                    "id": "accepted",
                    "policy_id": "no_latest_tag",
                    "accepted": True,
                    "ok_schema": True,
                    "ok_policy": True,
                    "ok_safety": True,
                    "ok_rescan": True,
                    "errors": [],
                }
            ]
        )

        code, stdout, stderr = self._run_report()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Total: 1 | Accepted: 1 | Rejected: 0", stdout)
        self.assertIn("No rejected verifier records found.", stdout)


if __name__ == "__main__":
    unittest.main()
