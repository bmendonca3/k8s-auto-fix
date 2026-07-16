import unittest
import json
from pathlib import Path

from scripts import update_metrics_docs as updater


class UpdateMetricsDocsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = updater.MetricsBundle(
            rules={
                "detections": 10,
                "patches": 10,
                "accepted": 10,
                "auto_fix_rate": 1.0,
                "median_patch_ops": 5,
            },
            rules_5000={
                "detections": 20,
                "accepted": 19,
                "median_patch_ops": 6,
            },
            supported_rules={
                "detections": 3,
                "accepted": 3,
                "median_patch_ops": 4,
            },
            grok_full={
                "detections": 10,
                "accepted": 10,
                "median_patch_ops": 6,
            },
            grok5k={
                "detections": 20,
                "accepted": 18,
                "median_patch_ops": 9,
            },
            schedule={
                "summary": {
                    "top_n": 5,
                    "total_candidates": 10,
                    "risk_priority": {
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
                    "risk_over_time": {
                        "mean_rank_top_n": 3.0,
                        "median_rank_top_n": 3.0,
                        "p95_rank_top_n": 5.0,
                    },
                },
                "telemetry": {
                    "risk_priority": {
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
        self.assertIn("10 / 10", section)
        self.assertIn("100.00%", section)
        self.assertIn("median patch ops 5", section)
        self.assertIn("18/20", section)
        self.assertIn("top 5 high-risk items", section)
        self.assertIn("5.5 patches/hour", section)

    def test_build_paper_paragraph(self) -> None:
        paragraph = updater.build_paper_paragraph(self.metrics)
        self.assertTrue(paragraph.startswith("\\noindent\\textbf{Full-run summary.}"))
        self.assertIn("10 accepted out of 10 patched items", paragraph)
        self.assertIn("100.00\\%", paragraph)
        self.assertIn("auto-fix rate 1.0000", paragraph)
        self.assertIn("median of 5 JSON Patch operations", paragraph)
        self.assertIn("1.5\\,h", paragraph)
        self.assertIn("+1.5\\,h", paragraph)

    def test_dry_run_does_not_write_scheduler_metrics(self) -> None:
        dashboards_path = Path("data/dashboard_metrics.json")
        dashboards_path.parent.mkdir(parents=True, exist_ok=True)
        original = {"sentinel": True}
        dashboards_path.write_text(json.dumps(original), encoding="utf-8")
        updater.run(dry_run=True)
        data = json.loads(dashboards_path.read_text())
        self.assertEqual(original, data)

    def test_update_readme_replaces_heading_when_markers_are_absent(self) -> None:
        path = Path("tmp/test-update-metrics-readme.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Demo\n\n## Metrics aligned to the paper (traceable in-repo)\nold\n\n## Related work\nkeep\n",
            encoding="utf-8",
        )
        updater.update_readme(path, "new metrics")
        text = path.read_text(encoding="utf-8")
        self.assertIn("new metrics", text)
        self.assertNotIn("\nold\n", text)
        self.assertIn("## Related work\nkeep", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
