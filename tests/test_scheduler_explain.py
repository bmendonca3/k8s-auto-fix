import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import scheduler_explain


class SchedulerExplainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "candidates.json"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write_records(self, records: list[dict[str, object]]) -> None:
        self.path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def _run(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = scheduler_explain.main([str(self.path), *args], stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_output_orders_candidates_by_scheduler_score(self) -> None:
        self._write_records(
            [
                {
                    "id": "slow-low",
                    "risk": 20.0,
                    "probability": 0.5,
                    "expected_time": 10.0,
                },
                {
                    "id": "kev-medium",
                    "risk": 30.0,
                    "probability": 1.0,
                    "expected_time": 10.0,
                    "kev": True,
                },
                {
                    "id": "fast-high",
                    "risk": 50.0,
                    "probability": 1.0,
                    "expected_time": 5.0,
                },
            ]
        )

        code, stdout, stderr = self._run("--json")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(
            [candidate["id"] for candidate in payload["candidates"]],
            ["fast-high", "kev-medium", "slow-low"],
        )
        self.assertEqual(
            [candidate["priority"] for candidate in payload["candidates"]],
            [1, 2, 3],
        )

    def test_markdown_output_explains_score_inputs(self) -> None:
        self._write_records(
            [
                {
                    "id": "pipe|id",
                    "risk": 12.0,
                    "probability": 0.5,
                    "expected_time": 3.0,
                    "wait": 0.25,
                    "explore": 0.5,
                }
            ]
        )

        code, stdout, stderr = self._run("--alpha", "2", "--explore-weight", "3")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("# Scheduler Priority Explanation", stdout)
        self.assertIn("Formula: `score = (risk * probability)", stdout)
        self.assertIn(
            "| Priority | ID | Score | Risk | Probability | Expected time | Wait | KEV | Explore | Risk/time | Explore bonus | Wait bonus | KEV bonus |",
            stdout,
        )
        self.assertIn("| 1 | pipe\\|id | 4 | 12 | 0.5 | 3 | 0.25 | no | 0.5 | 2 | 1.5 | 0.5 | 0 |", stdout)

    def test_json_output_includes_parameters_inputs_and_components(self) -> None:
        self._write_records(
            [
                {
                    "id": "kev-explore",
                    "risk": 40.0,
                    "probability": 0.25,
                    "expected_time": 5.0,
                    "wait": 0.5,
                    "kev": True,
                    "explore": 0.25,
                }
            ]
        )

        code, stdout, stderr = self._run(
            "--json",
            "--alpha",
            "2",
            "--kev-weight",
            "4",
            "--explore-weight",
            "3",
        )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(
            payload["parameters"],
            {"alpha": 2.0, "epsilon": 1e-06, "kev_weight": 4.0, "explore_weight": 3.0},
        )
        candidate = payload["candidates"][0]
        self.assertEqual(candidate["inputs"]["kev"], True)
        self.assertEqual(candidate["components"]["risk_probability_over_time"], 2.0)
        self.assertEqual(candidate["components"]["explore_bonus"], 0.75)
        self.assertEqual(candidate["components"]["wait_bonus"], 1.0)
        self.assertEqual(candidate["components"]["kev_bonus"], 4.0)
        self.assertEqual(candidate["score"], 7.75)

    def test_malformed_json_reports_clear_error(self) -> None:
        self.path.write_text("[not-json", encoding="utf-8")

        code, stdout, stderr = self._run()

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("error: failed to parse", stderr)

    def test_missing_required_field_reports_clear_error(self) -> None:
        self._write_records(
            [
                {
                    "id": "missing-time",
                    "risk": 10.0,
                    "probability": 0.5,
                }
            ]
        )

        code, stdout, stderr = self._run()

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("record 0 missing required field(s): expected_time", stderr)

    def test_invalid_epsilon_reports_clear_error(self) -> None:
        self._write_records(
            [
                {
                    "id": "zero-time",
                    "risk": 10.0,
                    "probability": 0.5,
                    "expected_time": 0.0,
                }
            ]
        )

        code, stdout, stderr = self._run("--epsilon", "0")

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("--epsilon must be greater than 0", stderr)


if __name__ == "__main__":
    unittest.main()
