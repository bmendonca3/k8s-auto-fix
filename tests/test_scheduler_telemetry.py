import unittest

from scripts import compare_schedulers


class SchedulerTelemetryTests(unittest.TestCase):
    def test_compute_telemetry_calculates_waits_and_rates(self) -> None:
        metadata = {
            "a": {"risk": 80.0, "probability": 0.9, "expected_time": 15.0},
            "b": {"risk": 40.0, "probability": 0.8, "expected_time": 30.0},
            "c": {"risk": 60.0, "probability": 1.0, "expected_time": 45.0},
        }
        order = ["a", "b", "c"]
        telemetry = compare_schedulers._compute_telemetry(order, metadata)

        self.assertEqual(telemetry["items"], 3)
        # Total runtime should be 90 minutes -> 1.5 hours
        self.assertAlmostEqual(telemetry["total_runtime_hours"], 1.5, places=4)
        waits = telemetry["wait_hours"]
        self.assertGreater(waits["median"], 0.0)
        self.assertGreaterEqual(telemetry["throughput_per_hour"], 2.0)
        self.assertGreater(telemetry["risk_reduction_per_hour"], 0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
