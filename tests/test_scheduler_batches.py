import unittest

from src.scheduler.batches import schedule_batches


class SchedulerBatchTests(unittest.TestCase):
    def test_groups_by_policy_and_orders_by_score_then_key(self) -> None:
        records = [
            {"id": "z1", "score": 5.0, "R": 4.0, "policy_id": "z_policy"},
            {"id": "b1", "score": 10.0, "risk": 7.0, "policy_id": "beta"},
            {"id": "a1", "score": 10.0, "risk": 3.0, "policy_id": "alpha"},
            {"id": "a2", "score": 2.0, "risk": 1.0, "policy_id": "alpha"},
        ]

        batches = schedule_batches(records, group_by="policy")

        self.assertEqual(
            [batch.group_key for batch in batches],
            ["alpha", "beta", "z_policy"],
        )
        self.assertEqual(batches[0].id, "policy_id:alpha")
        self.assertEqual(batches[0].ids, ("a1", "a2"))
        self.assertEqual(batches[0].count, 2)
        self.assertEqual(batches[0].total_risk, 4.0)
        self.assertEqual(batches[0].max_score, 10.0)
        self.assertEqual(batches[0].policies, ("alpha",))

    def test_groups_by_namespace(self) -> None:
        records = [
            {"id": "dev-fix", "score": 3.0, "risk": 2.0, "namespace": "dev"},
            {"id": "prod-fix", "score": 9.0, "risk": 8.0, "namespace": "prod"},
        ]

        summaries = [
            batch.to_dict()
            for batch in schedule_batches(records, group_by="namespace")
        ]

        self.assertEqual([summary["group_key"] for summary in summaries], ["prod", "dev"])
        self.assertEqual(summaries[0]["ids"], ["prod-fix"])
        self.assertEqual(summaries[0]["namespaces"], ["prod"])

    def test_owner_grouping_uses_team_fallback(self) -> None:
        records = [
            {"id": "owned", "score": 5.0, "risk": 1.0, "owner": "security"},
            {"id": "teamed", "score": 9.0, "risk": 1.0, "team": "platform"},
        ]

        batches = schedule_batches(records, group_by="owner")
        alias_batches = schedule_batches(records, group_by="team/owner")
        team_batches = schedule_batches([records[0]], group_by="team")

        self.assertEqual(
            [batch.group_key for batch in batches],
            ["platform", "security"],
        )
        self.assertEqual(
            [batch.group_key for batch in alias_batches],
            ["platform", "security"],
        )
        self.assertEqual(batches[0].owners, ("platform",))
        self.assertEqual(team_batches[0].group_key, "security")

    def test_merges_metadata_by_id_from_detection_records(self) -> None:
        records = [{"id": "det-1", "score": 8.0, "risk": 12.0, "namespace": ""}]
        detections = [
            {
                "id": "det-1",
                "policy_id": "no_privileged",
                "namespace": "prod",
                "team": "platform",
                "root_cause": "security_context",
            }
        ]

        batches = schedule_batches(records, group_by="namespace", metadata=detections)

        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].group_key, "prod")
        self.assertEqual(batches[0].policies, ("no_privileged",))
        self.assertEqual(batches[0].owners, ("platform",))
        self.assertEqual(batches[0].root_causes, ("security_context",))

    def test_groups_by_root_cause_aliases(self) -> None:
        records = [
            {"id": "host-path", "score": 4.0, "risk": 5.0, "root_cause": "volume"},
            {"id": "host-port", "score": 6.0, "risk": 7.0, "cause": "volume"},
        ]

        batches = schedule_batches(records, group_by="root-cause")

        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0].group_by, "root_cause")
        self.assertEqual(batches[0].group_key, "volume")
        self.assertEqual(batches[0].ids, ("host-port", "host-path"))

    def test_candidate_ordering_is_deterministic_inside_batch(self) -> None:
        records = [
            {"id": "b", "score": 5.0, "risk": 1.0, "policy_id": "same"},
            {"id": "a", "score": 5.0, "risk": 1.0, "policy_id": "same"},
            {"id": "c", "score": 6.0, "risk": 1.0, "policy_id": "same"},
        ]

        batches = schedule_batches(records, group_by="policy_id")

        self.assertEqual(batches[0].ids, ("c", "a", "b"))

    def test_max_batch_size_splits_groups(self) -> None:
        records = [
            {"id": "a", "score": 10.0, "risk": 1.0, "namespace": "prod"},
            {"id": "b", "score": 9.0, "risk": 2.0, "namespace": "prod"},
            {"id": "c", "score": 8.0, "risk": 3.0, "namespace": "prod"},
        ]

        batches = schedule_batches(records, group_by="namespace", max_batch_size=2)

        self.assertEqual(
            [batch.id for batch in batches],
            ["namespace:prod:1", "namespace:prod:2"],
        )
        self.assertEqual([batch.ids for batch in batches], [("a", "b"), ("c",)])
        self.assertEqual([batch.count for batch in batches], [2, 1])
        self.assertEqual([batch.total_risk for batch in batches], [3.0, 3.0])

    def test_empty_input_returns_no_batches(self) -> None:
        self.assertEqual(schedule_batches([], group_by="namespace"), [])

    def test_bad_group_by_raises_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "group_by"):
            schedule_batches([], group_by="service")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
