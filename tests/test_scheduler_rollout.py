import unittest

from src.scheduler.batches import BatchSummary
from src.scheduler.rollout import annotate_rollout_batches, filter_rollout_batches


class SchedulerRolloutTests(unittest.TestCase):
    def test_annotates_change_window_and_blast_radius_without_mutating_input(self) -> None:
        batch = {
            "id": "namespace:prod",
            "group_by": "namespace",
            "group_key": "prod",
            "ids": ["high", "low"],
            "count": 2,
            "total_risk": 9.5,
            "max_score": 7.0,
            "policies": ["no_privileged", "run_as_non_root"],
            "namespaces": ["prod"],
            "owners": ["platform"],
            "root_causes": ["security_context"],
        }

        annotated = annotate_rollout_batches(
            [batch],
            change_windows={
                "weekday": {"namespaces": ["dev"]},
                "weekend": {"namespaces": ["prod"], "owners": ["platform"]},
            },
            max_count=3,
            max_total_risk=10.0,
            max_namespaces=1,
            max_policies=3,
        )

        self.assertEqual(batch["ids"], ["high", "low"])
        self.assertNotIn("change_window", batch)
        self.assertEqual(annotated[0]["change_window"], "weekend")
        self.assertEqual(
            annotated[0]["blast_radius"],
            {
                "count": 2,
                "total_risk": 9.5,
                "namespace_count": 1,
                "policy_count": 2,
                "owner_count": 1,
            },
        )
        self.assertTrue(annotated[0]["rollout_allowed"])
        self.assertEqual(annotated[0]["rollout_reasons"], [])

    def test_filters_batches_that_exceed_blast_radius_limits(self) -> None:
        batches = [
            {
                "id": "namespace:prod",
                "group_by": "namespace",
                "group_key": "prod",
                "ids": ["a", "b", "c"],
                "count": 3,
                "total_risk": 12.0,
                "policies": ["p1", "p2"],
                "namespaces": ["prod"],
            },
            {
                "id": "namespace:dev",
                "group_by": "namespace",
                "group_key": "dev",
                "ids": ["d"],
                "count": 1,
                "total_risk": 2.0,
                "policies": ["p1"],
                "namespaces": ["dev"],
            },
        ]

        annotated = annotate_rollout_batches(
            batches,
            max_count=2,
            max_total_risk=10.0,
            max_policies=1,
        )
        allowed = filter_rollout_batches(
            batches,
            max_count=2,
            max_total_risk=10.0,
            max_policies=1,
        )

        self.assertFalse(annotated[0]["rollout_allowed"])
        self.assertEqual(
            annotated[0]["rollout_reasons"],
            ["count>2", "total_risk>10", "policies>1"],
        )
        self.assertEqual([batch["id"] for batch in allowed], ["namespace:dev"])

    def test_accepts_batch_summary_objects_and_uses_default_window(self) -> None:
        summary = BatchSummary(
            id="policy_id:no_latest_tag",
            group_by="policy_id",
            group_key="no_latest_tag",
            ids=("fix-1",),
            count=1,
            total_risk=4.0,
            max_score=5.0,
            policies=("no_latest_tag",),
            namespaces=("dev",),
            owners=("apps",),
            root_causes=("image_tag",),
        )

        annotated = annotate_rollout_batches(
            [summary],
            change_windows={"prod-only": {"namespaces": ["prod"]}},
            default_window="next-safe-window",
        )

        self.assertEqual(annotated[0]["change_window"], "next-safe-window")
        self.assertEqual(annotated[0]["ids"], ["fix-1"])
        self.assertEqual(annotated[0]["max_score"], 5.0)

    def test_change_window_selection_is_deterministic_by_window_name(self) -> None:
        batch = {
            "id": "owner:platform",
            "group_by": "owner",
            "group_key": "platform",
            "ids": ["fix"],
            "count": 1,
            "policies": ["p1"],
            "namespaces": ["prod"],
            "owners": ["platform"],
        }

        annotated = annotate_rollout_batches(
            [batch],
            change_windows={
                "z-late": {"namespaces": ["prod"]},
                "a-early": {"owners": ["platform"]},
            },
        )

        self.assertEqual(annotated[0]["change_window"], "a-early")

    def test_rejects_non_positive_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_count"):
            annotate_rollout_batches([], max_count=0)
        with self.assertRaisesRegex(ValueError, "max_total_risk"):
            annotate_rollout_batches([], max_total_risk=-1.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
