import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import jsonpatch
import yaml

from src.proposer.cli import (
    _assert_no_semantic_regression,
    _generate_patch_record,
    _rule_based_patch,
    _write_proposer_metrics,
)
from src.proposer.guards import PatchError, extract_json_array
from src.proposer.patch_safety import minimize_redundant_patch_ops, sanitize_patch_paths
from src.proposer.retry import resolve_retry_budget
from src.verifier.jsonpatch_guard import validate_paths_exist


SAMPLE_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: demo
spec:
  containers:
    - name: app
      image: nginx:latest
"""

HARDENING_MANIFEST = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
spec:
  template:
    spec:
      containers:
        - name: app
          image: nginx:latest
"""


class AlwaysInvalidGenerator:
    source = "vendor"

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _detection, _rng):
        self.calls += 1
        return [{"op": "replace", "path": "/spec/containers/9/image", "value": "nginx:stable"}]


class ProposerGuardsTests(unittest.TestCase):
    def test_extract_json_array_plain(self) -> None:
        text = '[{"op":"replace","path":"/spec/containers/0/image","value":"nginx:stable"}]'
        ops = extract_json_array(text)
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0]["op"], "replace")

    def test_extract_json_array_from_fenced_block(self) -> None:
        text = """```json\n[{\"op\":\"add\",\"path\":\"/metadata/labels/env\",\"value\":\"prod\"}]\n```"""
        ops = extract_json_array(text)
        self.assertEqual(ops[0]["op"], "add")

    def test_extract_json_array_invalid_text_raises(self) -> None:
        with self.assertRaises(PatchError):
            extract_json_array("not a json patch")

    def test_validate_paths_exist_accepts_valid_patch(self) -> None:
        patch_ops = [{"op": "replace", "path": "/spec/containers/0/image", "value": "nginx:stable"}]
        validate_paths_exist(SAMPLE_MANIFEST, patch_ops)

    def test_validate_paths_exist_rejects_invalid_patch(self) -> None:
        patch_ops = [{"op": "replace", "path": "/spec/containers/1/image", "value": "nginx:stable"}]
        with self.assertRaises(PatchError):
            validate_paths_exist(SAMPLE_MANIFEST, patch_ops)

    def test_sanitize_patch_paths_escapes_label_and_annotation_keys(self) -> None:
        patch_ops = [
            {"op": "add", "path": "/metadata/labels/app.kubernetes.io/name", "value": "demo"},
            {
                "op": "copy",
                "from": "/metadata/annotations/checksum/config",
                "path": "/metadata/annotations/config",
            },
        ]

        sanitized = sanitize_patch_paths(patch_ops)

        self.assertEqual(sanitized[0]["path"], "/metadata/labels/app.kubernetes.io~1name")
        self.assertEqual(sanitized[1]["from"], "/metadata/annotations/checksum~1config")
        self.assertEqual(sanitized[1]["path"], "/metadata/annotations/config")
        self.assertEqual(patch_ops[0]["path"], "/metadata/labels/app.kubernetes.io/name")

    def test_sanitize_patch_paths_decodes_url_encoded_keys(self) -> None:
        patch_ops = [
            {
                "op": "add",
                "path": "/spec/template/metadata/labels/app.kubernetes.io%2Fcomponent",
                "value": "api",
            }
        ]

        sanitized = sanitize_patch_paths(patch_ops)

        self.assertEqual(sanitized[0]["path"], "/spec/template/metadata/labels/app.kubernetes.io~1component")

    def test_sanitize_patch_paths_preserves_already_escaped_keys(self) -> None:
        patch_ops = [
            {"op": "add", "path": "/metadata/labels/app.kubernetes.io~1name", "value": "demo"},
            {"op": "add", "path": "/metadata/annotations/checksum~0config", "value": "abc"},
        ]

        sanitized_once = sanitize_patch_paths(patch_ops)
        sanitized_twice = sanitize_patch_paths(sanitized_once)

        self.assertEqual(sanitized_once, sanitized_twice)
        self.assertEqual(sanitized_once[0]["path"], "/metadata/labels/app.kubernetes.io~1name")
        self.assertEqual(sanitized_once[1]["path"], "/metadata/annotations/checksum~0config")

    def test_sanitize_patch_paths_keeps_selector_matchlabels_structural(self) -> None:
        patch_ops = [
            {"op": "add", "path": "/spec/selector/matchLabels/app.kubernetes.io/name", "value": "api"},
            {"op": "replace", "path": "/spec/selector/matchExpressions/0/values/0", "value": "api"},
        ]

        sanitized = sanitize_patch_paths(patch_ops)

        self.assertEqual(sanitized[0]["path"], "/spec/selector/matchLabels/app.kubernetes.io~1name")
        self.assertEqual(sanitized[1]["path"], "/spec/selector/matchExpressions/0/values/0")

    def test_sanitize_patch_paths_treats_service_selector_as_flat_label_map(self) -> None:
        patch_ops = [
            {"op": "add", "path": "/spec/selector/app.kubernetes.io/name", "value": "api"},
            {"op": "add", "path": "/spec/selector/matchLabels/team", "value": "platform"},
        ]

        sanitized = sanitize_patch_paths(patch_ops, {"kind": "Service"})

        self.assertEqual(sanitized[0]["path"], "/spec/selector/app.kubernetes.io~1name")
        self.assertEqual(sanitized[1]["path"], "/spec/selector/matchLabels~1team")

    def test_semantic_regression_allows_container_and_volume_descendant_removals(self) -> None:
        _assert_no_semantic_regression(
            [
                {"op": "remove", "path": "/spec/containers/0/securityContext/capabilities/add/0"},
                {"op": "remove", "path": "/spec/volumes/0/hostPath"},
            ]
        )

    def test_semantic_regression_rejects_whole_container_and_volume_removals(self) -> None:
        with self.assertRaises(PatchError):
            _assert_no_semantic_regression([{"op": "remove", "path": "/spec/containers/0"}])
        with self.assertRaises(PatchError):
            _assert_no_semantic_regression([{"op": "remove", "path": "/spec/volumes"}])

    def test_minimize_redundant_patch_ops_removes_noop_descendants(self) -> None:
        document = {"spec": {"containers": [{"name": "app"}]}}
        patch_ops = [
            {
                "op": "add",
                "path": "/spec/containers/0/securityContext",
                "value": {"privileged": False, "runAsNonRoot": True},
            },
            {"op": "add", "path": "/spec/containers/0/securityContext/privileged", "value": False},
            {"op": "add", "path": "/spec/containers/0/securityContext/runAsNonRoot", "value": True},
        ]

        minimized = minimize_redundant_patch_ops(document, patch_ops)

        self.assertEqual(minimized, patch_ops[:1])

    def test_minimize_redundant_patch_ops_coalesces_parent_updates(self) -> None:
        document = {"spec": {"containers": [{"name": "app", "securityContext": {"capabilities": {"add": ["NET_RAW"]}}}]}}
        patch_ops = [
            {"op": "add", "path": "/spec/containers/0/securityContext/capabilities/drop", "value": ["ALL"]},
            {"op": "replace", "path": "/spec/containers/0/securityContext/capabilities/add", "value": []},
            {"op": "add", "path": "/spec/containers/0/securityContext/privileged", "value": False},
            {"op": "add", "path": "/spec/containers/0/securityContext/runAsNonRoot", "value": True},
        ]

        minimized = minimize_redundant_patch_ops(document, patch_ops)

        self.assertEqual(len(minimized), 1)
        self.assertEqual(minimized[0]["op"], "replace")
        self.assertEqual(minimized[0]["path"], "/spec/containers/0/securityContext")
        self.assertEqual(
            jsonpatch.apply_patch(document, minimized, in_place=False),
            jsonpatch.apply_patch(document, patch_ops, in_place=False),
        )

    def test_minimize_redundant_patch_ops_keeps_invalid_patch_instead_of_crashing(self) -> None:
        document = {}
        patch_ops = [{"op": "add", "path": "/spec/containers/0/securityContext", "value": {"runAsNonRoot": True}}]

        self.assertEqual(minimize_redundant_patch_ops(document, patch_ops), patch_ops)

    def test_rule_based_patch_dispatches_known_policy(self) -> None:
        detection = {
            "id": "latest-001",
            "policy_id": "no_latest_tag",
            "violation_text": "container uses latest tag",
            "manifest_yaml": SAMPLE_MANIFEST,
        }

        ops = _rule_based_patch(detection)
        patched = jsonpatch.apply_patch(yaml.safe_load(SAMPLE_MANIFEST), ops, in_place=False)

        self.assertEqual(patched["spec"]["containers"][0]["image"], "nginx:stable")

    def test_rule_based_patch_unknown_policy_raises(self) -> None:
        detection = {
            "id": "unknown-001",
            "policy_id": "unknown_policy",
            "violation_text": "unsupported policy",
            "manifest_yaml": SAMPLE_MANIFEST,
        }

        with self.assertRaisesRegex(PatchError, "no rule available for policy unknown_policy"):
            _rule_based_patch(detection)

    def test_rule_based_patch_includes_guardrails(self) -> None:
        detection = {
            "id": "guard-001",
            "policy_id": "no_privileged",
            "violation_text": "container is privileged",
            "manifest_yaml": HARDENING_MANIFEST,
        }
        ops = _rule_based_patch(detection)
        patched = jsonpatch.apply_patch(yaml.safe_load(HARDENING_MANIFEST), ops, in_place=False)
        container = patched["spec"]["template"]["spec"]["containers"][0]
        security = container["securityContext"]
        resources = container["resources"]
        paths = {op["path"] for op in ops if isinstance(op, dict)}
        self.assertTrue(any("resources" in path for path in paths), "expected resources guard op")
        self.assertIs(security["runAsNonRoot"], True)
        self.assertIs(security["readOnlyRootFilesystem"], True)
        self.assertIs(security["privileged"], False)
        self.assertIn("requests", resources)
        self.assertIn("limits", resources)


