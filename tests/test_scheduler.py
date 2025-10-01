import unittest

from src.scheduler.schedule import PatchCandidate, schedule_patches


class SchedulerTests(unittest.TestCase):
    def test_candidates_sorted_by_priority_score(self) -> None:
        patches = [
            PatchCandidate(
                id="001",
                risk=80,
                probability=0.9,
                expected_time=5,
                wait=0.2,
                kev=True,
                explore=0.0,
            ),
            PatchCandidate(
                id="002",
                risk=40,
                probability=0.8,
                expected_time=8,
                wait=0.1,
                kev=False,
                explore=0.0,
            ),
        ]
        ordered = schedule_patches(patches, alpha=0.5)
        self.assertEqual(ordered[0], patches[0])
        self.assertGreater(
            ordered[0].score(alpha=0.5), ordered[1].score(alpha=0.5)
        )

    def test_dict_inputs_are_normalised(self) -> None:
        ordered = schedule_patches(
            [
                {
                    "id": "003",
                    "risk": 60,
                    "probability": 0.7,
                    "expected_time": 4,
                    "wait": 0.5,
                    "kev": True,
                },
                {
                    "id": "004",
                    "risk": 30,
                    "probability": 0.5,
                    "expected_time": 3,
                },
            ]
        )
        self.assertEqual(len(ordered), 2)
        self.assertGreaterEqual(ordered[0].risk, ordered[1].risk)

    def test_missing_required_field_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            schedule_patches([
                {
                    "id": "005",
                    "risk": 0.5,
                    "probability": 0.4,
                    # expected_time omitted intentionally
                }
            ])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
