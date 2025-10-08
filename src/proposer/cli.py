from __future__ import annotations

import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from functools import lru_cache

import copy
import jsonpatch

import typer
import yaml

from .guidance_store import GuidanceStore
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
    jobs: int = typer.Option(
        1,
        "--jobs",
        "-j",
        min=1,
        help="Number of parallel workers to use (default: 1).",
    ),
) -> None:
    detections_data = _load_json(detections)
    config_data = _load_yaml(config)
    base_dir = detections.parent.resolve()

    mode = config_data.get("proposer", {}).get("mode", "rules")
    seed = config_data.get("seed")
    max_attempts = int(config_data.get("max_attempts", 1))

    patches: List[Dict[str, Any]] = []
    if jobs <= 1:
        generator = _build_generator(mode, config_data, seed)
        rng = random.Random(seed) if seed is not None else random.Random()
        for record in detections_data:
            if not isinstance(record, dict):
                raise typer.BadParameter("Detection entries must be JSON objects")
            patches.append(
                _generate_patch_record(
                    record,
                    config_data=config_data,
                    base_dir=base_dir,
                    generator=generator,
                    rng=rng,
                    max_attempts=max_attempts,
                )
            )
    else:
        jobs = min(jobs, len(detections_data))
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = []
            for index, record in enumerate(detections_data):
                if not isinstance(record, dict):
                    raise typer.BadParameter("Detection entries must be JSON objects")
                rng_seed = None
                if isinstance(seed, int):
                    rng_seed = seed + index
                futures.append(
                    executor.submit(
                        _generate_patch_record,
                        record,
                        config_data=config_data,
                        base_dir=base_dir,
                        max_attempts=max_attempts,
                        rng_seed=rng_seed,
                    )
                )
            for future in futures:
                patches.append(future.result())

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(patches, indent=2), encoding="utf-8")
    typer.echo(f"Generated {len(patches)} patch(es) to {out.resolve()}")


def _generate_patch_record(
    record: Dict[str, Any],
    *,
    config_data: Dict[str, Any],
    base_dir: Path,
    generator: Optional[_GeneratorWrapper] = None,
    rng: Optional[random.Random] = None,
    rng_seed: Optional[int] = None,
    max_attempts: int,
) -> Dict[str, Any]:
    detection = _normalise_detection(record, base_dir)
    manifest_yaml = detection["manifest_yaml"]
    policy_id = detection["policy_id"]
    detection_id = detection["id"]
    mode = config_data.get("proposer", {}).get("mode", "rules")
    seed = config_data.get("seed")

    local_generator = generator if generator is not None else _build_generator(mode, config_data, seed)
    if rng is not None:
        local_rng = rng
    else:
        if rng_seed is not None:
            local_rng = random.Random(rng_seed)
        elif seed is not None:
            local_rng = random.Random(seed)
        else:
            local_rng = random.Random()

    patch_ops: Optional[List[Dict[str, Any]]] = None
    rule_guard_ops: List[Dict[str, Any]] = []
    if local_generator.source != "rules":
        try:
            rule_guard_ops = _rule_based_patch(detection)
        except PatchError:
            rule_guard_ops = []

    attempts = 0
    errors: List[str] = []
    while attempts < max_attempts and patch_ops is None:
        attempts += 1
        try:
            detection_for_prompt = dict(detection)
            if errors:
                detection_for_prompt["retry_feedback"] = "; ".join(errors[-3:])
            raw_patch = local_generator(detection_for_prompt, local_rng)
            if isinstance(raw_patch, str):
                patch_list = extract_json_array(raw_patch)
            else:
                patch_list = raw_patch
            validate_paths_exist(manifest_yaml, patch_list)
            patch_ops = patch_list
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    hardened = local_generator.source == "rules"
    if patch_ops is None:
        if rule_guard_ops:
            patch_ops = rule_guard_ops
            hardened = True
        else:
            raise RuntimeError(
                f"Unable to produce patch for detection {detection_id} after {max_attempts} attempts: {errors}"
            )

    if rule_guard_ops and local_generator.source != "rules":
        combined = _merge_patch_ops(patch_ops, rule_guard_ops)
        try:
            validate_paths_exist(manifest_yaml, combined)
            patch_ops = combined
            hardened = True
        except PatchError:
            patch_ops = rule_guard_ops
            hardened = True

    result: Dict[str, Any] = {
        "id": detection_id,
        "policy_id": policy_id,
        "source": local_generator.source,
        "hardened": hardened,
        "patch": patch_ops,
    }
    if errors:
        result["attempt_errors"] = errors
    return result


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
        "privilege-escalation-container": "drop_capabilities",
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
        "drop-net-raw-capability": "drop_capabilities",
        "dangling-service": "dangling_service",
        "non-existent-service-account": "non_existent_service_account",
        "pdb-unhealthy-pod-eviction-policy": "pdb_unhealthy_eviction_policy",
        "job-ttl-seconds-after-finished": "job_ttl_after_finished",
        "unsafe-sysctls": "unsafe_sysctls",
        "no-anti-affinity": "no_anti_affinity",
        "docker-sock": "no_host_path",
        "sensitive-host-mounts": "no_host_path",
        "deprecated-service-account-field": "deprecated_service_account_field",
        "env-var-secret": "env_var_secret",
        "envvar-secret": "env_var_secret",
        "liveness-port": "liveness_port",
        "readiness-port": "readiness_port",
        "startup-port": "startup_port",
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
    sections.append(
        "Global requirements:\n"
        "- Never leave securityContext.privileged set to true; set it to false for every container.\n"
        "- Always supply concrete CPU and memory values when creating resources.requests or resources.limits (e.g. cpu 100m, memory 128Mi).\n"
        "- When configuring securityContext.capabilities, drop NET_RAW, NET_ADMIN, SYS_ADMIN, SYS_MODULE, SYS_PTRACE, SYS_CHROOT and remove them from capabilities.add.\n"
        "- Prefer secure defaults: replace hostPath volumes with emptyDir: {} unless explicitly instructed otherwise."
    )
    feedback = detection.get("retry_feedback")
    if isinstance(feedback, str) and feedback.strip():
        sections.append(f"Verifier feedback: {feedback}")
    guidance = _policy_guidance(policy_id)
    if guidance:
        sections.append(f"Guidance:\n{guidance}")
    sections.append("Return ONLY a valid RFC6902 JSON Patch array.")
    return "\n\n".join(sections)


