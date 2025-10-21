import json
import tempfile
import unittest
from pathlib import Path

from src.verifier import cli as verifier_cli

PRIVILEGED_MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  name: privileged
spec:
  containers:
    - name: demo
      image: nginx:1.23
      securityContext:
        privileged: true
"""

LATEST_MANIFEST = """\
apiVersion: v1
kind: Pod
metadata:
  name: latest
spec:
  containers:
    - name: web
      image: nginx:latest
"""


class VerifierCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        base = Path(self.tmpdir.name)

        detections = [
            {
                "id": "001",
                "manifest_yaml": PRIVILEGED_MANIFEST,
                "policy_id": "no_privileged",
                "violation_text": "privileged container",
            },
            {
                "id": "002",
                "manifest_yaml": LATEST_MANIFEST,
                "policy_id": "no_latest_tag",
                "violation_text": "image uses :latest",
            },
        ]
        patches = [
            {
                "id": "001",
                "policy_id": "no_privileged",
                "patch": [
                    {
                        "op": "replace",
                        "path": "/spec/containers/0/securityContext/privileged",
                        "value": False,
                    }
                ],
            },
            {
                "id": "002",
                "policy_id": "no_latest_tag",
                "patch": [
                    {
                        "op": "replace",
                        "path": "/spec/containers/0/image",
                        "value": "nginx:stable",
                    }
                ],
            },
        ]

        self.detections_path = base / "detections.json"
        self.detections_path.write_text(json.dumps(detections, indent=2), encoding="utf-8")
        self.patches_path = base / "patches.json"
        self.patches_path.write_text(json.dumps(patches, indent=2), encoding="utf-8")
        self.output_path = base / "verified.json"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _invoke_verify(self, **kwargs) -> None:
        verifier_cli.verify(
            patches=self.patches_path,
            out=self.output_path,
            detections=self.detections_path,
            kubectl_cmd="kubectl",
            require_kubectl=False,
            enable_rescan=False,
            kube_linter_cmd="kube-linter",
            kyverno_cmd="kyverno",
            policies_dir=None,
            include_errors=True,
            ids=kwargs.get("ids"),
            limit=kwargs.get("limit"),
            jobs=1,
            gate_profile=kwargs.get("gate_profile", "full"),
            disable_gate=kwargs.get("disable_gate"),
        )

    def test_verify_filters_by_ids(self) -> None:
        self._invoke_verify(ids=["002"])
        results = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "002")

    def test_verify_respects_limit(self) -> None:
        self._invoke_verify(limit=1)
        results = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "001")

    def test_gate_profile_can_disable_policy_gate(self) -> None:
        patches = json.loads(self.patches_path.read_text(encoding="utf-8"))
        # Leave the :latest tag unfixed so the policy gate would normally fail.
        for patch in patches:
            if patch["id"] == "002":
                patch["patch"][0]["value"] = "nginx:latest"
        self.patches_path.write_text(json.dumps(patches, indent=2), encoding="utf-8")

        # Baseline should fail the policy check.
        self._invoke_verify()
        baseline_results = {entry["id"]: entry for entry in json.loads(self.output_path.read_text(encoding="utf-8"))}
        self.assertFalse(baseline_results["002"]["accepted"])
        self.assertFalse(baseline_results["002"]["ok_policy"])

        # Disable the policy gate; patch should be accepted despite remaining :latest.
        self._invoke_verify(gate_profile="no-policy")
        gated_results = {entry["id"]: entry for entry in json.loads(self.output_path.read_text(encoding="utf-8"))}
        self.assertTrue(gated_results["002"]["accepted"])
        self.assertTrue(gated_results["002"]["ok_policy"])
