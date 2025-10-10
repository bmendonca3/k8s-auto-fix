from __future__ import annotations

import copy
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import time

import jsonpatch
import yaml

from src.common.policy_ids import normalise_policy_id
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
    latency_ms: Optional[int] = None
    kubectl_ms: Optional[int] = None

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
        verify_start = time.perf_counter()
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

        ok_safety, safety_errors = self._check_safety(patched_obj, policy_id)
        errors.extend(safety_errors)

        ok_schema, schema_error, kubectl_ms = self._kubectl_dry_run(patched_yaml)
        if not ok_schema:
            if schema_error:
                errors.append(f"kubectl dry-run failed: {schema_error}")
            else:
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
            latency_ms=int((time.perf_counter() - verify_start) * 1000),
            kubectl_ms=kubectl_ms,
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

    def _kubectl_dry_run(self, manifest_yaml: str) -> Tuple[bool, Optional[str], int]:
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                [self.kubectl_cmd, "apply", "-f", "-", "--dry-run=server"],
                input=manifest_yaml.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except FileNotFoundError:
            message = "kubectl executable not found"
            return (not self.require_kubectl, message if self.require_kubectl else None, int((time.perf_counter() - start) * 1000))
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="ignore").strip()
            stdout = (exc.stdout or b"").decode("utf-8", errors="ignore").strip()
            detail = stderr or stdout or str(exc)
            if self.require_kubectl:
                return (False, detail, int((time.perf_counter() - start) * 1000))
            return (True, None, int((time.perf_counter() - start) * 1000))
        except Exception as exc:  # pragma: no cover - unexpected
            detail = str(exc)
            if self.require_kubectl:
                return (False, detail, int((time.perf_counter() - start) * 1000))
            return (True, None, int((time.perf_counter() - start) * 1000))
        return (completed.returncode == 0, None, int((time.perf_counter() - start) * 1000))

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

        if policy_id == "read_only_root_fs":
            for container in containers:
                security = container.get("securityContext")
                if isinstance(security, dict):
                    if security.get("readOnlyRootFilesystem") is not True:
                        errors.append("readOnlyRootFilesystem not enforced")
                else:
                    errors.append("securityContext missing for container")
            return (not errors, errors)

        if policy_id == "run_as_non_root":
            for container in containers:
                security = container.get("securityContext") if isinstance(container, dict) else None
                run_as_non_root = security.get("runAsNonRoot") if isinstance(security, dict) else None
                run_as_user = security.get("runAsUser") if isinstance(security, dict) else None
                if run_as_non_root is True:
                    continue
                if isinstance(run_as_user, int) and run_as_user != 0:
                    continue
                errors.append("container still permitted to run as root")
            return (not errors, errors)

        if policy_id == "set_requests_limits":
            for container in containers:
                resources = container.get("resources") if isinstance(container, dict) else None
                if not isinstance(resources, dict):
                    errors.append("resources block missing for container")
                    continue
                requests = resources.get("requests")
                limits = resources.get("limits")
                for scope, block in (("requests", requests), ("limits", limits)):
                    if not isinstance(block, dict):
                        errors.append(f"{scope} missing for container")
                        continue
                    cpu = block.get("cpu")
                    memory = block.get("memory")
                    if not isinstance(cpu, str) or not cpu.strip():
                        errors.append(f"{scope}.cpu missing or empty")
                    if not isinstance(memory, str) or not memory.strip():
                        errors.append(f"{scope}.memory missing or empty")
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

        if policy_id == "dangling_service":
            spec = manifest.get("spec")
            if not isinstance(spec, dict):
                errors.append("service spec missing after patch")
                return (False, errors)
            if spec.get("type") != "ExternalName":
                errors.append("service type not ExternalName")
            if "selector" in spec:
                errors.append("service still defines a selector")
            if not isinstance(spec.get("externalName"), str):
                errors.append("externalName missing")
            return (not errors, errors)

        if policy_id == "non_existent_service_account":
            specs = self._collect_pod_specs(manifest)
            if not specs:
                errors.append("no pod specs located for service account check")
                return (False, errors)
            for spec in specs:
                sa_name = spec.get("serviceAccountName") or spec.get("serviceAccount")
                if sa_name not in (None, "default"):
                    errors.append(f"serviceAccountName still references '{sa_name}'")
            return (not errors, errors)

        if policy_id == "env_var_secret":
            for container in containers:
                env_list = container.get("env")
                if not isinstance(env_list, list):
                    continue
                for env_entry in env_list:
                    if not isinstance(env_entry, dict):
                        continue
                    name = env_entry.get("name")
                    if not isinstance(name, str):
                        continue
                    lowered = name.lower()
                    if "secret" not in lowered and "password" not in lowered:
                        continue
                    value_from = env_entry.get("valueFrom")
                    if not (
                        isinstance(value_from, dict)
                        and isinstance(value_from.get("secretKeyRef"), dict)
                    ):
                        errors.append(f"environment variable {name} must use secretKeyRef")
            return (not errors, errors)

        if policy_id == "pdb_unhealthy_eviction_policy":
            spec = manifest.get("spec")
            if not isinstance(spec, dict):
                errors.append("PDB spec missing after patch")
                return (False, errors)
            value = spec.get("unhealthyPodEvictionPolicy")
            if not isinstance(value, str) or not value.strip():
                errors.append("unhealthyPodEvictionPolicy not set")
            return (not errors, errors)

        if policy_id in {"liveness_port", "readiness_port", "startup_port"}:
            probe_field = {
                "liveness_port": "livenessProbe",
                "readiness_port": "readinessProbe",
                "startup_port": "startupProbe",
            }[policy_id]
            for container in containers:
                probe = container.get(probe_field)
                if not isinstance(probe, dict):
                    continue
                port = None
                port_name: Optional[str] = None
                for field in ("httpGet", "tcpSocket", "grpc"):
                    details = probe.get(field)
                    if isinstance(details, dict) and details.get("port") is not None:
                        candidate = details.get("port")
                        if isinstance(candidate, int):
                            port = candidate
                        elif isinstance(candidate, str):
                            stripped = candidate.strip()
                            if stripped.isdigit():
                                port = int(stripped)
                            else:
                                port_name = stripped
                                port = self._lookup_container_port(container, stripped)
                                if port is None and not self._port_name_exists(container, stripped):
                                    errors.append(
                                        f"{probe_field} port must map to a numeric container port: {candidate}"
                                    )
                        break
                if port is None:
                    continue
                if not self._container_has_port(container, port, port_name):
                    label = port_name if port_name else port
                    errors.append(f"{probe_field} port {label} not exposed in container ports")
            return (not errors, errors)

        if policy_id == "unsafe_sysctls":
            specs = self._collect_pod_specs(manifest)
            for spec in specs:
                security = spec.get("securityContext") if isinstance(spec, dict) else None
                if isinstance(security, dict) and security.get("sysctls"):
                    errors.append("securityContext.sysctls still present")
            return (not errors, errors)

        if policy_id == "deprecated_service_account_field":
            specs = self._collect_pod_specs(manifest)
            for spec in specs:
                if isinstance(spec, dict) and "serviceAccount" in spec:
                    errors.append("serviceAccount field still present")
            return (not errors, errors)

        if policy_id == "no_anti_affinity":
            specs = self._collect_pod_specs(manifest)
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                affinity = spec.get("affinity")
                pod_aff = affinity.get("podAntiAffinity") if isinstance(affinity, dict) else None
                preferred = (
                    pod_aff.get("preferredDuringSchedulingIgnoredDuringExecution")
                    if isinstance(pod_aff, dict)
                    else None
                )
                if not preferred:
                    errors.append("podAntiAffinity preferred rules missing")
            return (not errors, errors)

        if policy_id == "job_ttl_after_finished":
            spec = manifest.get("spec")
            if not isinstance(spec, dict):
                errors.append("job spec missing after patch")
                return (False, errors)
            ttl = spec.get("ttlSecondsAfterFinished")
            if not isinstance(ttl, int) or ttl <= 0:
                errors.append("ttlSecondsAfterFinished missing or non-positive")
            return (not errors, errors)

        # Default: no additional policy checks
        return (True, errors)

    def _check_safety(self, manifest: Dict[str, Any], policy_id: str) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        containers = self._collect_containers(manifest)
        init_containers = self._collect_containers(manifest, container_types=("initContainers",))
        ephemeral_containers = self._collect_containers(manifest, container_types=("ephemeralContainers",))

        if not containers and not init_containers and not ephemeral_containers:
            allowed = {
                "dangling_service",
                "non_existent_service_account",
                "pdb_unhealthy_eviction_policy",
                "unsafe_sysctls",
                "deprecated_service_account_field",
                "no_anti_affinity",
                "job_ttl_after_finished",
            }
            if normalise_policy_id(policy_id) not in allowed:
                errors.append("no containers found in manifest")
                return (False, errors)
            return (True, errors)
        for container in containers + init_containers + ephemeral_containers:
            image = container.get("image")
            if not isinstance(image, str) or not image.strip():
                errors.append("container image missing or empty")
            security = container.get("securityContext")
            if isinstance(security, dict) and security.get("privileged") is True:
                errors.append("privileged container detected")
        return (not errors, errors)

    def _collect_containers(
        self,
        manifest: Dict[str, Any],
        *,
        container_types: Tuple[str, ...] = ("containers", "initContainers", "ephemeralContainers"),
    ) -> List[Dict[str, Any]]:
        containers: List[Dict[str, Any]] = []

        def visit(spec: Any) -> None:
            if not isinstance(spec, dict):
                return
            for ctype in container_types:
                raw_containers = spec.get(ctype)
                if isinstance(raw_containers, list):
                    containers.extend([c for c in raw_containers if isinstance(c, dict)])
            template = spec.get("template")
            if isinstance(template, dict):
                visit(template.get("spec"))
            job_template = spec.get("jobTemplate")
            if isinstance(job_template, dict):
                job_spec = job_template.get("spec")
                if isinstance(job_spec, dict):
                    template_obj = job_spec.get("template")
                    if isinstance(template_obj, dict):
                        visit(template_obj.get("spec"))
                direct_template = job_template.get("template")
                if isinstance(direct_template, dict):
                    visit(direct_template.get("spec"))

        visit(manifest.get("spec"))
        return containers

    @staticmethod
    def _lookup_container_port(container: Dict[str, Any], name: str) -> Optional[int]:
        ports = container.get("ports")
        if not isinstance(ports, list):
            return None
        for entry in ports:
            if not isinstance(entry, dict):
                continue
            if entry.get("name") == name and isinstance(entry.get("containerPort"), int):
                return entry["containerPort"]
        return None

    @staticmethod
    def _port_name_exists(container: Dict[str, Any], name: str) -> bool:
        ports = container.get("ports")
        if not isinstance(ports, list):
            return False
        return any(isinstance(entry, dict) and entry.get("name") == name for entry in ports)

    @staticmethod
    def _container_has_port(container: Dict[str, Any], target: int, port_name: Optional[str]) -> bool:
        ports = container.get("ports")
        if not isinstance(ports, list):
            return False
        for entry in ports:
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("containerPort"), int) and entry["containerPort"] == target:
                return True
            if port_name and entry.get("name") == port_name:
                return True
        return False

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
            job_template = spec.get("jobTemplate")
            if isinstance(job_template, dict):
                job_spec = job_template.get("spec")
                if isinstance(job_spec, dict):
                    template_obj = job_spec.get("template")
                    if isinstance(template_obj, dict):
                        visit(template_obj.get("spec"))

        visit(manifest.get("spec"))
        return volumes

    def _collect_pod_specs(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []

        def visit(spec: Any) -> None:
            if not isinstance(spec, dict):
                return
            if any(isinstance(spec.get(key), list) for key in ("containers", "initContainers", "ephemeralContainers")):
                specs.append(spec)
            template = spec.get("template")
            if isinstance(template, dict):
                visit(template.get("spec"))
            job_template = spec.get("jobTemplate")
            if isinstance(job_template, dict):
                job_spec = job_template.get("spec")
                if isinstance(job_spec, dict):
                    template_obj = job_spec.get("template")
                    if isinstance(template_obj, dict):
                        visit(template_obj.get("spec"))

        visit(manifest.get("spec"))
        return specs

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
            target_norm = normalise_policy_id(targeted_policy)
            for r in results:
                rule = (r.rule or "").strip().lower() if r.rule else ""
                if normalise_policy_id(rule) == target_norm:
                    return False
            return True


__all__ = ["Verifier", "VerificationResult"]