def _policy_guidance(policy_id: str) -> str:
    store_guidance = GUIDANCE_STORE.render(policy_id)
    if store_guidance:
        return store_guidance
    key = (policy_id or "").lower()
    external = _load_external_guidance(key)
    if external:
        return external
    if key == "set_requests_limits":
        return (
            "If resources.requests or resources.limits are missing, add the missing object(s). "
            "Do not remove fields that don't exist. Use paths like /spec/containers/0/resources, "
            "/spec/containers/0/resources/requests, and /spec/containers/0/resources/limits. "
            "Populate cpu and memory with sane defaults (e.g. requests.cpu=100m, requests.memory=128Mi, limits.cpu=500m, limits.memory=256Mi)."
        )
    if key == "read_only_root_fs":
        return (
            "Ensure /spec/containers/0/securityContext exists. Then set readOnlyRootFilesystem to true and make sure privileged is set to false."
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
            "Ensure securityContext exists and set runAsUser to a non-root UID such as 1000. "
            "Only add or update securityContext/runAsUser (and create securityContext if missing); avoid unrelated changes."
        )
    if key == "enforce_seccomp":
        return (
            "Set securityContext.seccompProfile.type to \"RuntimeDefault\" (create securityContext/seccompProfile if missing)."
        )
    if key == "drop_capabilities":
        return (
            "Ensure dangerous capabilities (NET_RAW, NET_ADMIN, SYS_ADMIN, SYS_MODULE, SYS_PTRACE, SYS_CHROOT) are dropped and absent from capabilities.add."
        )
    if key == "dangling_service":
        return (
            "Convert the Service into an ExternalName service. Remove any selector/ports/clusterIP fields, set spec.type to \"ExternalName\", and add spec.externalName pointing at the appropriate in-cluster DNS name."
        )
    if key == "non_existent_service_account":
        return (
            "Ensure every Pod spec uses a valid ServiceAccount. Prefer switching serviceAccountName/serviceAccount to \"default\" when the referenced account does not exist."
        )
    if key == "pdb_unhealthy_eviction_policy":
        return (
            "Set spec.unhealthyPodEvictionPolicy explicitly (e.g., \"AlwaysAllow\") so disruptions are controlled even when pods report unhealthy status."
        )
    if key == "job_ttl_after_finished":
        return (
            "Add spec.ttlSecondsAfterFinished with a reasonable value (for example 3600) so finished Jobs are garbage collected."
        )
    if key == "unsafe_sysctls":
        return (
            "Remove securityContext.sysctls so the pod inherits the cluster defaults instead of forcing unsafe kernel settings."
        )
    if key == "no_anti_affinity":
        return (
            "Add a podAntiAffinity stanza (topologyKey kubernetes.io/hostname) that matches an existing label such as app=... so replicas avoid co-locating."
        )
    if key == "deprecated_service_account_field":
        return (
            "Replace spec.serviceAccount with spec.serviceAccountName and drop the deprecated field."
        )
    if key == "env_var_secret":
        return (
            "Environment variables containing secrets should source values from a Secret. Replace plain `value` assignments with `valueFrom.secretKeyRef` entries."
        )
    if key == "liveness_port":
        return (
            "Ensure the container `ports` list exposes the port referenced by the livenessProbe so HTTP checks can succeed."
        )
    if key == "readiness_port":
        return (
            "Ensure the container `ports` list exposes the port referenced by the readinessProbe so HTTP checks can succeed."
        )
    if key == "startup_port":
        return (
            "Ensure the container `ports` list exposes the port referenced by the startupProbe so HTTP checks can succeed during boot."
        )
    return ""


