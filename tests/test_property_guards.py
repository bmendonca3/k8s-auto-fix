import copy
import jsonpatch
import random
import string
import unittest
from typing import Dict, List

from src.proposer import cli as proposer_cli
from src.proposer.guards import PatchError


SAFE_CAPABILITIES = ["SYSLOG", "CHOWN", "FOWNER", "SETUID", "SETGID"]


def _base_manifest(containers: List[Dict]) -> Dict:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "prop-test", "namespace": "default"},
        "spec": {"containers": containers},
    }


def _random_name(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase, k=random.randint(1, 4)))
    return f"{prefix}{suffix}"


def build_capability_manifest() -> Dict:
    dangerous = list(proposer_cli.DANGEROUS_CAPABILITIES)
    num_containers = random.randint(1, 3)
    containers: List[Dict] = []

    for idx in range(num_containers):
        container: Dict = {"name": _random_name("cap"), "image": "alpine:3.19"}
        security_context: Dict = {}
        capabilities: Dict = {}

        # Ensure at least one container (first) omits a dangerous capability and "ALL".
        drop_subset = random.sample(dangerous, k=random.randint(0, max(len(dangerous) - 1, 1)))
        if idx == 0 and len(drop_subset) == len(dangerous):
            drop_subset = drop_subset[:-1]
        capabilities["drop"] = drop_subset

        add_candidates = dangerous + SAFE_CAPABILITIES
        add_size = random.randint(0, min(4, len(add_candidates)))
        capabilities["add"] = random.sample(add_candidates, k=add_size)

        security_context["capabilities"] = capabilities
        security_context["privileged"] = random.choice([True, False])
        security_context["allowPrivilegeEscalation"] = random.choice([True, False])

        container["securityContext"] = security_context
        containers.append(container)

    return _base_manifest(containers)


def build_run_as_non_root_manifest() -> Dict:
    num_containers = random.randint(1, 3)
    containers: List[Dict] = []

    for idx in range(num_containers):
        container: Dict = {"name": _random_name("ran"), "image": "busybox:1.36"}
        include_context = random.choice([True, False])
        security_context: Dict = {}

        if not include_context or idx == 0:
            # Force missing or incorrect values for the first container.
            if include_context:
                security_context["runAsNonRoot"] = random.choice([None, False])
            # else leave empty to ensure patch adds context.
        else:
            run_value = random.choice([None, False, True])
            if run_value is not None:
                security_context["runAsNonRoot"] = run_value

        if include_context and random.choice([True, False]):
            security_context["privileged"] = random.choice([True, False])

        if security_context:
            container["securityContext"] = security_context
        containers.append(container)

    return _base_manifest(containers)


def build_sys_admin_manifest() -> Dict:
    container: Dict = {"name": _random_name("sys"), "image": "alpine:3.19"}
    container["securityContext"] = {"capabilities": {"drop": random.sample(SAFE_CAPABILITIES, k=2)}}
    if random.choice([True, False]):
        container["securityContext"]["capabilities"]["add"] = ["SYS_ADMIN"]
    return _base_manifest([container])


def build_privilege_escalation_manifest() -> Dict:
    container: Dict = {"name": _random_name("ape"), "image": "busybox:1.36"}
    container["securityContext"] = {"allowPrivilegeEscalation": random.choice([None, True])}
    return _base_manifest([container])


def build_host_path_manifest() -> Dict:
    volume = {"name": _random_name("vol"), "hostPath": {"path": f"/tmp/{_random_name('hp')}"}}  # always hostPath
    manifest = _base_manifest([{"name": _random_name("hp"), "image": "busybox:1.36"}])
    manifest["spec"]["volumes"] = [volume]
    return manifest


def build_read_only_manifest() -> Dict:
    container: Dict = {"name": _random_name("ro"), "image": "alpine:3.19"}
    container["securityContext"] = {"readOnlyRootFilesystem": random.choice([None, False])}
    return _base_manifest([container])


def build_seccomp_manifest() -> Dict:
    container: Dict = {"name": _random_name("sec"), "image": "alpine:3.19"}
    container["securityContext"] = {"seccompProfile": {"type": random.choice(["", "Localhost"])}}
    return _base_manifest([container])


