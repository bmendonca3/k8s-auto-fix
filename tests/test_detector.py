import json
import tempfile
import unittest
from pathlib import Path

from src.detector.detector import Detector, DetectionResult
import yaml


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
        manifest_obj = yaml.safe_load(self.manifest_path.read_text())
        self.assertTrue(
            any(yaml.safe_load(entry["manifest_yaml"]) == manifest_obj for entry in data)
        )
        self.assertIn("no-privileged", {entry["policy_id"] for entry in data})

    def test_detect_supports_parallel_jobs(self) -> None:
        other_manifest = Path(self.tmpdir.name) / "second.yaml"
        other_manifest.write_text(self.manifest_path.read_text())
        results = self.detector.detect([self.manifest_path, other_manifest], jobs=2)
        kube_calls = [cmd for cmd in self.commands if cmd[0] == "kube-linter"]
        kyverno_calls = [cmd for cmd in self.commands if cmd[0] == "kyverno"]
        self.assertEqual(len(kube_calls), 2)
        self.assertEqual(len(kyverno_calls), 2)
        self.assertEqual(len([r for r in results if r.tool == "kube-linter"]), 2)
        self.assertEqual(len([r for r in results if r.tool == "kyverno"]), 2)

    def test_builtin_detections_cover_hostpath_and_hostports(self) -> None:
        manifest = Path(self.tmpdir.name) / "host_access.yaml"
        manifest.write_text(
            """
apiVersion: v1
kind: Pod
metadata:
  name: host-access
spec:
  containers:
    - name: api
      image: nginx:1.25
      ports:
        - containerPort: 8080
          hostPort: 30080
  volumes:
    - name: data
      hostPath:
        path: /var/lib/data
""".strip()
        )
        results = self.detector.detect([manifest], jobs=1)
        rules = {result.rule for result in results if result.tool == "builtin"}
        self.assertIn("host-ports", rules)
        self.assertIn("hostpath-volume", rules)

    def test_targeted_manifest_selects_matching_document(self) -> None:
        multi_path = Path(self.tmpdir.name) / "multi.yaml"
        multi_path.write_text(
            """
apiVersion: v1
kind: ConfigMap
metadata:
  name: shared-config
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-deploy
  namespace: default
spec:
  template:
    spec:
      containers:
        - name: app
          image: nginx:latest
""".strip()
        )
        detection = DetectionResult(
            tool="kube-linter",
            manifest=str(multi_path),
            rule="no_latest_tag",
            message="uses :latest",
            resource="Deployment/default/demo-deploy",
            extra=None,
        )
        manifest_yaml = self.detector._load_targeted_manifest(multi_path, detection)
        manifest_obj = yaml.safe_load(manifest_yaml)
        self.assertEqual(manifest_obj.get("kind"), "Deployment")
        self.assertEqual(manifest_obj.get("metadata", {}).get("name"), "demo-deploy")
        self.assertNotIn("shared-config", manifest_yaml)

    def test_targeted_manifest_falls_back_to_first_mapping(self) -> None:
        multi_path = Path(self.tmpdir.name) / "multi_no_match.yaml"
        multi_path.write_text(
            """
kind: ConfigMap
metadata:
  name: shared-config
---
kind: Service
metadata:
  name: svc
""".strip()
        )
        detection = DetectionResult(
            tool="kube-linter",
            manifest=str(multi_path),
            rule="no_latest_tag",
            message="uses :latest",
            resource=None,
            extra=None,
        )
        manifest_yaml = self.detector._load_targeted_manifest(multi_path, detection)
        manifest_obj = yaml.safe_load(manifest_yaml)
        self.assertEqual(manifest_obj.get("kind"), "ConfigMap")
        self.assertEqual(manifest_obj.get("metadata", {}).get("name"), "shared-config")

    def test_manifest_pruning_reduces_context(self) -> None:
        large_path = Path(self.tmpdir.name) / "large.yaml"
        large_path.write_text(
            """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-deploy
  namespace: prod
  labels:
    app: demo
  annotations:
    trace: enabled
  extra_meta: should_not_appear
spec:
  replicas: 3
  selector:
    matchLabels:
      app: demo
  strategy:
    type: Recreate
  template:
    metadata:
      labels:
        app: demo
      annotations:
        trace: enabled
      nested_extra: nope
    spec:
      containers:
        - name: app
          image: nginx:latest
          imagePullPolicy: Always
          env:
            - name: PASSWORD
              value: s3cr3t
          envFrom:
            - secretRef:
                name: existing-secret
          resources:
            limits:
              cpu: "0"
            requests:
              cpu: "0"
          securityContext:
            privileged: true
          extra_field: remove_me
      terminationGracePeriodSeconds: 30
""".strip()
        )

        detection = DetectionResult(
            tool="kube-linter",
            manifest=str(large_path),
            rule="unset-cpu-requirements",
            message="missing cpu requests",
            resource=None,
            extra=None,
        )
        manifest_yaml = self.detector._load_targeted_manifest(large_path, detection)
        pruned = yaml.safe_load(manifest_yaml)

        self.assertEqual(pruned["kind"], "Deployment")
        self.assertNotIn("extra_meta", pruned.get("metadata", {}))
        spec = pruned.get("spec", {})
        self.assertIn("replicas", spec)
        self.assertNotIn("strategy", spec)

        template_meta = spec.get("template", {}).get("metadata", {})
        self.assertNotIn("nested_extra", template_meta)
        container = spec.get("template", {}).get("spec", {}).get("containers", [])[0]
        self.assertNotIn("extra_field", container)
        self.assertIn("resources", container)
        self.assertIn("envFrom", container)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
