"""Shared helpers for normalising policy identifiers across components."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional


_POLICY_NORMALISATION_MAP = {
    # Image tag policies
    "latest-tag": "no_latest_tag",
    "no_latest_tag": "no_latest_tag",
    # Privilege / capabilities
    "no-privileged": "no_privileged",
    "privileged-container": "no_privileged",
    "privilege-escalation-container": "drop_capabilities",
    "no_privileged": "no_privileged",
    "drop-capabilities": "drop_capabilities",
    "linux-capabilities": "drop_capabilities",
    "invalid-capabilities": "drop_capabilities",
    "drop-net-raw-capability": "drop_capabilities",
    "cap-sys-admin": "drop_cap_sys_admin",
    "sys-admin-capability": "drop_cap_sys_admin",
    # Allow privilege escalation
    "allow-privilege-escalation": "no_allow_privilege_escalation",
    "allow-privilege-escalation-container": "no_allow_privilege_escalation",
    # Host access
    "hostpath": "no_host_path",
    "host-path": "no_host_path",
    "hostpath-volume": "no_host_path",
    "disallow-hostpath": "no_host_path",
    "hostports": "no_host_ports",
    "host-port": "no_host_ports",
    "host-ports": "no_host_ports",
    "disallow-hostports": "no_host_ports",
    "hostnetwork": "no_host_network",
    "host-network": "no_host_network",
    "hostpid": "no_host_pid",
    "host-pid": "no_host_pid",
    "hostipc": "no_host_ipc",
    "host-ipc": "no_host_ipc",
    "sensitive-host-mounts": "no_host_path",
    "docker-sock": "no_host_path",
    # Pod security context
    "run-as-non-root": "run_as_non_root",
    "check-runasnonroot": "run_as_non_root",
    "run-as-user": "run_as_user",
    "check-runasuser": "run_as_user",
    "requires-runasuser": "run_as_user",
    "no-read-only-root-fs": "read_only_root_fs",
    "check-requests-limits": "set_requests_limits",
    "unset-cpu-requirements": "set_requests_limits",
    "unset-memory-requirements": "set_requests_limits",
    # Probes
    "liveness-port": "liveness_port",
    "readiness-port": "readiness_port",
    "startup-port": "startup_port",
    # Secret / env policies
    "env-var-secret": "env_var_secret",
    "envvar-secret": "env_var_secret",
    # ServiceAccount / dangling service
    "dangling-service": "dangling_service",
    "non-existent-service-account": "non_existent_service_account",
    "deprecated-service-account-field": "deprecated_service_account_field",
    # Other KYverno/kube-linter policies referenced
    "pdb-unhealthy-pod-eviction-policy": "pdb_unhealthy_eviction_policy",
    "job-ttl-seconds-after-finished": "job_ttl_after_finished",
    "unsafe-sysctls": "unsafe_sysctls",
    "no-anti-affinity": "no_anti_affinity",
    # Service port validation
    "invalid-target-ports": "invalid_target_ports",
    "invalid_target_ports": "invalid_target_ports",
}


@lru_cache(maxsize=None)
def normalise_policy_id(policy: Optional[str]) -> str:
    """Map a raw policy identifier to the canonical form used across the pipeline."""

    key = (policy or "").strip().lower()
    if not key:
        return ""
    return _POLICY_NORMALISATION_MAP.get(key, key)


__all__ = ["normalise_policy_id"]
