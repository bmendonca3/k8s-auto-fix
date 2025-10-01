import json
import tempfile
import unittest
from pathlib import Path

from src.detector.detector import Detector


class DetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.manifest_path = Path(self.tmpdir.name) / "manifest.yaml"
        self.manifest_path.write_text(
            """
apiVersion: v1
kind: Pod
metadata:
  name: demo
  namespace: default
spec:
  containers:
    - name: demo
      image: nginx
""".strip()
        )
        self.kube_output = json.dumps(
            {
                "Reports": [
                    {
                        "Check": "no-privileged",
                        "Severity": "error",
                        "Diagnostic": {
                            "Message": "Privileged container detected",
                            "Object": {
                                "Kind": "Pod",
                                "Name": "demo",
                                "Namespace": "default",
                            },
                        },
                    }
                ]
            }
        )
        self.kyverno_output = json.dumps(
            {
                "results": [
                    {
                        "policy": "require-limits",
                        "rule": "limits-required",
                        "message": "resources.limits is required",
                        "result": "fail",
                        "severity": "medium",
                        "resources": [
                            {
                                "kind": "Pod",
                                "name": "demo",
                                "namespace": "default",
                            }
                        ],
                    }
                ]
            }
        )
        self.detector = Detector(policies_dir=Path(self.tmpdir.name))
        self.commands = []

        def fake_command(command):
            self.commands.append(tuple(command))
            if command[0] == "kube-linter":
                return self.kube_output
            if command[0] == "kyverno":
                return self.kyverno_output
            raise AssertionError(f"Unexpected command: {command}")

        self.detector._run_command = fake_command  # type: ignore[method-assign]

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_detect_combines_kube_linter_and_kyverno_results(self) -> None:
        results = self.detector.detect([self.manifest_path])
        tools = {result.tool for result in results}
        self.assertEqual(tools, {"kube-linter", "kyverno"})
        kube_issue = next(result for result in results if result.tool == "kube-linter")
        self.assertIn("Privileged", kube_issue.message)
        self.assertEqual(kube_issue.resource, "Pod/default/demo")
        kyverno_issue = next(result for result in results if result.tool == "kyverno")
        self.assertIn("limits", kyverno_issue.message)
        self.assertEqual(kyverno_issue.rule, "limits-required")
        self.assertTrue(any(cmd[0] == "kube-linter" for cmd in self.commands))
        self.assertTrue(any(cmd[0] == "kyverno" for cmd in self.commands))

    def test_write_results_creates_json_file(self) -> None:
        results = self.detector.detect([self.manifest_path])
        output_path = Path(self.tmpdir.name) / "detections.json"
        self.detector.write_results(results, output_path)
        data = json.loads(output_path.read_text())
        self.assertEqual(len(data), 2)
        required_fields = {"id", "manifest_path", "manifest_yaml", "policy_id", "violation_text"}
        for entry in data:
            self.assertTrue(required_fields.issubset(entry.keys()))
        manifest_contents = self.manifest_path.read_text()
        self.assertTrue(any(entry["manifest_yaml"] == manifest_contents for entry in data))
        self.assertIn("no-privileged", {entry["policy_id"] for entry in data})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