class ProposerRetryBudgetTests(unittest.TestCase):
    def test_resolve_retry_budget_preserves_fallback_without_config(self) -> None:
        self.assertEqual(resolve_retry_budget({}, "no_latest_tag", 3), 3)

    def test_resolve_retry_budget_prefers_policy_over_default(self) -> None:
        config = {"retry_budgets": {"default": 2, "no_latest_tag": 4}}

        self.assertEqual(resolve_retry_budget(config, "no_latest_tag", 3), 4)

    def test_resolve_retry_budget_uses_nested_default(self) -> None:
        config = {"proposer": {"retry_budgets": {"default": "2"}}}

        self.assertEqual(resolve_retry_budget(config, "no_latest_tag", 3), 2)

    def test_resolve_retry_budget_nested_overrides_top_level(self) -> None:
        config = {
            "retry_budgets": {"default": 2, "no_latest_tag": 3},
            "proposer": {"retry_budgets": {"no_latest_tag": 4}},
        }

        self.assertEqual(resolve_retry_budget(config, "no_latest_tag", 3), 4)

    def test_generate_patch_record_preserves_max_attempts_without_retry_budget(self) -> None:
        generator = AlwaysInvalidGenerator()

        result = _generate_patch_record(
            _retry_detection(),
            config_data={},
            base_dir=Path("."),
            generator=generator,
            max_attempts=3,
        )

        self.assertEqual(generator.calls, 3)
        self.assertEqual(result["attempt_count"], 3)
        self.assertEqual(result["retry_budget"], 3)
        self.assertEqual(len(result["attempt_errors"]), 3)

    def test_generate_patch_record_uses_policy_retry_budget(self) -> None:
        generator = AlwaysInvalidGenerator()

        result = _generate_patch_record(
            _retry_detection(),
            config_data={"retry_budgets": {"default": 5, "no_latest_tag": 2}},
            base_dir=Path("."),
            generator=generator,
            max_attempts=5,
        )

        self.assertEqual(generator.calls, 2)
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["retry_budget"], 2)
        self.assertEqual(len(result["attempt_errors"]), 2)

    def test_generate_patch_record_uses_proposer_retry_budget_default(self) -> None:
        generator = AlwaysInvalidGenerator()

        result = _generate_patch_record(
            _retry_detection(),
            config_data={"proposer": {"retry_budgets": {"default": 2}}},
            base_dir=Path("."),
            generator=generator,
            max_attempts=5,
        )

        self.assertEqual(generator.calls, 2)
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["retry_budget"], 2)
        self.assertEqual(len(result["attempt_errors"]), 2)

    def test_write_proposer_metrics_aggregates_attempts_and_retry_budget(self) -> None:
        patches = [
            {
                "id": "retry-001",
                "policy_id": "no_latest_tag",
                "source": "vendor",
                "total_latency_ms": 10,
                "attempt_count": 3,
                "retry_budget": 3,
            },
            {
                "id": "retry-002",
                "policy_id": "no_privileged",
                "source": "rules",
                "total_latency_ms": 5,
                "attempt_count": 1,
                "retry_budget": 2,
            },
        ]

        with TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "metrics.json"
            _write_proposer_metrics(metrics_path, patches)
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["records"][0]["attempt_count"], 3)
        self.assertEqual(payload["records"][0]["retry_budget"], 3)
        self.assertEqual(payload["records"][1]["attempt_count"], 1)
        self.assertEqual(payload["records"][1]["retry_budget"], 2)
        self.assertEqual(payload["summary"]["attempts"], {"total": 4, "retries": 2, "max": 3})
        self.assertEqual(payload["summary"]["retry_budget"], {"total": 5, "max": 3})

    def test_write_proposer_metrics_accounts_for_reasoning_tokens(self) -> None:
        patches = [
            {
                "id": "tokens-001",
                "policy_id": "no_latest_tag",
                "source": "vendor",
                "model_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "completion_tokens_details": {"reasoning_tokens": 7},
                    "total_tokens": 20,
                },
            }
        ]

        with TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "metrics.json"
            _write_proposer_metrics(metrics_path, patches)
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["records"][0]["reasoning_tokens"], 7.0)
        self.assertEqual(
            payload["summary"]["tokens"],
            {
                "usage_records": 1,
                "prompt": 10.0,
                "completion": 3.0,
                "reasoning": 7.0,
                "unattributed": 0,
                "total": 20.0,
            },
        )


def _retry_detection():
    return {
        "id": "retry-001",
        "policy_id": "no_latest_tag",
        "violation_text": "container uses latest tag",
        "manifest_yaml": SAMPLE_MANIFEST,
    }


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
