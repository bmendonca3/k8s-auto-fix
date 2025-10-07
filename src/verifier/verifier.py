from __future__ import annotations

import copy
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonpatch
import yaml

from src.detector.detector import Detector
from src.proposer.guards import PatchError


@dataclass
class VerificationResult:
    ok_policy: bool
    ok_schema: bool
    ok_safety: bool
    patched_manifest: Optional[Dict[str, Any]]
    patched_yaml: Optional[str]
    errors: List[str]
    ok_rescan: bool = True

    @property
    def accepted(self) -> bool:
        return self.ok_policy and self.ok_schema and self.ok_safety and self.ok_rescan


class Verifier:
    def __init__(
        self,
        kubectl_cmd: str = "kubectl",
        *,
        require_kubectl: bool = True,
        enable_rescan: bool = False,
        kube_linter_cmd: Optional[str] = None,
        kyverno_cmd: Optional[str] = None,
        policies_dir: Optional[Path] = None,
    ) -> None:
        self.kubectl_cmd = kubectl_cmd
        self.require_kubectl = require_kubectl
        self.enable_rescan = enable_rescan
        self.kube_linter_cmd = kube_linter_cmd or "kube-linter"
        self.kyverno_cmd = kyverno_cmd or "kyverno"
        self.policies_dir = policies_dir
        self._dangerous_capabilities = ("NET_RAW", "NET_ADMIN", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_CHROOT")

    def verify(
        self,
        manifest_yaml: str,
        patch_ops: List[Dict[str, Any]],
        policy_id: str,
    ) -> VerificationResult:
        errors: List[str] = []
        try:
            base_obj = self._load_manifest(manifest_yaml)
        except PatchError as exc:
            return VerificationResult(False, False, False, None, None, [str(exc)])

        try:
            patched_obj = self._apply_patch(base_obj, patch_ops)
        except PatchError as exc:
            return VerificationResult(False, False, False, None, None, [str(exc)])

        patched_yaml = yaml.safe_dump(patched_obj, sort_keys=False)

        ok_policy, policy_errors = self._check_policy(policy_id, patched_obj)
        errors.extend(policy_errors)

        ok_safety, safety_errors = self._check_safety(patched_obj)
        errors.extend(safety_errors)

        ok_schema = self._kubectl_dry_run(patched_yaml)
        if not ok_schema:
            errors.append("kubectl dry-run failed")

        ok_rescan = True
        if self.enable_rescan and ok_schema and ok_policy and ok_safety:
            try:
                ok_rescan = self._rescan_policy_cleared(patched_yaml, policy_id)
            except Exception as exc:  # pragma: no cover - unexpected rescan error
                ok_rescan = False
                errors.append(f"rescan failed: {exc}")

        return VerificationResult(
            ok_policy=ok_policy,
            ok_schema=ok_schema,
            ok_safety=ok_safety,
            patched_manifest=patched_obj if ok_policy and ok_safety else None,
            patched_yaml=patched_yaml if ok_schema and ok_policy and ok_safety and ok_rescan else None,
            errors=errors,
            ok_rescan=ok_rescan,
        )

    def _load_manifest(self, manifest_yaml: str) -> Dict[str, Any]:
        documents = list(yaml.safe_load_all(manifest_yaml))
        if not documents:
            raise PatchError("manifest is empty")
        first = documents[0]
        if not isinstance(first, dict):
            raise PatchError("manifest must be a mapping")
        return first

    def _apply_patch(
        self, manifest: Dict[str, Any], patch_ops: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        try:
            manifest_copy = copy.deepcopy(manifest)
            return jsonpatch.apply_patch(manifest_copy, patch_ops, in_place=False)
        except jsonpatch.JsonPatchException as exc:
            raise PatchError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - unexpected
            raise PatchError(str(exc)) from exc

    def _kubectl_dry_run(self, manifest_yaml: str) -> bool:
        try:
            completed = subprocess.run(
                [self.kubectl_cmd, "apply", "-f", "-", "--dry-run=server"],
                input=manifest_yaml.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except FileNotFoundError:
            return not self.require_kubectl
        except subprocess.CalledProcessError:
            return not self.require_kubectl
        return completed.returncode == 0

    def _check_policy(self, policy_id: str, manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        containers = self._collect_containers(manifest)

        if policy_id == "no_latest_tag":
            for container in containers:
                image = container.get("image")
                if isinstance(image, str) and image.endswith(":latest"):
                    errors.append("container image still uses :latest")
            return (not errors, errors)

        if policy_id == "no_privileged":
            for container in containers:
                security = container.get("securityContext")
                if isinstance(security, dict) and security.get("privileged") is True:
                    errors.append("container remains privileged")
            return (not errors, errors)

        if policy_id == "no_host_path":
            for volume in self._collect_volumes(manifest):
                if isinstance(volume.get("hostPath"), dict):
                    errors.append("volume still references hostPath")
            return (not errors, errors)

        if policy_id == "no_host_ports":
            for container in containers:
                ports = container.get("ports")
                if not isinstance(ports, list):
                    continue
                for port in ports:
                    if not isinstance(port, dict):
                        continue
                    host_port = port.get("hostPort")
                    if isinstance(host_port, int) and host_port != 0:
                        errors.append("container port still sets hostPort")
                    elif isinstance(host_port, str) and host_port.strip() not in {"", "0"}:
                        errors.append("container port still sets hostPort")
            return (not errors, errors)

        if policy_id == "run_as_user":
            for container in containers:
                security = container.get("securityContext")
                run_as_user = security.get("runAsUser") if isinstance(security, dict) else None
                if not isinstance(run_as_user, int) or run_as_user == 0:
                    errors.append("runAsUser missing or still root")
            return (not errors, errors)

        if policy_id == "enforce_seccomp":
            for container in containers:
                security = container.get("securityContext")
                profile = security.get("seccompProfile") if isinstance(security, dict) else None
                if not isinstance(profile, dict) or profile.get("type") != "RuntimeDefault":
                    errors.append("seccompProfile.type not RuntimeDefault")
            return (not errors, errors)

        if policy_id == "drop_capabilities":
            for container in containers:
                security = container.get("securityContext")
                capabilities = security.get("capabilities") if isinstance(security, dict) else None
                if not isinstance(capabilities, dict):
                    errors.append("capabilities not defined")
                    continue
                drop = capabilities.get("drop")
                if not isinstance(drop, list):
                    errors.append("capabilities.drop missing")
                else:
                    missing = [cap for cap in self._dangerous_capabilities if cap not in drop]
                    if missing:
                        errors.append(f"capabilities.drop missing {', '.join(missing)}")
                add_list = capabilities.get("add")
                if isinstance(add_list, list):
                    remaining = [cap for cap in add_list if cap in self._dangerous_capabilities]
                    if remaining:
                        errors.append(f"capabilities.add still contains {', '.join(remaining)}")
            return (not errors, errors)

        # Default: no additional policy checks
        return (True, errors)

    def _check_safety(self, manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        containers = self._collect_containers(manifest)
        if not containers:
            errors.append("no containers found in manifest")
        for container in containers:
            image = container.get("image")
            if not isinstance(image, str) or not image.strip():
                errors.append("container image missing or empty")
            security = container.get("securityContext")
            if isinstance(security, dict) and security.get("privileged") is True:
                errors.append("privileged container detected")
        return (not errors, errors)

    def _collect_containers(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        containers: List[Dict[str, Any]] = []

        def visit(spec: Any) -> None:
            if not isinstance(spec, dict):
                return
            raw_containers = spec.get("containers")
            if isinstance(raw_containers, list):
                containers.extend([c for c in raw_containers if isinstance(c, dict)])
            template = spec.get("template")
            if isinstance(template, dict):
                visit(template.get("spec"))

        visit(manifest.get("spec"))
        return containers

    def _collect_volumes(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        volumes: List[Dict[str, Any]] = []

        def visit(spec: Any) -> None:
            if not isinstance(spec, dict):
                return
            raw_volumes = spec.get("volumes")
            if isinstance(raw_volumes, list):
                volumes.extend([v for v in raw_volumes if isinstance(v, dict)])
            template = spec.get("template")
            if isinstance(template, dict):
                visit(template.get("spec"))

        visit(manifest.get("spec"))
        return volumes

    def _rescan_policy_cleared(self, patched_yaml: str, targeted_policy: str) -> bool:
        """Re-run kube-linter and Kyverno; accept if the targeted policy no longer appears.

        We do not require zero total violations, only that the specific targeted policy is cleared.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=True) as tmp:
            tmp.write(patched_yaml)
            tmp.flush()
            detector = Detector(
                kube_linter_cmd=self.kube_linter_cmd,
                kyverno_cmd=self.kyverno_cmd,
                policies_dir=self.policies_dir,
            )
            results = detector.detect([Path(tmp.name)])
            target_norm = self._normalise_policy_id(targeted_policy)
            for r in results:
                rule = (r.rule or "").strip().lower() if r.rule else ""
                if self._normalise_policy_id(rule) == target_norm:
                    return False
            return True

    @staticmethod
    def _normalise_policy_id(policy: str) -> str:
        key = (policy or "").strip().lower()
        mapping = {
            "no_latest_tag": "no_latest_tag",
            "latest-tag": "no_latest_tag",
            "privileged-container": "no_privileged",
            "privilege-escalation-container": "no_privileged",
            "no_privileged": "no_privileged",
            "no-read-only-root-fs": "read_only_root_fs",
            "check-requests-limits": "set_requests_limits",
            "unset-cpu-requirements": "set_requests_limits",
            "unset-memory-requirements": "set_requests_limits",
            "run-as-non-root": "run_as_non_root",
            "check-runasnonroot": "run_as_non_root",
            "hostpath": "no_host_path",
            "host-path": "no_host_path",
            "hostpath-volume": "no_host_path",
            "disallow-hostpath": "no_host_path",
            "hostports": "no_host_ports",
            "host-port": "no_host_ports",
            "host-ports": "no_host_ports",
            "disallow-hostports": "no_host_ports",
            "run-as-user": "run_as_user",
            "check-runasuser": "run_as_user",
            "requires-runasuser": "run_as_user",
            "seccomp": "enforce_seccomp",
            "seccomp-profile": "enforce_seccomp",
            "requires-seccomp": "enforce_seccomp",
            "drop-capabilities": "drop_capabilities",
            "linux-capabilities": "drop_capabilities",
            "invalid-capabilities": "drop_capabilities",
            "cap-sys-admin": "drop_cap_sys_admin",
            "sys-admin-capability": "drop_cap_sys_admin",
        }
        return mapping.get(key, key)


__all__ = ["Verifier", "VerificationResult"]