@lru_cache(maxsize=None)
def _load_external_guidance(policy_id: str) -> str:
    candidate = GUIDANCE_DIR / f"{policy_id}.md"
    if candidate.exists():
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def _rule_based_patch(detection: Dict[str, Any]) -> List[Dict[str, Any]]:
    manifest_yaml = detection["manifest_yaml"]
    policy_id = detection["policy_id"]
    obj = yaml.safe_load(manifest_yaml) or {}
    if policy_id == "dangling_service":
        ops = _patch_dangling_service(obj)
    elif policy_id == "no_latest_tag":
        ops = _patch_no_latest(obj)
    elif policy_id == "no_privileged":
        ops = _patch_no_privileged(obj)
    elif policy_id == "read_only_root_fs":
        ops = _patch_read_only_root_fs(obj)
    elif policy_id == "run_as_non_root":
        ops = _patch_run_as_non_root(obj)
    elif policy_id == "set_requests_limits":
        ops = _patch_set_requests_limits(obj)
    elif policy_id == "no_allow_privilege_escalation":
        ops = _patch_no_allow_privilege_escalation(obj)
    elif policy_id == "no_host_network":
        ops = _patch_no_host_flag(obj, flag="hostNetwork")
    elif policy_id == "no_host_pid":
        ops = _patch_no_host_flag(obj, flag="hostPID")
    elif policy_id == "no_host_ipc":
        ops = _patch_no_host_flag(obj, flag="hostIPC")
    elif policy_id == "drop_cap_sys_admin":
        ops = _patch_drop_cap_sys_admin(obj)
    elif policy_id == "no_host_path":
        ops = _patch_no_host_path(obj)
    elif policy_id == "no_host_ports":
        ops = _patch_no_host_ports(obj)
    elif policy_id == "run_as_user":
        ops = _patch_run_as_user(obj)
    elif policy_id == "enforce_seccomp":
        ops = _patch_enforce_seccomp(obj)
    elif policy_id == "drop_capabilities":
        ops = _patch_drop_capabilities(obj)
    elif policy_id == "non_existent_service_account":
        ops = _patch_non_existent_service_account(obj)
    elif policy_id == "pdb_unhealthy_eviction_policy":
        ops = _patch_pdb_unhealthy_eviction(obj)
    elif policy_id == "job_ttl_after_finished":
        ops = _patch_job_ttl_after_finished(obj)
    elif policy_id == "unsafe_sysctls":
        ops = _patch_unsafe_sysctls(obj)
    elif policy_id == "no_anti_affinity":
        ops = _patch_no_anti_affinity(obj)
    elif policy_id == "deprecated_service_account_field":
        ops = _patch_deprecated_service_account_field(obj)
    elif policy_id == "env_var_secret":
        ops = _patch_env_var_secret(obj)
    elif policy_id == "liveness_port":
        ops = _patch_probe_port(obj, "liveness")
    elif policy_id == "readiness_port":
        ops = _patch_probe_port(obj, "readiness")
    elif policy_id == "startup_port":
        ops = _patch_probe_port(obj, "startup")
    else:
        raise PatchError(f"no rule available for policy {policy_id}")

    return _augment_with_guardrails(obj, ops, policy_id)


