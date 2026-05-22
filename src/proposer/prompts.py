from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from .guidance_store import GuidanceStore
from .retriever import FailureCache, GuidanceRetriever

SERVICE_ACCOUNT_ALLOW_ANNOTATION = "k8s-auto-fix.dev/allow-default-service-account"

GUIDANCE_DIR = Path(__file__).resolve().parents[2] / "docs" / "policy_guidance"
GUIDANCE_STORE = GuidanceStore.default()
GUIDANCE_RETRIEVER = GuidanceRetriever(GUIDANCE_STORE)
FAILURE_CACHE = FailureCache()


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
        "- Prefer secure defaults: replace hostPath volumes with emptyDir: {} unless explicitly instructed otherwise.\n"
        "- Use RFC6901 JSON Pointer encoding in patch paths: escape '~' as '~0' and '/' as '~1' within key names (do NOT use URL encoding)."
    )
    feedback = detection.get("retry_feedback")
    failure_hint = ""
    if isinstance(feedback, str) and feedback.strip():
        failure_hint = feedback.strip()
        sections.append(f"Verifier feedback: {failure_hint}")
    else:
        failure_hint = FAILURE_CACHE.lookup(detection.get("id", ""))
        if failure_hint:
            sections.append(f"Verifier feedback: {failure_hint}")
    guidance = _policy_guidance(policy_id, failure_hint or None)
    if guidance:
        sections.append(f"Guidance:\n{guidance}")
    sections.append("Return ONLY a valid RFC6902 JSON Patch array.")
    return "\n\n".join(sections)


def _policy_guidance(policy_id: str, failure_hint: Optional[str] = None) -> str:
    retrieved = GUIDANCE_RETRIEVER.retrieve(policy_id, failure_hint)
    if retrieved:
        return retrieved
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
        return "Ensure /spec/containers/0/securityContext exists. Then set runAsNonRoot to true."
    if key == "no_host_path":
        return "Replace any volume hostPath usage by removing hostPath and adding emptyDir: {} for that volume."
    if key == "no_host_ports":
        return "Remove the hostPort field from every container port entry so pods rely on service networking instead."
    if key == "run_as_user":
        return (
            "Ensure securityContext exists and set runAsUser to a non-root UID such as 1000. "
            "Only add or update securityContext/runAsUser (and create securityContext if missing); avoid unrelated changes."
        )
    if key == "enforce_seccomp":
        return 'Set securityContext.seccompProfile.type to "RuntimeDefault" (create securityContext/seccompProfile if missing).'
    if key == "drop_capabilities":
        return (
            "Ensure dangerous capabilities (NET_RAW, NET_ADMIN, SYS_ADMIN, SYS_MODULE, SYS_PTRACE, SYS_CHROOT) are dropped and absent from capabilities.add."
        )
    if key == "dangling_service":
        return (
            "Ensure the Service stays ClusterIP-backed and targets a stable label. Prefer reusing metadata.labels (e.g. app=...) to populate spec.selector, and do not remove ports or clusterIP entries. If no safe selector exists, leave the Service for manual review."
        )
    if key == "non_existent_service_account":
        return (
            f'Ensure every Pod spec uses an existing ServiceAccount. Only switch serviceAccountName/serviceAccount to "default" when the manifest opts in via the annotation {SERVICE_ACCOUNT_ALLOW_ANNOTATION}=true.'
        )
    if key == "pdb_unhealthy_eviction_policy":
        return (
            'Set spec.unhealthyPodEvictionPolicy explicitly (e.g., "AlwaysAllow") so disruptions are controlled even when pods report unhealthy status.'
        )
    if key == "job_ttl_after_finished":
        return "Add spec.ttlSecondsAfterFinished with a reasonable value (for example 3600) so finished Jobs are garbage collected."
    if key == "unsafe_sysctls":
        return "Remove securityContext.sysctls so the pod inherits the cluster defaults instead of forcing unsafe kernel settings."
    if key == "no_anti_affinity":
        return (
            "Add a podAntiAffinity stanza (topologyKey kubernetes.io/hostname) that matches an existing label such as app=... so replicas avoid co-locating."
        )
    if key == "deprecated_service_account_field":
        return "Replace spec.serviceAccount with spec.serviceAccountName and drop the deprecated field."
    if key == "env_var_secret":
        return (
            "Environment variables containing secrets should source values from a Secret. Replace plain `value` assignments with `valueFrom.secretKeyRef` entries."
        )
    if key == "liveness_port":
        return "Ensure the container `ports` list exposes the port referenced by the livenessProbe so HTTP checks can succeed."
    if key == "readiness_port":
        return "Ensure the container `ports` list exposes the port referenced by the readinessProbe so HTTP checks can succeed."
    if key == "startup_port":
        return "Ensure the container `ports` list exposes the port referenced by the startupProbe so HTTP checks can succeed during boot."
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


__all__ = [
    "FAILURE_CACHE",
    "GUIDANCE_DIR",
    "GUIDANCE_RETRIEVER",
    "GUIDANCE_STORE",
    "SERVICE_ACCOUNT_ALLOW_ANNOTATION",
    "_build_prompt",
    "_load_external_guidance",
    "_policy_guidance",
]
