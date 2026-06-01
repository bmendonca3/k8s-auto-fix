#!/usr/bin/env python3
"""Create independent structural detector labels for the ArtifactHub sample."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "data/eval/artifacthub_sample"
OUT = ROOT / "data/eval/artifacthub_sample_labels_structural.json"
PROTOCOL = ROOT / "data/eval/artifacthub_sample_labeling_protocol.md"

ALLOWLIST_HOSTPATH_PREFIXES = (
    "/var/run/secrets/kubernetes.io/serviceaccount",
    "/var/lib/kubelet/pods",
    "/etc/ssl/certs",
)
DANGEROUS_CAPS = {"NET_RAW", "NET_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_CHROOT"}


def docs(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [doc for doc in yaml.safe_load_all(handle) if isinstance(doc, dict)]


def containers(spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("containers", "initContainers", "ephemeralContainers"):
        vals = spec.get(key) or []
        if isinstance(vals, list):
            out.extend(c for c in vals if isinstance(c, dict))
    return out


def pod_spec(obj: dict[str, Any]) -> dict[str, Any] | None:
    kind = obj.get("kind")
    spec = obj.get("spec") or {}
    if kind in {"Pod"}:
        return spec if isinstance(spec, dict) else None
    if kind == "CronJob" and isinstance(spec, dict):
        job_spec = ((spec.get("jobTemplate") or {}).get("spec") or {})
        tmpl = job_spec.get("template") if isinstance(job_spec, dict) else None
        if isinstance(tmpl, dict):
            tspec = tmpl.get("spec")
            return tspec if isinstance(tspec, dict) else None
    tmpl = spec.get("template") if isinstance(spec, dict) else None
    if isinstance(tmpl, dict):
        tspec = tmpl.get("spec")
        return tspec if isinstance(tspec, dict) else None
    return None


def image_latest(image: str) -> bool:
    if not image or "@sha256:" in image:
        return False
    last = image.rsplit("/", 1)[-1]
    if ":" not in last:
        return True
    return last.rsplit(":", 1)[-1] == "latest"


def labels_for_obj(obj: dict[str, Any], known_sas: set[tuple[str, str]], pod_labels: list[tuple[str, dict[str, str]]]) -> set[str]:
    labels: set[str] = set()
    kind = obj.get("kind")
    meta = obj.get("metadata") or {}
    ns = meta.get("namespace") or "default"
    spec = obj.get("spec") or {}
    pspec = pod_spec(obj)

    if isinstance(spec, dict) and kind == "Service":
        selector = spec.get("selector") or {}
        if isinstance(selector, dict) and selector:
            if not any(pns == ns and all(plabels.get(k) == v for k, v in selector.items()) for pns, plabels in pod_labels):
                labels.add("dangling_service")

    if kind == "Job" and isinstance(spec, dict) and "ttlSecondsAfterFinished" not in spec:
        labels.add("job_ttl_after_finished")

    if not isinstance(pspec, dict):
        return labels

    if pspec.get("hostNetwork") is True:
        labels.add("no_host_network")
    if pspec.get("hostPID") is True:
        labels.add("no_host_pid")
    if pspec.get("hostIPC") is True:
        labels.add("no_host_ipc")

    sa = pspec.get("serviceAccountName")
    if sa and (ns, str(sa)) not in known_sas:
        labels.add("non_existent_service_account")

    pod_sc = pspec.get("securityContext") or {}
    if pod_sc.get("runAsNonRoot") is False or pod_sc.get("runAsUser") == 0:
        labels.add("run_as_non_root")

    for vol in pspec.get("volumes") or []:
        hp = vol.get("hostPath") if isinstance(vol, dict) else None
        path = hp.get("path") if isinstance(hp, dict) else None
        if path and not str(path).startswith(ALLOWLIST_HOSTPATH_PREFIXES):
            labels.add("no_host_path")

    for c in containers(pspec):
        sc = c.get("securityContext") or {}
        if image_latest(str(c.get("image") or "")):
            labels.add("no_latest_tag")
        if sc.get("privileged") is True:
            labels.add("no_privileged")

        run_as_non_root = sc.get("runAsNonRoot", pod_sc.get("runAsNonRoot"))
        run_as_user = sc.get("runAsUser", pod_sc.get("runAsUser"))
        known_non_root_uid = isinstance(run_as_user, int) and run_as_user > 0
        if run_as_non_root is not True and not known_non_root_uid:
            labels.add("run_as_non_root")

        if sc.get("readOnlyRootFilesystem") is not True:
            labels.add("read_only_root_fs")
        if sc.get("allowPrivilegeEscalation") is True:
            labels.add("no_allow_privilege_escalation")
        caps = sc.get("capabilities") or {}
        added = {str(v).upper() for v in (caps.get("add") or [])}
        dropped = {str(v).upper() for v in (caps.get("drop") or [])}
        if "SYS_ADMIN" not in dropped and "ALL" not in dropped:
            labels.add("drop_cap_sys_admin")
        if "SYS_ADMIN" in added:
            labels.add("drop_cap_sys_admin")
        if added & DANGEROUS_CAPS:
            labels.add("drop_capabilities")
        resources = c.get("resources") or {}
        requests = resources.get("requests") or {}
        limits = resources.get("limits") or {}
        if not all(k in requests for k in ("cpu", "memory")) or not all(k in limits for k in ("cpu", "memory")):
            labels.add("set_requests_limits")
        port_names = {p.get("name") for p in c.get("ports") or [] if isinstance(p, dict) and p.get("name")}
        port_nums = {p.get("containerPort") for p in c.get("ports") or [] if isinstance(p, dict) and p.get("containerPort") is not None}
        for pname, policy in (("livenessProbe", "liveness_port"), ("readinessProbe", "readiness_port"), ("startupProbe", "startup_port")):
            probe = c.get(pname) or {}
            ref = (probe.get("httpGet") or probe.get("tcpSocket") or {}).get("port") if isinstance(probe, dict) else None
            if ref is not None and ref not in port_names and ref not in port_nums:
                labels.add(policy)
        for port in c.get("ports") or []:
            if isinstance(port, dict) and port.get("hostPort") is not None:
                labels.add("no_host_ports")
    return labels


def main() -> None:
    files = sorted(SAMPLE_DIR.glob("*.yaml"))
    all_docs = {path: docs(path) for path in files}
    known_sas = {
        ((obj.get("metadata") or {}).get("namespace") or "default", (obj.get("metadata") or {}).get("name"))
        for objs in all_docs.values()
        for obj in objs
        if obj.get("kind") == "ServiceAccount" and (obj.get("metadata") or {}).get("name")
    }
    pod_labels: list[tuple[str, dict[str, str]]] = []
    for objs in all_docs.values():
        for obj in objs:
            meta = obj.get("metadata") or {}
            ns = meta.get("namespace") or "default"
            spec = obj.get("spec") or {}
            labels = {}
            if obj.get("kind") == "Pod":
                labels = meta.get("labels") or {}
            elif isinstance(spec, dict) and isinstance(spec.get("template"), dict):
                labels = ((spec["template"].get("metadata") or {}).get("labels") or {})
            if isinstance(labels, dict) and labels:
                pod_labels.append((ns, {str(k): str(v) for k, v in labels.items()}))

    result = {}
    for path, objs in all_docs.items():
        found: set[str] = set()
        for obj in objs:
            found |= labels_for_obj(obj, known_sas, pod_labels)
        result[str(path.relative_to(ROOT))] = sorted(found)

    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PROTOCOL.write_text(
        "# ArtifactHub Detector Structural Labels\n\n"
        "Generated by `scripts/label_artifacthub_detector_structural.py` from YAML structure, "
        "not from detector output. The labeler checks Kubernetes fields against the configured "
        "policy semantics used in the sample: explicit unsafe values such as `privileged: true`, "
        "`hostNetwork: true`, `hostPath`, `:latest` images, invalid probe ports, dangling "
        "services, and missing hardening controls such as absent `runAsNonRoot`, absent "
        "`readOnlyRootFilesystem: true`, missing CPU/memory requests or limits, and missing "
        "`SYS_ADMIN`/`ALL` capability drops. CronJob pod templates are traversed through "
        "`spec.jobTemplate.spec.template.spec`. These labels are an independent structural "
        "oracle for the sample, not human adjudication and not a broad detector benchmark.\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
