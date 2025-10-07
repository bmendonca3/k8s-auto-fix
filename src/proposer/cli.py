from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml

from .guards import PatchError, extract_json_array
from .model_client import ClientOptions, ModelClient
from src.verifier.jsonpatch_guard import validate_paths_exist

app = typer.Typer(help="Generate JSON patches from detections using configurable backends.")


@app.command()
def propose(
    detections: Path = typer.Option(
        Path("data/detections.json"),
        "--detections",
        "-d",
        help="Path to detections JSON file.",
    ),
    out: Path = typer.Option(
        Path("data/patches.json"),
        "--out",
        "-o",
        help="Where to write generated patches.",
    ),
    config: Path = typer.Option(
        Path("configs/run.yaml"),
        "--config",
        "-c",
        help="Run configuration file.",
    ),
) -> None:
    detections_data = _load_json(detections)
    config_data = _load_yaml(config)
    base_dir = detections.parent.resolve()

    mode = config_data.get("proposer", {}).get("mode", "rules")
    seed = config_data.get("seed")
    rng = random.Random(seed) if seed is not None else random.Random()
    generator = _build_generator(mode, config_data, seed)
    max_attempts = int(config_data.get("max_attempts", 1))

    patches: List[Dict[str, Any]] = []
    for record in detections_data:
        if not isinstance(record, dict):
            raise typer.BadParameter("Detection entries must be JSON objects")
        detection = _normalise_detection(record, base_dir)
        manifest_yaml = detection.get("manifest_yaml")
        policy_id = detection["policy_id"]
        detection_id = detection["id"]
        violation_text = detection["violation_text"]

        patch_ops: Optional[List[Dict[str, Any]]] = None
        attempts = 0
        errors: List[str] = []
        while attempts < max_attempts and patch_ops is None:
            attempts += 1
            try:
                # Include feedback and policy guidance for retries in LLM modes
                detection_for_prompt = dict(detection)
                if errors:
                    detection_for_prompt["retry_feedback"] = "; ".join(errors[-3:])
                raw_patch = generator(detection_for_prompt, rng)
                if isinstance(raw_patch, str):
                    patch_list = extract_json_array(raw_patch)
                else:
                    patch_list = raw_patch
                validate_paths_exist(manifest_yaml, patch_list)
                patch_ops = patch_list
            except PatchError as exc:
                errors.append(str(exc))
        if patch_ops is None:
            raise RuntimeError(
                f"Unable to produce patch for detection {detection_id} after {max_attempts} attempts: {errors}"
            )

        patches.append(
            {
                "id": detection_id,
                "policy_id": policy_id,
                "source": generator.source,
                "patch": patch_ops,
            }
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(patches, indent=2), encoding="utf-8")
    typer.echo(f"Generated {len(patches)} patch(es) to {out.resolve()}")


