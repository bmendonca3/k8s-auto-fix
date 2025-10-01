import types
import unittest

from src.verifier.verifier import Verifier

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
