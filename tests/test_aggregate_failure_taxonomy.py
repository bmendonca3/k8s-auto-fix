import unittest

from scripts.aggregate_failure_taxonomy import aggregate_failures


class FailureTaxonomyTests(unittest.TestCase):
    def test_counts_unique_records_and_raw_error_events_separately(self) -> None:
        records = [
            {
                "id": "a",
                "accepted": False,
                "policy_id": "drop_capabilities",
                "errors": ["capabilities not defined", "capabilities not defined"],
            },
            {
                "id": "b",
                "accepted": False,
                "policy_id": "drop_capabilities",
                "errors": ["capabilities not defined"],
            },
            {"id": "c", "accepted": True, "policy_id": "drop_capabilities"},
        ]

        total, accepted, record_counts, event_counts, policy_counts = aggregate_failures(records)

        self.assertEqual((total, accepted), (3, 1))
        self.assertEqual(record_counts["capabilities not defined"], 2)
        self.assertEqual(event_counts["capabilities not defined"], 3)
        self.assertEqual(policy_counts["drop_capabilities"], 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