def _load_json(path: Path) -> List[Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Input file not found: {path}") from exc
    if not isinstance(data, list):
        raise typer.BadParameter("Detections file must contain a JSON array")
    return data


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"Config file not found: {path}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("Config file must contain a mapping")
    return data


def _normalise_detection(record: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
    required_fields = {"id", "policy_id", "violation_text"}
    missing = required_fields - record.keys()
    if missing:
        raise typer.BadParameter(f"Detection missing required fields: {', '.join(sorted(missing))}")

    manifest_yaml = record.get("manifest_yaml")
    if manifest_yaml is None:
        manifest_path = record.get("manifest_path")
        if manifest_path:
            candidate = Path(manifest_path)
            if not candidate.is_absolute():
                candidate = (base_dir / candidate).resolve()
            try:
                manifest_yaml = candidate.read_text(encoding="utf-8")
            except OSError as exc:
                raise typer.BadParameter(f"Failed to read manifest {manifest_path}: {exc}") from exc
        else:
            raise typer.BadParameter("Detection must include manifest_yaml or manifest_path")
    original_policy = str(record["policy_id"]) if "policy_id" in record else ""
    policy_id = _normalise_policy_id(original_policy)
    return {
        "id": str(record["id"]),
        "policy_id": policy_id,
        "violation_text": str(record["violation_text"]),
        "manifest_yaml": manifest_yaml,
    }


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
        "allow-privilege-escalation": "no_allow_privilege_escalation",
        "allow-privilege-escalation-container": "no_allow_privilege_escalation",
        "hostnetwork": "no_host_network",
        "host-network": "no_host_network",
        "hostpid": "no_host_pid",
        "host-pid": "no_host_pid",
        "hostipc": "no_host_ipc",
        "host-ipc": "no_host_ipc",
        "dangerous-capabilities": "drop_capabilities",
        "invalid-capabilities": "drop_capabilities",
        "cap-sys-admin": "drop_cap_sys_admin",
        "sys-admin-capability": "drop_cap_sys_admin",
        "hostpath": "no_host_path",
        "host-path": "no_host_path",
        "hostpath-volume": "no_host_path",
        "disallow-hostpath": "no_host_path",
        "hostports": "no_host_ports",
        "host-ports": "no_host_ports",
        "host-port": "no_host_ports",
        "disallow-hostports": "no_host_ports",
        "run-as-user": "run_as_user",
        "check-runasuser": "run_as_user",
        "requires-runasuser": "run_as_user",
        "seccomp": "enforce_seccomp",
        "requires-seccomp": "enforce_seccomp",
        "seccomp-profile": "enforce_seccomp",
        "drop-capabilities": "drop_capabilities",
        "linux-capabilities": "drop_capabilities",
        "invalid-capabilities-set": "drop_capabilities",
    }
    return mapping.get(key, key)


class _GeneratorWrapper:
    def __init__(self, source: str, func):
        self.source = source
        self._func = func

    def __call__(self, detection: Dict[str, Any], rng: random.Random):
        return self._func(detection, rng)


def _build_generator(mode: str, config: Dict[str, Any], seed: Optional[int]) -> _GeneratorWrapper:
    mode_lower = (mode or "rules").lower()
    proposer_cfg = config.get("proposer", {})
    timeout = float(proposer_cfg.get("timeout_seconds", 60))
    retries = int(proposer_cfg.get("retries", 0))

    if mode_lower in {"vendor", "vllm", "grok"}:
        backend_cfg = config.get(mode_lower, {})
        options = ClientOptions(
            endpoint=backend_cfg.get("endpoint") or proposer_cfg.get("endpoint") or "http://localhost:8000",
            model=backend_cfg.get("model") or proposer_cfg.get("model") or "proposer-model",
            api_key_env=backend_cfg.get("api_key_env"),
            timeout_seconds=timeout,
            retries=retries,
            seed=seed,
            auth_header=backend_cfg.get("auth_header") or proposer_cfg.get("auth_header"),
            auth_scheme=backend_cfg.get("auth_scheme") or proposer_cfg.get("auth_scheme"),
        )
        client = ModelClient(options)

        def func(detection: Dict[str, Any], _rng: random.Random) -> str:
            prompt = _build_prompt(detection)
            return client.request_patch(prompt)

        return _GeneratorWrapper(mode_lower, func)

    if mode_lower == "rules":
        def func(detection: Dict[str, Any], _rng: random.Random) -> List[Dict[str, Any]]:
            return _rule_based_patch(detection)

        return _GeneratorWrapper("rules", func)

    raise typer.BadParameter(f"Unsupported proposer mode: {mode}")


def _build_prompt(detection: Dict[str, Any]) -> str:
    manifest_yaml = detection["manifest_yaml"]
    policy_id = detection["policy_id"]
    violation_text = detection["violation_text"]
    sections = [
        "You are fixing a Kubernetes manifest.",
        "Manifest YAML:",
        manifest_yaml,
        f"Policy: {policy_id}",
        f"Violation: {violation_text}",
    ]
    feedback = detection.get("retry_feedback")
    if isinstance(feedback, str) and feedback.strip():
        sections.append(f"Verifier feedback: {feedback}")
    guidance = _policy_guidance(policy_id)
    if guidance:
        sections.append(f"Guidance:\n{guidance}")
    sections.append("Return ONLY a valid RFC6902 JSON Patch array.")
    return "\n\n".join(sections)


def _policy_guidance(policy_id: str) -> str:
    key = (policy_id or "").lower()
    if key == "set_requests_limits":
        return (
            "If resources.requests or resources.limits are missing, add the missing object(s). "
            "Do not remove fields that don't exist. Use paths like /spec/containers/0/resources, "
            "/spec/containers/0/resources/requests, and /spec/containers/0/resources/limits."
        )
    if key == "read_only_root_fs":
        return (
            "Ensure /spec/containers/0/securityContext exists. Then set readOnlyRootFilesystem to true."
        )
    if key == "run_as_non_root":
        return (
            "Ensure /spec/containers/0/securityContext exists. Then set runAsNonRoot to true."
        )
    if key == "no_host_path":
        return (
            "Replace any volume hostPath usage by removing hostPath and adding emptyDir: {} for that volume."
        )
    if key == "no_host_ports":
        return (
            "Remove the hostPort field from every container port entry so pods rely on service networking instead."
        )
    if key == "run_as_user":
        return (
            "Ensure securityContext exists and set runAsUser to a non-root UID such as 1000."
        )
    if key == "enforce_seccomp":
        return (
            "Set securityContext.seccompProfile.type to \"RuntimeDefault\" (create securityContext/seccompProfile if missing)."
        )
    if key == "drop_capabilities":
        return (
            "Ensure dangerous capabilities (NET_RAW, NET_ADMIN, SYS_ADMIN, SYS_MODULE, SYS_PTRACE, SYS_CHROOT) are dropped and absent from capabilities.add."
        )
    return ""


def _rule_based_patch(detection: Dict[str, Any]) -> List[Dict[str, Any]]:
    manifest_yaml = detection["manifest_yaml"]
    policy_id = detection["policy_id"]
    obj = yaml.safe_load(manifest_yaml) or {}

    if policy_id == "no_latest_tag":
        return _patch_no_latest(obj)
    if policy_id == "no_privileged":
        return _patch_no_privileged(obj)
    if policy_id == "read_only_root_fs":
        return _patch_read_only_root_fs(obj)
    if policy_id == "run_as_non_root":
        return _patch_run_as_non_root(obj)
    if policy_id == "set_requests_limits":
        return _patch_set_requests_limits(obj)
    if policy_id == "no_allow_privilege_escalation":
        return _patch_no_allow_privilege_escalation(obj)
    if policy_id == "no_host_network":
        return _patch_no_host_flag(obj, flag="hostNetwork")
    if policy_id == "no_host_pid":
        return _patch_no_host_flag(obj, flag="hostPID")
    if policy_id == "no_host_ipc":
        return _patch_no_host_flag(obj, flag="hostIPC")
    if policy_id == "drop_cap_sys_admin":
        return _patch_drop_cap_sys_admin(obj)
    if policy_id == "no_host_path":
        return _patch_no_host_path(obj)
    if policy_id == "no_host_ports":
        return _patch_no_host_ports(obj)
    if policy_id == "run_as_user":
        return _patch_run_as_user(obj)
    if policy_id == "enforce_seccomp":
        return _patch_enforce_seccomp(obj)
    if policy_id == "drop_capabilities":
        return _patch_drop_capabilities(obj)
    raise PatchError(f"no rule available for policy {policy_id}")


def _patch_no_latest(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            image = container.get("image")
            if isinstance(image, str) and image.endswith(":latest"):
                new_image = image.rsplit(":", 1)[0] + ":stable"
                path = f"{base_path}/containers/{idx}/image"
                return [{"op": "replace", "path": path, "value": new_image}]
    raise PatchError("no container with :latest tag found")


def _patch_no_privileged(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict) and security.get("privileged") is True:
                path = f"{base_path}/containers/{idx}/securityContext/privileged"
                return [{"op": "replace", "path": path, "value": False}]
    raise PatchError("no privileged container found")


def _patch_read_only_root_fs(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                ro = security.get("readOnlyRootFilesystem")
                if ro is not True:
                    # add or replace readOnlyRootFilesystem
                    path = f"{base_path}/containers/{idx}/securityContext/readOnlyRootFilesystem"
                    return [{"op": "add", "path": path, "value": True}]
            else:
                # add securityContext object
                path = f"{base_path}/containers/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"readOnlyRootFilesystem": True}}]
    raise PatchError("no container found to set readOnlyRootFilesystem")


def _patch_run_as_non_root(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                val = security.get("runAsNonRoot")
                if val is not True:
                    path = f"{base_path}/containers/{idx}/securityContext/runAsNonRoot"
                    return [{"op": "add", "path": path, "value": True}]
            else:
                path = f"{base_path}/containers/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"runAsNonRoot": True}}]
    raise PatchError("no container found to set runAsNonRoot")


def _patch_set_requests_limits(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            resources = container.get("resources")
            if not isinstance(resources, dict):
                path = f"{base_path}/containers/{idx}/resources"
                value = {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "256Mi"},
                }
                return [{"op": "add", "path": path, "value": value}]
            # If resources exists but missing subfields, add the minimal missing piece
            if "requests" not in resources:
                path = f"{base_path}/containers/{idx}/resources/requests"
                return [{"op": "add", "path": path, "value": {"cpu": "100m", "memory": "128Mi"}}]
            if "limits" not in resources:
                path = f"{base_path}/containers/{idx}/resources/limits"
                return [{"op": "add", "path": path, "value": {"cpu": "500m", "memory": "256Mi"}}]
    raise PatchError("no container found to set resources requests/limits")


def _patch_no_allow_privilege_escalation(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                ape = security.get("allowPrivilegeEscalation")
                if ape is not False:
                    path = f"{base_path}/containers/{idx}/securityContext/allowPrivilegeEscalation"
                    return [{"op": "add", "path": path, "value": False}]
            else:
                path = f"{base_path}/containers/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"allowPrivilegeEscalation": False}}]
    raise PatchError("no container found to set allowPrivilegeEscalation=false")


def _patch_no_host_flag(obj: Dict[str, Any], flag: str) -> List[Dict[str, Any]]:
    spec = obj.get("spec")
    if isinstance(spec, dict):
        val = spec.get(flag)
        if val is True:
            return [{"op": "replace", "path": f"/spec/{flag}", "value": False}]
        if val is None:
            return [{"op": "add", "path": f"/spec/{flag}", "value": False}]
    raise PatchError(f"{flag} not present or already false")


def _patch_drop_cap_sys_admin(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            sec = container.get("securityContext")
            if not isinstance(sec, dict):
                path = f"{base_path}/containers/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"capabilities": {"drop": ["SYS_ADMIN"]}}}]
            caps = sec.get("capabilities")
            if not isinstance(caps, dict):
                path = f"{base_path}/containers/{idx}/securityContext/capabilities"
                return [{"op": "add", "path": path, "value": {"drop": ["SYS_ADMIN"]}}]
            drop = caps.get("drop")
            if isinstance(drop, list):
                if "SYS_ADMIN" not in drop:
                    path = f"{base_path}/containers/{idx}/securityContext/capabilities/drop/-"
                    return [{"op": "add", "path": path, "value": "SYS_ADMIN"}]
            else:
                path = f"{base_path}/containers/{idx}/securityContext/capabilities/drop"
                return [{"op": "add", "path": path, "value": ["SYS_ADMIN"]}]
    raise PatchError("no container found to drop CAP_SYS_ADMIN")

DANGEROUS_CAPABILITIES = ("NET_RAW", "NET_ADMIN", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_CHROOT")


def _patch_no_host_path(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    volumes_info = _find_volumes(obj)
    for base_path, volumes in volumes_info:
        for idx, volume in enumerate(volumes):
            host_path = volume.get("hostPath")
            if host_path is None:
                continue
            ops: List[Dict[str, Any]] = [
                {"op": "remove", "path": f"{base_path}/{idx}/hostPath"},
            ]
            if "emptyDir" not in volume:
                ops.append({"op": "add", "path": f"{base_path}/{idx}/emptyDir", "value": {}})
            return ops
    raise PatchError("no hostPath volume found")


def _patch_no_host_ports(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for c_idx, container in enumerate(containers):
            ports = container.get("ports")
            if not isinstance(ports, list):
                continue
            for p_idx, port in enumerate(ports):
                if not isinstance(port, dict):
                    continue
                host_port = port.get("hostPort")
                if isinstance(host_port, int) and host_port != 0:
                    ops.append({"op": "remove", "path": f"{base_path}/containers/{c_idx}/ports/{p_idx}/hostPort"})
                elif isinstance(host_port, str) and host_port.strip() not in {"", "0"}:
                    ops.append({"op": "remove", "path": f"{base_path}/containers/{c_idx}/ports/{p_idx}/hostPort"})
    if ops:
        return ops
    raise PatchError("no hostPort fields found")


def _patch_run_as_user(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                run_as_user = security.get("runAsUser")
                if not isinstance(run_as_user, int) or run_as_user == 0:
                    path = f"{base_path}/containers/{idx}/securityContext/runAsUser"
                    return [{"op": "add", "path": path, "value": 1000}]
            else:
                path = f"{base_path}/containers/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"runAsUser": 1000}}]
    raise PatchError("no container found to set runAsUser")


def _patch_enforce_seccomp(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                profile = security.get("seccompProfile")
                if isinstance(profile, dict) and profile.get("type") == "RuntimeDefault":
                    continue
                path = f"{base_path}/containers/{idx}/securityContext/seccompProfile"
                return [{"op": "add", "path": path, "value": {"type": "RuntimeDefault"}}]
            else:
                path = f"{base_path}/containers/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"seccompProfile": {"type": "RuntimeDefault"}}}]
    raise PatchError("no container found to set seccompProfile")


def _patch_drop_capabilities(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if not isinstance(security, dict):
                path = f"{base_path}/containers/{idx}/securityContext"
                return [
                    {
                        "op": "add",
                        "path": path,
                        "value": {"capabilities": {"drop": list(DANGEROUS_CAPABILITIES)}},
                    }
                ]
            caps = security.get("capabilities")
            caps_path = f"{base_path}/containers/{idx}/securityContext/capabilities"
            if not isinstance(caps, dict):
                return [{"op": "add", "path": caps_path, "value": {"drop": list(DANGEROUS_CAPABILITIES)}}]
            ops: List[Dict[str, Any]] = []
            drop = caps.get("drop")
            if isinstance(drop, list):
                missing = [cap for cap in DANGEROUS_CAPABILITIES if cap not in drop]
                for cap in missing:
                    ops.append({"op": "add", "path": f"{caps_path}/drop/-", "value": cap})
            else:
                ops.append({"op": "add", "path": f"{caps_path}/drop", "value": list(DANGEROUS_CAPABILITIES)})
            add_list = caps.get("add")
            if isinstance(add_list, list):
                filtered = [cap for cap in add_list if cap not in DANGEROUS_CAPABILITIES]
                if filtered != add_list:
                    ops.append({"op": "replace", "path": f"{caps_path}/add", "value": filtered})
            if ops:
                return ops
    raise PatchError("no container found requiring capability adjustments")


def _find_volumes(obj: Dict[str, Any]) -> List[tuple[str, List[Dict[str, Any]]]]:
    results: List[tuple[str, List[Dict[str, Any]]]] = []

    def visit(spec_obj: Any, base_path: str) -> None:
        if not isinstance(spec_obj, dict):
            return
        volumes = spec_obj.get("volumes")
        if isinstance(volumes, list):
            valid_volumes = [v for v in volumes if isinstance(v, dict)]
            if valid_volumes:
                results.append((f"{base_path}/volumes", valid_volumes))
        template = spec_obj.get("template")
        if isinstance(template, dict):
            visit(template.get("spec"), f"{base_path}/template/spec")

    visit(obj.get("spec"), "/spec")
    return results


def _find_containers(obj: Dict[str, Any]) -> List[tuple[str, List[Dict[str, Any]]]]:
    results: List[tuple[str, List[Dict[str, Any]]]] = []

    def visit(spec_obj: Any, base_path: str) -> None:
        if not isinstance(spec_obj, dict):
            return
        containers = spec_obj.get("containers")
        if isinstance(containers, list):
            valid_containers = [c for c in containers if isinstance(c, dict)]
            if valid_containers:
                results.append((base_path, valid_containers))
        template = spec_obj.get("template")
        if isinstance(template, dict):
            visit(template.get("spec"), f"{base_path}/template/spec")

    visit(obj.get("spec"), "/spec")
    return results


if __name__ == "__main__":  # pragma: no cover
    app()
