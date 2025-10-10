import unittest
import json
from pathlib import Path

from scripts import update_metrics_docs as updater


class UpdateMetricsDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = updater.MetricsBundle(
            rules={
                "detections": 10,
                "accepted": 10,
                "median_patch_ops": 5,
            },
            grok_full={
                "detections": 10,
                "accepted": 10,
                "median_patch_ops": 6,
            },
            schedule={
                "summary": {
                    "top_n": 5,
                    "baseline": {
                        "mean_rank_top_n": 2.5,
                        "median_rank_top_n": 2.5,
                        "p95_rank_top_n": 4.0,
                    },
                    "fifo": {
                        "mean_rank_top_n": 50.0,
                        "median_rank_top_n": 50.0,
                        "p95_rank_top_n": 80.0,
                    },
                    "risk_only": {
                        "mean_rank_top_n": 2.5,
                        "median_rank_top_n": 2.5,
                        "p95_rank_top_n": 4.0,
                    },
                },
                "telemetry": {
                    "baseline": {
                        "items": 10,
                        "total_runtime_hours": 12.0,
                        "throughput_per_hour": 5.5,
                        "top_risk_wait_hours": {"p95": 1.5},
                    },
                    "fifo": {
                        "items": 10,
                        "total_runtime_hours": 12.0,
                        "throughput_per_hour": 5.5,
                        "top_risk_wait_hours": {"p95": 3.0},
                    },
                },
            },
            grok200_results=[
                {"count": 10, "accepted": 10},
                {"count": 10, "accepted": 9},
            ],
        )

    def test_build_readme_section(self) -> None:
        section = updater.build_readme_section(self.metrics)
        self.assertIn("10/10", section)
        self.assertIn("20 detections", section)
        self.assertIn("top 5 high-risk items", section)
        self.assertIn("5.5 patches/hour", section)

    def test_build_paper_paragraph(self) -> None:
        paragraph = updater.build_paper_paragraph(self.metrics)
        self.assertTrue(paragraph.startswith("\\noindent"))
        self.assertIn("100.0\\%", paragraph)
        self.assertIn("1.5\\,h", paragraph)
        self.assertIn("+1.5\\,h", paragraph)

    def test_scheduler_metrics_written(self) -> None:
        dashboards_path = Path("data/dashboard_metrics.json")
        dashboards_path.parent.mkdir(parents=True, exist_ok=True)
        dashboards_path.write_text(json.dumps({"scheduler_summary": {}, "scheduler_telemetry": {}}), encoding="utf-8")
        updater.run(dry_run=True)
        data = json.loads(dashboards_path.read_text())
        self.assertIn("scheduler_summary", data)
        self.assertIn("scheduler_telemetry", data)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
