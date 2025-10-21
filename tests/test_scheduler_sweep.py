import unittest

from scripts import scheduler_sweep


class SchedulerSweepUtilsTests(unittest.TestCase):
    def test_gini_two_values(self) -> None:
        self.assertAlmostEqual(scheduler_sweep._gini([0.0, 1.0]), 0.5, places=6)
        self.assertAlmostEqual(scheduler_sweep._gini([1.0, 1.0, 1.0]), 0.0, places=6)

    def test_head_of_line_share(self) -> None:
        ordered_ids = ["a", "b", "c", "d"]
        percentile_map = {"a": 0.1, "b": 0.2, "c": 0.8, "d": 0.9}
        boundaries = [0.25, 0.75]
        band_labels = scheduler_sweep._format_band_names(len(boundaries) + 1)
        share = scheduler_sweep._head_of_line_share(
            ordered_ids,
            percentile_map,
            boundaries,
            band_labels,
            head_fraction=0.5,
        )
        self.assertEqual(share, 0.0)

    def test_evaluate_order_metrics(self) -> None:
        ordered_ids = ["a", "b", "c", "d"]
        metadata = {
            "a": {"expected_time": 60.0},
            "b": {"expected_time": 120.0},
            "c": {"expected_time": 30.0},
            "d": {"expected_time": 30.0},
        }
        percentile_map = {"a": 0.1, "b": 0.6, "c": 0.85, "d": 0.9}
        boundaries = [0.25, 0.75]
        band_labels = scheduler_sweep._format_band_names(len(boundaries) + 1)

        result = scheduler_sweep._evaluate_order(
            mode="test",
            ordered_ids=ordered_ids,
            metadata=metadata,
            percentile_map=percentile_map,
            boundaries=boundaries,
            band_labels=band_labels,
            starvation_threshold=2.0,
            head_fraction=0.5,
        )

        waits = result["overall_wait_hours"]
        self.assertAlmostEqual(waits["median"], 2.0, places=4)
        self.assertAlmostEqual(waits["starvation_rate"], 0.5, places=4)
        self.assertIn("gini", waits)
        self.assertEqual(result["mode"], "test")


if __name__ == "__main__":
    unittest.main()
