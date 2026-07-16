import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.compare_schedulers import compare_schedulers
from scripts.plot_scheduler_waits import load_waits


class SchedulerComparisonTests(unittest.TestCase):
    def test_comparison_labels_static_replay_and_exact_top_cohort(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            detections = root / "detections.json"
            verified = root / "verified.json"
            output = root / "comparison.json"
            detections.write_text(
                json.dumps(
                    [
                        {"id": "low", "policy_id": "startup_port"},
                        {"id": "high", "policy_id": "no_privileged"},
                        {"id": "mid", "policy_id": "no_latest_tag"},
                    ]
                ),
                encoding="utf-8",
            )
            verified.write_text(
                json.dumps([{"id": item, "accepted": True} for item in ("low", "high", "mid")]),
                encoding="utf-8",
            )

            result = compare_schedulers(
                verified_path=verified,
                detections_path=detections,
                risk_path=None,
                policy_metrics_path=None,
                out_path=output,
                alpha=1.0,
                epsilon=1e-6,
                top_n=1,
            )
            cohort_size, waits = load_waits(output)

        self.assertEqual(cohort_size, 1)
        self.assertIn("risk_priority", result["telemetry"])
        self.assertNotIn("baseline", result["telemetry"])
        self.assertEqual(result["configuration"]["nonzero_wait_inputs"], 0)
        self.assertEqual(result["configuration"]["nonzero_exploration_inputs"], 0)
        self.assertEqual(waits["risk_priority"]["p95"], 0.0)
        self.assertGreater(waits["fifo"]["p95"], 0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
