import unittest

from src.proposer.cli import _rule_based_patch
from src.proposer.guards import PatchError, extract_json_array
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

    def test_rule_based_patch_includes_guardrails(self) -> None:
        detection = {
            "id": "guard-001",
            "policy_id": "no_privileged",
            "violation_text": "container is privileged",
            "manifest_yaml": HARDENING_MANIFEST,
        }
        ops = _rule_based_patch(detection)
        paths = {op["path"] for op in ops if isinstance(op, dict)}
        self.assertTrue(any("resources" in path for path in paths), "expected resources guard op")
        self.assertTrue(any("runAsNonRoot" in path for path in paths), "expected runAsNonRoot guard op")
        self.assertTrue(
            any("readOnlyRootFilesystem" in path for path in paths),
            "expected readOnlyRootFilesystem guard op",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