def _merge_patch_ops(primary: List[Dict[str, Any]], guard: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not guard:
        return primary
    merged: List[Dict[str, Any]] = list(primary)
    seen = {json.dumps(op, sort_keys=True) for op in merged if isinstance(op, dict)}
    for op in guard:
        key = json.dumps(op, sort_keys=True)
        if key not in seen:
            merged.append(op)
            seen.add(key)
    return merged


def _patch_dangling_service(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if obj.get("kind") != "Service":
        raise PatchError("dangling-service fix expects a Service resource")
    spec = obj.get("spec")
    if not isinstance(spec, dict):
        raise PatchError("service spec missing")
    metadata = obj.get("metadata") or {}
    name = metadata.get("name")
    if not isinstance(name, str) or not name:
        raise PatchError("service name unavailable")
    namespace = metadata.get("namespace") or "default"
    external_name = f"{name}.{namespace}.svc.cluster.local"

    ops: List[Dict[str, Any]] = []
    type_path = "/spec/type"
    if spec.get("type") != "ExternalName":
        op = "replace" if "type" in spec else "add"
        ops.append({"op": op, "path": type_path, "value": "ExternalName"})
    if "selector" in spec:
        ops.append({"op": "remove", "path": "/spec/selector"})
    if "ports" in spec:
        ops.append({"op": "remove", "path": "/spec/ports"})
    if "clusterIP" in spec:
        ops.append({"op": "remove", "path": "/spec/clusterIP"})
    if spec.get("externalName") != external_name:
        op = "replace" if "externalName" in spec else "add"
        ops.append({"op": op, "path": "/spec/externalName", "value": external_name})
    if not ops:
        raise PatchError("service already uses ExternalName")
    return ops


def _patch_non_existent_service_account(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs_info = _find_pod_specs(obj)
    ops: List[Dict[str, Any]] = []
    for spec_path, spec in specs_info:
        if not isinstance(spec, dict):
            continue
        desired = "default"
        sa_name = spec.get("serviceAccountName")
        if sa_name != desired:
            op = "replace" if sa_name is not None else "add"
            ops.append({"op": op, "path": f"{spec_path}/serviceAccountName", "value": desired})
        sa_legacy = spec.get("serviceAccount")
        if sa_legacy not in (None, desired):
            ops.append({"op": "replace", "path": f"{spec_path}/serviceAccount", "value": desired})
    try:
        ops.extend(_patch_no_privileged(obj))
    except PatchError:
        pass
    if ops:
        return ops
    raise PatchError("service account already valid")


def _patch_pdb_unhealthy_eviction(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if obj.get("kind", "").lower() != "poddisruptionbudget":
        raise PatchError("policy expects a PodDisruptionBudget resource")
    spec = obj.get("spec")
    if not isinstance(spec, dict):
        raise PatchError("PDB spec missing")
    current = spec.get("unhealthyPodEvictionPolicy")
    if isinstance(current, str) and current.strip():
        raise PatchError("unhealthyPodEvictionPolicy already set")
    op = "replace" if "unhealthyPodEvictionPolicy" in spec else "add"
    return [
        {
            "op": op,
            "path": "/spec/unhealthyPodEvictionPolicy",
            "value": "AlwaysAllow",
        }
    ]


def _patch_job_ttl_after_finished(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if obj.get("kind", "").lower() != "job":
        raise PatchError("policy expects a Job resource")
    spec = obj.get("spec")
    if not isinstance(spec, dict):
        raise PatchError("job spec missing")
    current = spec.get("ttlSecondsAfterFinished")
    if isinstance(current, int) and current > 0:
        raise PatchError("ttlSecondsAfterFinished already set")
    op = "replace" if "ttlSecondsAfterFinished" in spec else "add"
    return [
        {
            "op": op,
            "path": "/spec/ttlSecondsAfterFinished",
            "value": 3600,
        }
    ]


def _patch_unsafe_sysctls(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs_info = _find_pod_specs(obj)
    ops: List[Dict[str, Any]] = []
    for spec_path, spec in specs_info:
        if not isinstance(spec, dict):
            continue
        security = spec.get("securityContext")
        if isinstance(security, dict) and security.get("sysctls"):
            ops.append({"op": "remove", "path": f"{spec_path}/securityContext/sysctls"})
    if ops:
        return ops
    raise PatchError("no unsafe sysctls found")


def _patch_deprecated_service_account_field(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs_info = _find_pod_specs(obj)
    ops: List[Dict[str, Any]] = []
    for spec_path, spec in specs_info:
        if not isinstance(spec, dict):
            continue
        legacy = spec.get("serviceAccount")
        if isinstance(legacy, str) and legacy.strip():
            sa_name = spec.get("serviceAccountName")
            if sa_name != legacy:
                op = "replace" if sa_name is not None else "add"
                ops.append({"op": op, "path": f"{spec_path}/serviceAccountName", "value": legacy})
            ops.append({"op": "remove", "path": f"{spec_path}/serviceAccount"})
    try:
        ops.extend(_patch_no_privileged(obj))
    except PatchError:
        pass
    if ops:
        return ops
    raise PatchError("no deprecated serviceAccount field found")


def _build_pod_anti_affinity(labels: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(labels, dict):
        return None
    for key, value in labels.items():
        if isinstance(key, str) and isinstance(value, str) and key and value:
            return {
                "weight": 100,
                "podAffinityTerm": {
                    "topologyKey": "kubernetes.io/hostname",
                    "labelSelector": {
                        "matchExpressions": [
                            {"key": key, "operator": "In", "values": [value]},
                        ]
                    },
                },
            }
    return None


def _patch_no_anti_affinity(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs_info = _find_pod_specs(obj)
    ops: List[Dict[str, Any]] = []
    for spec_path, spec in specs_info:
        if not isinstance(spec, dict):
            continue
        metadata = _get_metadata_for_spec(obj, spec_path)
        labels = metadata.get("labels") if isinstance(metadata, dict) else {}
        preferred_entry = _build_pod_anti_affinity(labels or {})
        if preferred_entry is None:
            continue
        affinity_path = f"{spec_path}/affinity"
        affinity = spec.get("affinity")
        if not isinstance(affinity, dict):
            ops.append({"op": "add", "path": affinity_path, "value": {}})
            affinity = {}
        pod_aff = affinity.get("podAntiAffinity")
        if not isinstance(pod_aff, dict):
            ops.append({"op": "add", "path": f"{affinity_path}/podAntiAffinity", "value": {}})
            pod_aff = {}
        preferred_list = pod_aff.get("preferredDuringSchedulingIgnoredDuringExecution")
        if isinstance(preferred_list, list):
            already = [
                item
                for item in preferred_list
                if isinstance(item, dict)
                and item.get("podAffinityTerm", {})
                .get("labelSelector", {})
                .get("matchExpressions")
                == preferred_entry["podAffinityTerm"]["labelSelector"]["matchExpressions"]
            ]
            if already:
                continue
        else:
            ops.append(
                {
                    "op": "add",
                    "path": f"{affinity_path}/podAntiAffinity/preferredDuringSchedulingIgnoredDuringExecution",
                    "value": [],
                }
            )
        ops.append(
            {
                "op": "add",
                "path": f"{affinity_path}/podAntiAffinity/preferredDuringSchedulingIgnoredDuringExecution/-",
                "value": preferred_entry,
            }
        )
    if ops:
        return ops
    raise PatchError("no anti-affinity gaps found")


def _derive_secret_ref(env_name: str) -> Tuple[str, str]:
    base = env_name.lower()
    secret_name = re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "app"
    if not secret_name.endswith("-secret"):
        secret_name = f"{secret_name}-secret"
    secret_key = re.sub(r"[^a-z0-9]+", "_", base).strip("_") or "value"
    return secret_name, secret_key


def _patch_env_var_secret(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    secret_candidates = _collect_secret_names(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            env_list = container.get("env")
            if not isinstance(env_list, list):
                continue
            for env_idx, env_entry in enumerate(env_list):
                if not isinstance(env_entry, dict):
                    continue
                name = env_entry.get("name")
                if not isinstance(name, str):
                    continue
                lowered = name.lower()
                if "secret" not in lowered and "password" not in lowered:
                    continue
                existing_value_from = env_entry.get("valueFrom")
                if isinstance(existing_value_from, dict) and isinstance(existing_value_from.get("secretKeyRef"), dict):
                    continue
                spec_path = base_path.rsplit("/", 1)[0]
                spec_obj = _resolve_path(obj, spec_path)
                secret_name, secret_key = _select_secret_reference(
                    env_name=name,
                    env_value=env_entry.get("value"),
                    spec=spec_obj,
                    container=container,
                    available_names=secret_candidates,
                )
                replacement = {
                    "name": name,
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": secret_name,
                            "key": secret_key,
                        }
                    },
                }
                return [
                    {
                        "op": "replace",
                        "path": f"{base_path}/{idx}/env/{env_idx}",
                        "value": replacement,
                    }
                ]
    raise PatchError("no secret-like environment variable found")


def _normalise_probe_port(port: Any, ports: Any) -> Tuple[int, Optional[str]]:
    if isinstance(port, int):
        return port, None
    if isinstance(port, str):
        candidate = port.strip()
        if candidate.isdigit():
            return int(candidate), None
        mapped = _lookup_port_by_name(ports, candidate)
        if mapped is not None:
            return mapped, candidate
    raise PatchError("unsupported probe port value")


def _lookup_port_by_name(ports: Any, name: str) -> Optional[int]:
    if not isinstance(ports, list):
        return None
    for entry in ports:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == name and isinstance(entry.get("containerPort"), int):
            return entry["containerPort"]
    return None


def _probe_port_exists(ports: Any, target: int, port_name: Optional[str]) -> bool:
    if not isinstance(ports, list):
        return False
    for entry in ports:
        if not isinstance(entry, dict):
            continue
        container_port = entry.get("containerPort")
        if isinstance(container_port, int) and container_port == target:
            return True
        if port_name and entry.get("name") == port_name:
            return True
    return False


def _patch_probe_port(obj: Dict[str, Any], probe_kind: str) -> List[Dict[str, Any]]:
    probe_field = f"{probe_kind}Probe"
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            probe = container.get(probe_field)
            if not isinstance(probe, dict):
                continue
            ports = container.get("ports")
            port_value = None
            port_name: Optional[str] = None
            for field in ("httpGet", "tcpSocket", "grpc"):
                details = probe.get(field)
                if isinstance(details, dict) and details.get("port") is not None:
                    try:
                        port_value, port_name = _normalise_probe_port(details.get("port"), ports)
                    except PatchError:
                        continue
                    break
            if port_value is None:
                continue
            if _probe_port_exists(ports, port_value, port_name):
                continue
            entry = {"containerPort": port_value}
            if port_name:
                entry["name"] = port_name
            else:
                entry["name"] = f"{probe_kind}-probe"
            ports_path = f"{base_path}/{idx}/ports"
            if not isinstance(ports, list):
                ops.append({"op": "add", "path": ports_path, "value": [entry]})
            else:
                ops.append({"op": "add", "path": f"{ports_path}/-", "value": entry})
    if ops:
        return ops
    raise PatchError(f"no {probe_kind} probe missing container port found")


def _augment_with_guardrails(obj: Dict[str, Any], ops: List[Dict[str, Any]], policy_id: str) -> List[Dict[str, Any]]:
    guard_ops: List[Dict[str, Any]] = []
    try:
        simulated = jsonpatch.apply_patch(copy.deepcopy(obj), ops, in_place=False)
    except jsonpatch.JsonPatchException:
        simulated = None
    manifest_for_guards = simulated if simulated is not None else obj

    guard_strategies = [
        ("drop_capabilities", _patch_drop_capabilities),
        ("no_latest_tag", _patch_no_latest),
        ("set_requests_limits", _patch_set_requests_limits),
        ("run_as_non_root", _patch_run_as_non_root),
        ("no_allow_privilege_escalation", _patch_no_allow_privilege_escalation),
        ("read_only_root_fs", _patch_read_only_root_fs),
        ("env_var_secret", _patch_env_var_secret),
    ]

    cursor = manifest_for_guards
    for skip_policy, func in guard_strategies:
        if policy_id == skip_policy:
            continue
        try:
            additions = func(cursor)
        except PatchError:
            continue
        guard_ops = _merge_patch_ops(guard_ops, additions)
        try:
            cursor = jsonpatch.apply_patch(copy.deepcopy(cursor), additions, in_place=False)
        except jsonpatch.JsonPatchException:
            # If the guard ops fail to apply we still keep them so the
            # verifier can surface the underlying issue.
            pass

    return _merge_patch_ops(ops, guard_ops)


def _resolve_path(obj: Dict[str, Any], path: str) -> Any:
    if not path or path == "/":
        return obj
    current: Any = obj
    parts = [p for p in path.strip("/").split("/") if p]
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _collect_secret_names(obj: Any) -> set[str]:
    names: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if "secretName" in node and isinstance(node["secretName"], str):
                names.add(node["secretName"])
            secret_ref = node.get("secretRef")
            if isinstance(secret_ref, dict):
                ref_name = secret_ref.get("name")
                if isinstance(ref_name, str):
                    names.add(ref_name)
            secret_obj = node.get("secret")
            if isinstance(secret_obj, dict):
                sec_name = secret_obj.get("secretName") or secret_obj.get("name")
                if isinstance(sec_name, str):
                    names.add(sec_name)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return names


def _select_secret_reference(
    env_name: str,
    env_value: Any,
    spec: Any,
    container: Dict[str, Any],
    available_names: set[str],
) -> Tuple[str, str]:
    default_name, default_key = _derive_secret_ref(env_name)
    sorted_names = sorted(available_names)

    if isinstance(env_value, str):
        match = _match_secret_from_mount(spec, container, env_value)
        if match is not None:
            entry = _choose_secret_entry(
                env_name,
                env_value,
                match.get("entries") or [],
                match.get("relative"),
            )
            key = entry.get("key") if entry.get("key") else default_key
            return match["name"], key
        if env_value in available_names:
            return env_value, default_key

    if sorted_names:
        return sorted_names[0], default_key

    return default_name, default_key


def _choose_secret_entry(
    env_name: str,
    env_value: str,
    entries: List[Dict[str, Optional[str]]],
    relative: Optional[str],
) -> Dict[str, Optional[str]]:
    if not entries:
        return {}
    env_name_norm = re.sub(r"[^a-z0-9]", "", env_name.lower())
    env_value_norm = env_value.strip()
    relative_norm = relative.strip() if isinstance(relative, str) else None

    def score(entry: Dict[str, Optional[str]]) -> Tuple[int, int, int]:
        key = entry.get("key") or ""
        path = entry.get("path") or ""
        key_norm = re.sub(r"[^a-z0-9]", "", key.lower()) if key else ""
        path_norm = path.lower() if path else ""

        match_env_name = 1 if key_norm and key_norm == env_name_norm else 0
        match_env_value = 0
        if env_value_norm:
            if path and env_value_norm.endswith(path):
                match_env_value = 2
            elif key and key in env_value_norm:
                match_env_value = 1
        if relative_norm:
            if path and relative_norm == path.lower():
                match_env_value = max(match_env_value, 3)
            elif key and key.lower() == relative_norm.replace("-", "").replace("_", ""):
                match_env_value = max(match_env_value, 2)
        match_default = 1 if key else 0
        return (match_env_value, match_env_name, match_default)

    best = max(entries, key=score)
    return best


def _match_secret_from_mount(spec: Any, container: Dict[str, Any], env_value: str) -> Optional[Dict[str, Any]]:
    if not isinstance(spec, dict):
        return None
    mounts = container.get("volumeMounts")
    if not isinstance(mounts, list):
        return None
    candidate_volume = None
    relative_path: Optional[str] = None
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        mount_path = mount.get("mountPath")
        if not isinstance(mount_path, str):
            continue
        normalized_mount = mount_path.rstrip("/")
        normalized_value = env_value.rstrip("/")
        if normalized_value == normalized_mount:
            candidate_volume = mount.get("name")
            relative_path = ""
            break
        if normalized_value.startswith(normalized_mount + "/"):
            candidate_volume = mount.get("name")
            relative_path = normalized_value[len(normalized_mount) + 1 :]
            break
    if not candidate_volume:
        return None
    volumes = spec.get("volumes")
    if not isinstance(volumes, list):
        return None
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        if volume.get("name") != candidate_volume:
            continue
        secret_obj = volume.get("secret")
        if isinstance(secret_obj, dict):
            name = secret_obj.get("secretName") or secret_obj.get("name")
            if isinstance(name, str):
                return {
                    "name": name,
                    "entries": _extract_secret_entries(secret_obj),
                    "relative": relative_path,
                }
        projected = volume.get("projected")
        if isinstance(projected, dict):
            sources = projected.get("sources")
            if isinstance(sources, list):
                for source in sources:
                    if not isinstance(source, dict):
                        continue
                    secret_source = source.get("secret")
                    if isinstance(secret_source, dict):
                        name = secret_source.get("name")
                        if isinstance(name, str):
                            return {
                                "name": name,
                                "entries": _extract_secret_entries(secret_source),
                                "relative": relative_path,
                            }
    return None


def _extract_secret_entries(secret_obj: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    items = secret_obj.get("items")
    if not isinstance(items, list):
        return []
    entries: List[Dict[str, Optional[str]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        path = item.get("path") if isinstance(item.get("path"), str) else None
        entries.append({"key": key if isinstance(key, str) else None, "path": path})
    return entries


def _patch_no_latest(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            image = container.get("image")
            path = f"{base_path}/{idx}/image"
            if not isinstance(image, str):
                if "image" in container:
                    ops.append({"op": "replace", "path": path, "value": "busybox:stable"})
                else:
                    ops.append({"op": "add", "path": path, "value": "busybox:stable"})
                continue
            if not image.strip():
                ops.append({"op": "replace", "path": path, "value": "busybox:stable"})
                continue
            image_core = image.strip()
            last_segment = image_core.rsplit("/", 1)[-1]
            if ":" in last_segment:
                name, tag = image_core.rsplit(":", 1)
                if tag == "latest":
                    ops.append({"op": "replace", "path": path, "value": f"{name}:stable"})
                continue
            ops.append({"op": "replace", "path": path, "value": f"{image_core}:stable"})
    if ops:
        return ops
    raise PatchError("no container with :latest tag found")


def _patch_no_privileged(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                if security.get("privileged") is True:
                    path = f"{base_path}/{idx}/securityContext/privileged"
                    ops.append({"op": "replace", "path": path, "value": False})
            else:
                path = f"{base_path}/{idx}/securityContext"
                ops.append({"op": "add", "path": path, "value": {"privileged": False}})
    if ops:
        return ops
    raise PatchError("no privileged container found")


def _patch_read_only_root_fs(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            security_path = f"{base_path}/{idx}/securityContext"
            if not isinstance(security, dict):
                ops.append({"op": "add", "path": security_path, "value": {}})
                security = {}
            ro = security.get("readOnlyRootFilesystem")
            if ro is not True:
                path = f"{security_path}/readOnlyRootFilesystem"
                op = "add" if "readOnlyRootFilesystem" not in security else "replace"
                ops.append({"op": op, "path": path, "value": True})
            if security.get("privileged") is not False:
                path = f"{security_path}/privileged"
                op = "replace" if "privileged" in security else "add"
                ops.append({"op": op, "path": path, "value": False})
    if ops:
        return ops
    raise PatchError("no container found to set readOnlyRootFilesystem")


def _patch_run_as_non_root(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            security_path = f"{base_path}/{idx}/securityContext"
            if not isinstance(security, dict):
                ops.append({"op": "add", "path": security_path, "value": {}})
                security = {}
            val = security.get("runAsNonRoot")
            if val is not True:
                path = f"{security_path}/runAsNonRoot"
                op = "add" if "runAsNonRoot" not in security else "replace"
                ops.append({"op": op, "path": path, "value": True})
            if security.get("privileged") is not False:
                path = f"{security_path}/privileged"
                op = "replace" if "privileged" in security else "add"
                ops.append({"op": op, "path": path, "value": False})
    if ops:
        return ops
    raise PatchError("no container found to set runAsNonRoot")


def _patch_set_requests_limits(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            resources = container.get("resources")
            if not isinstance(resources, dict):
                path = f"{base_path}/{idx}/resources"
                value = {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "256Mi"},
                }
                ops.append({"op": "add", "path": path, "value": value})
                resources = value
            requests = resources.get("requests") if isinstance(resources.get("requests"), dict) else None
            limits = resources.get("limits") if isinstance(resources.get("limits"), dict) else None
            missing_requests = {}
            missing_limits = {}
            if requests is None:
                missing_requests = {"cpu": "100m", "memory": "128Mi"}
            else:
                if "cpu" not in requests:
                    missing_requests["cpu"] = "100m"
                if "memory" not in requests:
                    missing_requests["memory"] = "128Mi"
            if limits is None:
                missing_limits = {"cpu": "500m", "memory": "256Mi"}
            else:
                if "cpu" not in limits:
                    missing_limits["cpu"] = "500m"
                if "memory" not in limits:
                    missing_limits["memory"] = "256Mi"

            if missing_requests and missing_limits:
                merged = dict(resources)
                merged["requests"] = dict(requests or {})
                merged["requests"].update(missing_requests)
                merged["limits"] = dict(limits or {})
                merged["limits"].update(missing_limits)
                path = f"{base_path}/{idx}/resources"
                ops.append({"op": "replace", "path": path, "value": merged})
            else:
                if missing_requests:
                    path = f"{base_path}/{idx}/resources/requests"
                    new_requests = dict(requests or {})
                    new_requests.update(missing_requests)
                    op = "add" if requests is None else "replace"
                    ops.append({"op": op, "path": path, "value": new_requests})
                if missing_limits:
                    path = f"{base_path}/{idx}/resources/limits"
                    new_limits = dict(limits or {})
                    new_limits.update(missing_limits)
                    op = "add" if limits is None else "replace"
                    ops.append({"op": op, "path": path, "value": new_limits})
            security = container.get("securityContext")
            security_path = f"{base_path}/{idx}/securityContext"
            if not isinstance(security, dict):
                ops.append({"op": "add", "path": security_path, "value": {}})
                security = {}
            if security.get("privileged") is not False:
                path = f"{security_path}/privileged"
                op = "replace" if "privileged" in security else "add"
                ops.append({"op": op, "path": path, "value": False})
    if ops:
        return ops
    raise PatchError("no container found to set resources requests/limits")


def _patch_no_allow_privilege_escalation(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            if isinstance(security, dict):
                ape = security.get("allowPrivilegeEscalation")
                if ape is not False:
                    path = f"{base_path}/{idx}/securityContext/allowPrivilegeEscalation"
                    return [{"op": "add", "path": path, "value": False}]
            else:
                path = f"{base_path}/{idx}/securityContext"
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
                path = f"{base_path}/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"capabilities": {"drop": ["SYS_ADMIN"]}}}]
            caps = sec.get("capabilities")
            if not isinstance(caps, dict):
                path = f"{base_path}/{idx}/securityContext/capabilities"
                return [{"op": "add", "path": path, "value": {"drop": ["SYS_ADMIN"]}}]
            drop = caps.get("drop")
            if isinstance(drop, list):
                if "SYS_ADMIN" not in drop:
                    path = f"{base_path}/{idx}/securityContext/capabilities/drop/-"
                    return [{"op": "add", "path": path, "value": "SYS_ADMIN"}]
            else:
                path = f"{base_path}/{idx}/securityContext/capabilities/drop"
                return [{"op": "add", "path": path, "value": ["SYS_ADMIN"]}]
    raise PatchError("no container found to drop CAP_SYS_ADMIN")

DANGEROUS_CAPABILITIES = ("NET_RAW", "NET_ADMIN", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_CHROOT")


def _patch_no_host_path(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    volumes_info = _find_volumes(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, volumes in volumes_info:
        for idx, volume in enumerate(volumes):
            host_path = volume.get("hostPath")
            if host_path is None:
                continue
            ops.append({"op": "remove", "path": f"{base_path}/{idx}/hostPath"})
            if "emptyDir" not in volume:
                ops.append({"op": "add", "path": f"{base_path}/{idx}/emptyDir", "value": {}})
    if ops:
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
                    ops.append({"op": "remove", "path": f"{base_path}/{c_idx}/ports/{p_idx}/hostPort"})
                elif isinstance(host_port, str) and host_port.strip() not in {"", "0"}:
                    ops.append({"op": "remove", "path": f"{base_path}/{c_idx}/ports/{p_idx}/hostPort"})
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
                    path = f"{base_path}/{idx}/securityContext/runAsUser"
                    return [{"op": "add", "path": path, "value": 1000}]
            else:
                path = f"{base_path}/{idx}/securityContext"
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
                path = f"{base_path}/{idx}/securityContext/seccompProfile"
                return [{"op": "add", "path": path, "value": {"type": "RuntimeDefault"}}]
            else:
                path = f"{base_path}/{idx}/securityContext"
                return [{"op": "add", "path": path, "value": {"seccompProfile": {"type": "RuntimeDefault"}}}]
    raise PatchError("no container found to set seccompProfile")


def _patch_drop_capabilities(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers_info = _find_containers(obj)
    ops: List[Dict[str, Any]] = []
    for base_path, containers in containers_info:
        for idx, container in enumerate(containers):
            security = container.get("securityContext")
            security_path = f"{base_path}/{idx}/securityContext"
            container_ops: List[Dict[str, Any]] = []
            if not isinstance(security, dict):
                container_ops.append({"op": "add", "path": security_path, "value": {}})
                security = {}
            caps_path = f"{security_path}/capabilities"
            caps = security.get("capabilities") if isinstance(security, dict) else None
            if not isinstance(caps, dict):
                container_ops.append({"op": "add", "path": caps_path, "value": {"drop": list(DANGEROUS_CAPABILITIES)}})
                caps = {"drop": list(DANGEROUS_CAPABILITIES)}
            drop = caps.get("drop")
            if isinstance(drop, list):
                missing = [cap for cap in DANGEROUS_CAPABILITIES if cap not in drop]
                for cap in missing:
                    container_ops.append({"op": "add", "path": f"{caps_path}/drop/-", "value": cap})
            else:
                container_ops.append({"op": "add", "path": f"{caps_path}/drop", "value": list(DANGEROUS_CAPABILITIES)})
            add_list = caps.get("add")
            if isinstance(add_list, list):
                filtered = [cap for cap in add_list if cap not in DANGEROUS_CAPABILITIES]
                if filtered != add_list:
                    container_ops.append({"op": "replace", "path": f"{caps_path}/add", "value": filtered})
            if security.get("privileged") is not False:
                op = "replace" if "privileged" in security else "add"
                container_ops.append({"op": op, "path": f"{security_path}/privileged", "value": False})
            if security.get("allowPrivilegeEscalation") is not False:
                op = "replace" if "allowPrivilegeEscalation" in security else "add"
                container_ops.append({"op": op, "path": f"{security_path}/allowPrivilegeEscalation", "value": False})
            if container_ops:
                ops.extend(container_ops)
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
        job_template = spec_obj.get("jobTemplate")
        if isinstance(job_template, dict):
            template_candidates: List[tuple[Dict[str, Any], str]] = []
            job_spec = job_template.get("spec")
            if isinstance(job_spec, dict):
                job_template_obj = job_spec.get("template")
                if isinstance(job_template_obj, dict):
                    template_candidates.append((job_template_obj, f"{base_path}/jobTemplate/spec/template/spec"))
            direct_template = job_template.get("template")
            if isinstance(direct_template, dict):
                template_candidates.append((direct_template, f"{base_path}/jobTemplate/template/spec"))
            for template_obj, next_path in template_candidates:
                visit(template_obj.get("spec"), next_path)
            direct_template = job_template.get("template")
            if isinstance(direct_template, dict):
                visit(direct_template.get("spec"), f"{base_path}/jobTemplate/template/spec")

    visit(obj.get("spec"), "/spec")
    return results


def _find_pod_specs(obj: Dict[str, Any]) -> List[tuple[str, Dict[str, Any]]]:
    results: List[tuple[str, Dict[str, Any]]] = []

    def visit(spec_obj: Any, base_path: str) -> None:
        if not isinstance(spec_obj, dict):
            return
        if any(
            isinstance(spec_obj.get(key), list) for key in ("containers", "initContainers", "ephemeralContainers")
        ):
            results.append((base_path, spec_obj))
        template = spec_obj.get("template")
        if isinstance(template, dict):
            visit(template.get("spec"), f"{base_path}/template/spec")
        job_template = spec_obj.get("jobTemplate")
        if isinstance(job_template, dict):
            template_candidates: List[tuple[Dict[str, Any], str]] = []
            job_spec = job_template.get("spec")
            if isinstance(job_spec, dict):
                job_template_obj = job_spec.get("template")
                if isinstance(job_template_obj, dict):
                    template_candidates.append((job_template_obj, f"{base_path}/jobTemplate/spec/template/spec"))
            direct_template = job_template.get("template")
            if isinstance(direct_template, dict):
                template_candidates.append((direct_template, f"{base_path}/jobTemplate/template/spec"))
            for template_obj, next_path in template_candidates:
                visit(template_obj.get("spec"), next_path)

    visit(obj.get("spec"), "/spec")
    return results


def _get_metadata_for_spec(obj: Dict[str, Any], spec_path: str) -> Dict[str, Any] | None:
    parts = [p for p in spec_path.strip("/").split("/") if p]
    current: Any = obj
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    if not isinstance(current, dict):
        return None
    metadata = current.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return None


def _find_containers(obj: Dict[str, Any]) -> List[tuple[str, List[Dict[str, Any]]]]:
    results: List[tuple[str, List[Dict[str, Any]]]] = []

    def visit(spec_obj: Any, base_path: str) -> None:
        if not isinstance(spec_obj, dict):
            return
        for key in ("containers", "initContainers", "ephemeralContainers"):
            items = spec_obj.get(key)
            if isinstance(items, list):
                valid_containers = [c for c in items if isinstance(c, dict)]
                if valid_containers:
                    results.append((f"{base_path}/{key}", valid_containers))
        template = spec_obj.get("template")
        if isinstance(template, dict):
            visit(template.get("spec"), f"{base_path}/template/spec")
        job_template = spec_obj.get("jobTemplate")
        if isinstance(job_template, dict):
            job_spec = job_template.get("spec")
            if isinstance(job_spec, dict):
                job_template_obj = job_spec.get("template")
                if isinstance(job_template_obj, dict):
                    visit(job_template_obj.get("spec"), f"{base_path}/jobTemplate/spec/template/spec")
            direct_template = job_template.get("template")
            if isinstance(direct_template, dict):
                visit(direct_template.get("spec"), f"{base_path}/jobTemplate/template/spec")

    visit(obj.get("spec"), "/spec")
    return results


GUIDANCE_DIR = Path(__file__).resolve().parents[2] / "docs" / "policy_guidance"
GUIDANCE_STORE = GuidanceStore.default()


if __name__ == "__main__":  # pragma: no cover
    app()
