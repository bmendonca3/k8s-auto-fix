from __future__ import annotations

import copy
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonpatch
import yaml

from src.proposer.guards import PatchError


@dataclass
class VerificationResult:
    ok_policy: bool
    ok_schema: bool
    ok_safety: bool
    patched_manifest: Optional[Dict[str, Any]]
    patched_yaml: Optional[str]
    errors: List[str]

    @property
    def accepted(self) -> bool:
        return self.ok_policy and self.ok_schema and self.ok_safety


class Verifier:
    def __init__(self, kubectl_cmd: str = "kubectl") -> None:
        self.kubectl_cmd = kubectl_cmd

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

        return VerificationResult(
            ok_policy=ok_policy,
            ok_schema=ok_schema,
            ok_safety=ok_safety,
            patched_manifest=patched_obj if ok_policy and ok_safety else None,
            patched_yaml=patched_yaml if ok_schema and ok_policy and ok_safety else None,
            errors=errors,
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
            return False
        except subprocess.CalledProcessError:
            return False
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


__all__ = ["Verifier", "VerificationResult"]