class GuardPropertyTests(unittest.TestCase):
    def setUp(self) -> None:
        random.seed(1337)

    def test_drop_capabilities_patch_enforces_hardening(self) -> None:
        for _ in range(80):
            manifest = build_capability_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_drop_capabilities(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)

            containers = patched.get("spec", {}).get("containers", [])
            self.assertTrue(containers)

            for container in containers:
                security = container.get("securityContext")
                self.assertIsInstance(security, dict)
                caps = security.get("capabilities")
                self.assertIsInstance(caps, dict)
                drop_list = caps.get("drop")
                self.assertIsInstance(drop_list, list)
                drop_upper = {str(item).upper() for item in drop_list}

                self.assertIn("ALL", drop_upper)
                for cap in proposer_cli.DANGEROUS_CAPABILITIES:
                    self.assertIn(cap, drop_upper)

                add_list = caps.get("add")
                if isinstance(add_list, list):
                    for cap in add_list:
                        self.assertNotIn(str(cap).upper(), proposer_cli.DANGEROUS_CAPABILITIES)

                self.assertFalse(security.get("privileged", False))
                self.assertFalse(security.get("allowPrivilegeEscalation", False))

            with self.assertRaises(PatchError):
                proposer_cli._patch_drop_capabilities(patched)

    def test_run_as_non_root_patch_enforces_non_root(self) -> None:
        for _ in range(80):
            manifest = build_run_as_non_root_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_run_as_non_root(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)

            containers = patched.get("spec", {}).get("containers", [])
            self.assertTrue(containers)

            for container in containers:
                security = container.get("securityContext")
                self.assertIsInstance(security, dict)
                self.assertTrue(security.get("runAsNonRoot"))
                self.assertFalse(security.get("privileged", False))

            with self.assertRaises(PatchError):
                proposer_cli._patch_run_as_non_root(patched)

    def test_drop_cap_sys_admin_patch_enforces_guard(self) -> None:
        for _ in range(60):
            manifest = build_sys_admin_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_drop_cap_sys_admin(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)
            containers = patched.get("spec", {}).get("containers", [])
            self.assertTrue(containers)
            for container in containers:
                security = container.get("securityContext")
                self.assertIsInstance(security, dict)
                caps = security.get("capabilities")
                self.assertIsInstance(caps, dict)
                drop_list = caps.get("drop")
                self.assertIsInstance(drop_list, list)
                self.assertIn("SYS_ADMIN", {str(item).upper() for item in drop_list})
                add_list = caps.get("add")
                if isinstance(add_list, list):
                    self.assertNotIn("SYS_ADMIN", {str(item).upper() for item in add_list})
            with self.assertRaises(PatchError):
                proposer_cli._patch_drop_cap_sys_admin(patched)

    def test_no_allow_privilege_escalation_patch(self) -> None:
        for _ in range(60):
            manifest = build_privilege_escalation_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_no_allow_privilege_escalation(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)
            containers = patched.get("spec", {}).get("containers", [])
            self.assertTrue(containers)
            for container in containers:
                security = container.get("securityContext")
                self.assertIsInstance(security, dict)
                self.assertFalse(security.get("allowPrivilegeEscalation", True))
            with self.assertRaises(PatchError):
                proposer_cli._patch_no_allow_privilege_escalation(patched)

    def test_no_host_path_patch_removes_hostpath(self) -> None:
        for _ in range(40):
            manifest = build_host_path_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_no_host_path(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)
            volumes = patched.get("spec", {}).get("volumes", [])
            for volume in volumes:
                self.assertNotIn("hostPath", volume)
            with self.assertRaises(PatchError):
                proposer_cli._patch_no_host_path(patched)

    def test_read_only_root_fs_patch(self) -> None:
        for _ in range(60):
            manifest = build_read_only_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_read_only_root_fs(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)
            containers = patched.get("spec", {}).get("containers", [])
            for container in containers:
                security = container.get("securityContext")
                self.assertIsInstance(security, dict)
                self.assertTrue(security.get("readOnlyRootFilesystem"))
            with self.assertRaises(PatchError):
                proposer_cli._patch_read_only_root_fs(patched)

    def test_enforce_seccomp_patch(self) -> None:
        for _ in range(40):
            manifest = build_seccomp_manifest()
            original = copy.deepcopy(manifest)
            patches = proposer_cli._patch_enforce_seccomp(copy.deepcopy(original))
            patched = jsonpatch.apply_patch(original, patches, in_place=False)
            containers = patched.get("spec", {}).get("containers", [])
            for container in containers:
                security = container.get("securityContext")
                self.assertIsInstance(security, dict)
                profile = security.get("seccompProfile")
                self.assertIsInstance(profile, dict)
                self.assertEqual(profile.get("type"), "RuntimeDefault")
            with self.assertRaises(PatchError):
                proposer_cli._patch_enforce_seccomp(patched)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
