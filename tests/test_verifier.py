import types
import unittest

import yaml

from src.verifier.verifier import Verifier
from src.proposer import cli as proposer_cli

PRIVILEGED_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: privileged
spec:
  containers:
    - name: ubuntu
      image: ubuntu:22.04
      securityContext:
        privileged: true
"""

LATEST_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: latest
spec:
  containers:
    - name: nginx
      image: nginx:latest
"""


class VerifierTests(unittest.TestCase):
    def _stub_kubectl(self, verifier: Verifier, value: bool) -> None:
        verifier._kubectl_dry_run = types.MethodType(lambda _self, _yaml: value, verifier)

    def test_verify_successful_patch(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, True)
        patch = [{"op": "replace", "path": "/spec/containers/0/image", "value": "nginx:stable"}]
        result = verifier.verify(LATEST_MANIFEST, patch, "no_latest_tag")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_schema)
        self.assertTrue(result.ok_policy)
        self.assertIsNotNone(result.patched_yaml)

    def test_verify_policy_failure(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, True)
        # Patch changes unrelated field, leaving privileged true
        patch = [{"op": "add", "path": "/metadata/labels/env", "value": "prod"}]
        result = verifier.verify(PRIVILEGED_MANIFEST, patch, "no_privileged")
        self.assertFalse(result.accepted)
        self.assertFalse(result.ok_policy)

    def test_verify_schema_failure(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, False)
        patch = [{"op": "replace", "path": "/spec/containers/0/image", "value": "ubuntu:stable"}]
        result = verifier.verify(PRIVILEGED_MANIFEST, patch, "no_privileged")
        self.assertFalse(result.ok_schema)
        self.assertFalse(result.accepted)

    def test_verify_invalid_patch(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, True)
        patch = [{"op": "replace", "path": "/spec/containers/1/image", "value": "nginx:stable"}]
        result = verifier.verify(LATEST_MANIFEST, patch, "no_latest_tag")
        self.assertFalse(result.accepted)
        self.assertIsNone(result.patched_yaml)

    def test_verify_host_path_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      hostPath:
        path: /var/lib/data
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_host_path(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_host_path")
        self.assertTrue(result.accepted)

    def test_verify_host_ports_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: hostport-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
      ports:
        - containerPort: 80
          hostPort: 30080
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_host_ports(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_host_ports")
        self.assertTrue(result.accepted)

    def test_verify_run_as_user_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: runasuser-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_run_as_user(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "run_as_user")
        self.assertTrue(result.accepted)

    def test_verify_enforce_seccomp_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: seccomp-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_enforce_seccomp(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "enforce_seccomp")
        self.assertTrue(result.accepted)

    def test_verify_drop_capabilities_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: caps-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
      securityContext:
        capabilities:
          add: ["NET_RAW", "CHOWN"]
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_drop_capabilities(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "drop_capabilities")
        self.assertTrue(result.accepted)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
