#!/usr/bin/env python3
"""
Run live-cluster validation for k8s-auto-fix.

When connected to a staging Kubernetes cluster, this script replays a batch of
manifests, compares server-side dry-run outcomes with real `kubectl apply`
results, and records any divergence. A simulation mode is provided so CI
pipelines and documentation builds can exercise the workflow without a live
cluster (used for the evaluation artefacts in this repository).

Examples:
    # Simulated run (no cluster required)
    python scripts/run_live_cluster_eval.py \
        --manifests data/manifests \
        --simulate \
        --output data/live_cluster/results_simulated.json

    # Real cluster evaluation
    python scripts/run_live_cluster_eval.py \
        --manifests data/live_cluster/batch \
        --namespace-prefix live-eval \
        --output data/live_cluster/results.json

Prerequisites for real runs:
    - `kubectl` in PATH (override with --kubectl).
    - Authenticated context pointing at a non-production cluster.
    - Fixtures from `infra/fixtures/` applied (RBAC, NetworkPolicy, CRDs).
"""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import logging
import pathlib
import random
import string
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import yaml


DEFAULT_RESULTS_PATH = pathlib.Path("data/live_cluster/results.json")
DEFAULT_SUMMARY_PATH = pathlib.Path("data/live_cluster/summary.csv")
FILTER_CONFIG_PATH = pathlib.Path("configs/live_cluster_filters.yaml")
DEFAULT_NFS_SERVER = "nfs.test.local"
PLACEHOLDER_IMAGE = "busybox:1.36"
FILTERED_ERROR_CLASS = "FilteredManifest"

# Lower score = earlier scheduling during evaluation to prioritise primitives
RESOURCE_PRIORITY = {
    "Namespace": 0,
    "CustomResourceDefinition": 0,
    "ServiceAccount": 1,
    "ClusterRole": 1,
    "ClusterRoleBinding": 1,
    "Role": 2,
    "RoleBinding": 2,
    "ConfigMap": 3,
    "Secret": 3,
    "PersistentVolume": 3,
    "PersistentVolumeClaim": 3,
    "Deployment": 4,
    "StatefulSet": 4,
    "DaemonSet": 4,
    "Job": 4,
}

# Static blacklist of resources that consistently fail in ephemeral clusters
DEFAULT_FILTER_RULES: Tuple[Dict[str, Any], ...] = (
    {
        "kind": "MutatingWebhookConfiguration",
        "reason": "Webhook configurations require an external HTTPS endpoint in staging.",
    },
    {
        "kind": "ValidatingWebhookConfiguration",
        "reason": "Webhook configurations require an external HTTPS endpoint in staging.",
    },
    {
        "kind": "PodSecurityPolicy",
        "reason": "PodSecurityPolicy is removed from recent Kubernetes releases.",
    },
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@dataclass
class EvaluationRecord:
    manifest_path: str
    namespace: Optional[str]
    dry_run_pass: Optional[bool]
    live_apply_pass: Optional[bool]
    rollback_triggered: Optional[bool]
    error_class: Optional[str]
    notes: Optional[str]
    kubectl_stdout: Optional[str] = None
    kubectl_stderr: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "manifest_path": self.manifest_path,
            "namespace": self.namespace,
            "dry_run_pass": self.dry_run_pass,
            "live_apply_pass": self.live_apply_pass,
            "rollback_triggered": self.rollback_triggered,
            "error_class": self.error_class,
            "notes": self.notes,
            "kubectl_stdout": self.kubectl_stdout,
            "kubectl_stderr": self.kubectl_stderr,
        }


@dataclass
class ManifestBundle:
    path: pathlib.Path
    docs: List[Any]
    priority: int
    filter_reason: Optional[str] = None


def load_yaml_documents(manifest_yaml: str) -> List[Any]:
    docs = []
    for doc in yaml.safe_load_all(manifest_yaml):
        if doc is not None and doc != "":
            docs.append(doc)
    return docs


def dump_yaml_documents(docs: Sequence[Any]) -> str:
    return yaml.safe_dump_all(
        docs,
        sort_keys=False,
        explicit_start=len(docs) > 1,
    )


def collect_namespace_usage(bundles: Sequence[ManifestBundle]) -> Dict[str, int]:
    counter: Dict[str, int] = collections.Counter()
    for bundle in bundles:
        if bundle.filter_reason:
            continue
        for doc in bundle.docs:
            if isinstance(doc, dict):
                ns = doc.get("metadata", {}).get("namespace")
                if ns:
                    counter[ns] += 1
    return dict(counter)


def calculate_manifest_priority(docs: Sequence[Any]) -> int:
    if not docs:
        return max(RESOURCE_PRIORITY.values(), default=5) + 1
    priorities: List[int] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind")
        if kind in RESOURCE_PRIORITY:
            priorities.append(RESOURCE_PRIORITY[kind])
    if priorities:
        return min(priorities)
    return max(RESOURCE_PRIORITY.values(), default=5) + 1


def load_filter_rules(path: pathlib.Path) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = [dict(rule) for rule in DEFAULT_FILTER_RULES]
    if path.exists():
        loaded = yaml.safe_load(path.read_text()) or []
        if isinstance(loaded, list):
            for rule in loaded:
                if isinstance(rule, dict):
                    rules.append(rule)
        else:
            logging.warning(
                "Live-cluster filter config %s is not a list; ignoring custom rules.",
                path,
            )
    elif path.parent.exists():
        logging.info(
            "No custom live-cluster filter file found at %s; using built-in defaults.",
            path,
        )
    return rules


def _doc_matches_rule(doc: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    if not isinstance(doc, dict):
        return False
    if "kind" in rule and doc.get("kind") != rule["kind"]:
        return False
    if "apiVersion" in rule and doc.get("apiVersion") != rule["apiVersion"]:
        return False
    metadata = doc.get("metadata", {})
    if "metadata.name" in rule and metadata.get("name") != rule["metadata.name"]:
        return False
    if "metadata.namespace" in rule and metadata.get("namespace") != rule["metadata.namespace"]:
        return False
    return True


def manifest_matches_filter(
    manifest_path: pathlib.Path,
    docs: Sequence[Any],
    rules: Sequence[Dict[str, Any]],
) -> Optional[str]:
    for rule in rules:
        reason = rule.get("reason", "Filtered by rule")
        path_substring = rule.get("path_substring")
        if path_substring and path_substring not in str(manifest_path):
            continue
        doc_matched = False
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if _doc_matches_rule(doc, rule):
                doc_matched = True
                break
        name_substring = rule.get("metadata.name_substring")
        if name_substring and not doc_matched:
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                metadata = doc.get("metadata", {})
                if isinstance(metadata, dict) and name_substring in str(metadata.get("name", "")):
                    doc_matched = True
                    break
        if doc_matched:
            return reason
    return None


def collect_crd_definitions(
    bundles: Sequence[ManifestBundle],
) -> Dict[str, str]:
    crds: Dict[str, str] = {}
    for bundle in bundles:
        for doc in bundle.docs:
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") != "CustomResourceDefinition":
                continue
            name = doc.get("metadata", {}).get("name")
            if not name:
                continue
            crds[name] = yaml.safe_dump(doc, sort_keys=False)
    return crds


def install_crds(kubectl: str, crds: Dict[str, str]) -> List[str]:
    installed: List[str] = []
    for name, crd_yaml in crds.items():
        proc = run_kubectl(kubectl, ["apply", "-f", "-"], input_data=crd_yaml)
        if proc.returncode == 0:
            installed.append(name)
            continue
        stderr = proc.stderr.decode()
        if "AlreadyExists" in stderr or "unchanged" in stderr:
            logging.info("CRD %s already present; continuing.", name)
            continue
        logging.error("Failed to install CRD %s: %s", name, stderr.strip())
    if installed:
        logging.info("Installed %d CRDs required for evaluation.", len(installed))
    return installed


def uninstall_crds(kubectl: str, crd_names: Iterable[str]) -> None:
    for name in crd_names:
        proc = run_kubectl(kubectl, ["delete", "crd", name])
        if proc.returncode != 0:
            stderr = proc.stderr.decode().strip()
            if "NotFound" in stderr:
                continue
            logging.warning("Failed to delete CRD %s during teardown: %s", name, stderr)


class NamespaceManager:
    def __init__(self, kubectl: str, namespace_usage: Dict[str, int]):
        self.kubectl = kubectl
        self.namespace_usage = collections.Counter(namespace_usage)
        self.created_namespaces: Dict[str, bool] = {}
        self.checked_namespaces: set[str] = set()
        self.default_sa_ensured: set[str] = set()

    def ensure(
        self,
        namespace: Optional[str],
        ephemeral: bool,
    ) -> Tuple[bool, List[str], Optional[str]]:
        warnings: List[str] = []
        if not namespace:
            return False, warnings, None

        created = False
        if ephemeral:
            proc = run_kubectl(self.kubectl, ["create", "namespace", namespace])
            if proc.returncode != 0 and "AlreadyExists" not in proc.stderr.decode():
                return False, warnings, proc.stderr.decode().strip()
            created = proc.returncode == 0
        else:
            if namespace not in self.checked_namespaces:
                proc = run_kubectl(self.kubectl, ["get", "namespace", namespace])
                if proc.returncode != 0:
                    stderr = proc.stderr.decode()
                    if "NotFound" in stderr or "not found" in stderr:
                        create_proc = run_kubectl(
                            self.kubectl,
                            ["create", "namespace", namespace],
                        )
                        if create_proc.returncode != 0 and "AlreadyExists" not in create_proc.stderr.decode():
                            return False, warnings, create_proc.stderr.decode().strip()
                        created = create_proc.returncode == 0
                    else:
                        return False, warnings, stderr.strip()
                self.checked_namespaces.add(namespace)

        if created:
            self.created_namespaces[namespace] = ephemeral

        sa_warning = self._ensure_default_service_account(namespace)
        if sa_warning:
            warnings.append(sa_warning)

        return created, warnings, None

    def release(self, namespace: Optional[str], ephemeral: bool) -> List[str]:
        warnings: List[str] = []
        if not namespace:
            return warnings

        if ephemeral:
            warnings.extend(self._delete_namespace(namespace))
            return warnings

        if namespace in self.namespace_usage:
            self.namespace_usage[namespace] -= 1
            if self.namespace_usage[namespace] <= 0:
                if namespace in self.created_namespaces and not self.created_namespaces[namespace]:
                    warnings.extend(self._delete_namespace(namespace))
                self.namespace_usage.pop(namespace, None)
        return warnings

    def _delete_namespace(self, namespace: str) -> List[str]:
        warnings: List[str] = []
        delete_proc = run_kubectl(
            self.kubectl,
            ["delete", "namespace", namespace, "--wait=false"],
        )
        if delete_proc.returncode != 0:
            warnings.append(
                f"Namespace cleanup error for {namespace}: {delete_proc.stderr.decode().strip()}"
            )
        else:
            self.created_namespaces.pop(namespace, None)
        return warnings

    def _ensure_default_service_account(self, namespace: str) -> Optional[str]:
        if namespace in self.default_sa_ensured:
            return None
        sa_yaml = f"""apiVersion: v1
kind: ServiceAccount
metadata:
  name: default
  namespace: {namespace}
"""
        proc = run_kubectl(self.kubectl, ["apply", "-f", "-"], input_data=sa_yaml)
        if proc.returncode != 0:
            stderr = proc.stderr.decode()
            if "AlreadyExists" in stderr or "unchanged" in stderr:
                self.default_sa_ensured.add(namespace)
                return None
            return f"Failed to ensure default service account in {namespace}: {stderr.strip()}"
        self.default_sa_ensured.add(namespace)
        return None


def iter_pod_specs(doc: Dict[str, Any]) -> Iterable[Tuple[Dict[str, Any], str]]:
    if not isinstance(doc, dict):
        return []
    kind = doc.get("kind")
    if kind == "Pod":
        spec = doc.get("spec")
        if isinstance(spec, dict):
            return [(spec, "spec")]
        return []

    spec = doc.get("spec")
    if not isinstance(spec, dict):
        return []

    if kind in {"Deployment", "ReplicaSet", "StatefulSet", "DaemonSet"}:
        template = spec.get("template", {})
        template_spec = template.get("spec")
        if isinstance(template_spec, dict):
            return [(template_spec, "spec.template.spec")]
        return []

    if kind == "Job":
        template = spec.get("template", {})
        template_spec = template.get("spec")
        if isinstance(template_spec, dict):
            return [(template_spec, "spec.template.spec")]
        return []

    if kind == "CronJob":
        job_template = spec.get("jobTemplate", {})
        job_spec = job_template.get("spec", {})
        template = job_spec.get("template", {})
        template_spec = template.get("spec")
        if isinstance(template_spec, dict):
            return [(template_spec, "spec.jobTemplate.spec.template.spec")]
        return []

    return []


def iter_containers(pod_spec: Dict[str, Any]) -> Iterable[Tuple[Dict[str, Any], str]]:
    for container in pod_spec.get("containers", []) or []:
        if isinstance(container, dict):
            yield container, "containers"
    for container in pod_spec.get("initContainers", []) or []:
        if isinstance(container, dict):
            yield container, "initContainers"


def enforce_privileged_mounts(
    doc: Dict[str, Any],
    manifest_path: pathlib.Path,
    doc_index: int,
) -> List[str]:
    notes: List[str] = []
    for pod_spec, context in iter_pod_specs(doc):
        for container, container_type in iter_containers(pod_spec):
            mounts = container.get("volumeMounts") or []
            if not isinstance(mounts, list):
                continue
            for mount in mounts:
                if not isinstance(mount, dict):
                    continue
                propagation = mount.get("mountPropagation")
                if isinstance(propagation, str) and propagation.lower() == "bidirectional":
                    sc = container.setdefault("securityContext", {})
                    if not isinstance(sc, dict):
                        sc = {}
                        container["securityContext"] = sc
                    if sc.get("privileged") is True:
                        continue
                    sc["privileged"] = True
                    container_name = container.get("name", "<unnamed>")
                    notes.append(
                        f"Set securityContext.privileged=true for container "
                        f"{container_name} ({container_type}) in doc #{doc_index} due to Bidirectional mountPropagation."
                    )
                    break
    return notes


def inject_nfs_defaults(
    doc: Dict[str, Any],
    doc_index: int,
) -> List[str]:
    notes: List[str] = []
    for pod_spec, _ in iter_pod_specs(doc):
        volumes = pod_spec.get("volumes") or []
        if not isinstance(volumes, list):
            continue
        for volume in volumes:
            if not isinstance(volume, dict):
                continue
            nfs = volume.get("nfs")
            if isinstance(nfs, dict) and not nfs.get("server"):
                nfs["server"] = DEFAULT_NFS_SERVER
                volume_name = volume.get("name", "<unnamed>")
                notes.append(
                    f"Injected default NFS server '{DEFAULT_NFS_SERVER}' for volume {volume_name} in doc #{doc_index}."
                )
    return notes


def ensure_placeholder_images(
    doc: Dict[str, Any],
    doc_index: int,
) -> List[str]:
    notes: List[str] = []
    for pod_spec, _ in iter_pod_specs(doc):
        for container, container_type in iter_containers(pod_spec):
            image = container.get("image")
            if not image:
                container["image"] = PLACEHOLDER_IMAGE
                container_name = container.get("name", "<unnamed>")
                notes.append(
                    f"Injected placeholder image '{PLACEHOLDER_IMAGE}' for container "
                    f"{container_name} ({container_type}) in doc #{doc_index}."
                )
        if doc.get("kind") in {"CronJob", "Job"} and not pod_spec.get("restartPolicy"):
            pod_spec["restartPolicy"] = "OnFailure"
            notes.append(
                f"Set restartPolicy=OnFailure for doc #{doc_index} ({doc.get('kind')}) to satisfy workload requirements."
            )
    return notes


def collect_service_accounts(doc: Dict[str, Any]) -> List[Tuple[Optional[str], str]]:
    accounts: Set[Tuple[Optional[str], str]] = set()
    if not isinstance(doc, dict):
        return []
    metadata = doc.get("metadata", {})
    doc_namespace: Optional[str] = None
    if isinstance(metadata, dict):
        ns = metadata.get("namespace")
        if isinstance(ns, str) and ns:
            doc_namespace = ns
    for pod_spec, _ in iter_pod_specs(doc):
        sa = pod_spec.get("serviceAccountName") or pod_spec.get("serviceAccount")
        if isinstance(sa, str) and sa and sa != "default":
            accounts.add((doc_namespace, sa))
    return sorted(accounts)


def ensure_named_service_accounts(
    kubectl: str,
    fallback_namespace: Optional[str],
    service_accounts: Sequence[Tuple[Optional[str], str]],
) -> List[str]:
    warnings: List[str] = []
    for doc_namespace, name in service_accounts:
        target_namespace = doc_namespace or fallback_namespace
        if not target_namespace or not name:
            continue
        sa_yaml = f"""apiVersion: v1
kind: ServiceAccount
metadata:
  name: {name}
  namespace: {target_namespace}
"""
        proc = run_kubectl(kubectl, ["apply", "-f", "-"], input_data=sa_yaml)
        if proc.returncode != 0:
            stderr = proc.stderr.decode()
            if "AlreadyExists" in stderr or "unchanged" in stderr:
                continue
            warnings.append(
                f"Failed to ensure service account {name} in {target_namespace}: {stderr.strip()}"
            )
    return warnings


def deterministic_suffix(manifest_path: pathlib.Path, doc_index: int) -> str:
    seed = f"{manifest_path.as_posix()}::{doc_index}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return digest[:8]


def ensure_resource_name(
    doc: Dict[str, Any],
    manifest_path: pathlib.Path,
    doc_index: int,
) -> List[str]:
    notes: List[str] = []
    metadata = doc.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        doc["metadata"] = metadata

    generate_name = metadata.get("generateName")
    name = metadata.get("name")
    if generate_name:
        suffix = deterministic_suffix(manifest_path, doc_index)
        base = generate_name
        max_len = 63
        if len(base) + len(suffix) > max_len:
            base = base[: max_len - len(suffix)]
        metadata["name"] = f"{base}{suffix}"
        metadata.pop("generateName", None)
        notes.append(
            f"Converted generateName '{generate_name}' to deterministic name '{metadata['name']}' in doc #{doc_index}."
        )
    elif not name:
        kind = doc.get("kind", "resource").lower()
        suffix = deterministic_suffix(manifest_path, doc_index)
        candidate = f"{kind}-{suffix}"
        metadata["name"] = candidate[:63]
        notes.append(
            f"Assigned generated resource name '{metadata['name']}' in doc #{doc_index}."
        )
    return notes


def preprocess_manifest_docs(
    docs: Sequence[Any],
    manifest_path: pathlib.Path,
) -> Tuple[List[Any], List[str], List[Tuple[Optional[str], str]]]:
    updated_docs = copy.deepcopy(list(docs))
    notes: List[str] = []
    service_accounts: Set[Tuple[Optional[str], str]] = set()
    for idx, doc in enumerate(updated_docs, start=1):
        if not isinstance(doc, dict):
            continue
        notes.extend(ensure_resource_name(doc, manifest_path, idx))
        notes.extend(enforce_privileged_mounts(doc, manifest_path, idx))
        notes.extend(inject_nfs_defaults(doc, idx))
        notes.extend(ensure_placeholder_images(doc, idx))
        service_accounts.update(collect_service_accounts(doc))
    return updated_docs, notes, sorted(service_accounts)
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare server-side dry-run vs live apply results for manifests."
    )
    parser.add_argument(
        "--manifests",
        type=pathlib.Path,
        required=True,
        help="Directory containing manifests to evaluate.",
    )
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--summary", type=pathlib.Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument(
        "--namespace-prefix",
        type=str,
        default="live-eval",
        help="Prefix for temporary namespaces (namespace = prefix-<rand>).",
    )
    parser.add_argument(
        "--kubectl",
        type=str,
        default="kubectl",
        help="Path to kubectl binary.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Generate deterministic pseudo-results instead of talking to a cluster.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Random seed for namespace suffixes and simulation.",
    )
    return parser.parse_args()


def load_manifests(manifest_dir: pathlib.Path) -> List[pathlib.Path]:
    if not manifest_dir.exists():
        raise FileNotFoundError(f"Manifest directory {manifest_dir} not found.")
    manifests = [p for p in manifest_dir.glob("**/*.yaml") if p.is_file()]
    if not manifests:
        raise FileNotFoundError(f"No manifests found in {manifest_dir}")
    return sorted(manifests)


def random_namespace(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}-{suffix}"


def upgrade_api_versions(manifest_yaml: str) -> str:
    """
    Upgrade deprecated API versions to current versions.
    
    This fixes corpus quality issues where manifests use deprecated APIs.
    """
    api_migrations = {
        "apiVersion: batch/v1beta1": "apiVersion: batch/v1",
        "apiVersion: extensions/v1beta1": "apiVersion: apps/v1",
        "apiVersion: apps/v1beta1": "apiVersion: apps/v1",
        "apiVersion: apps/v1beta2": "apiVersion: apps/v1",
    }
    
    for old_api, new_api in api_migrations.items():
        manifest_yaml = manifest_yaml.replace(old_api, new_api)
    
    return manifest_yaml


def resolve_namespace(docs: Sequence[Any], namespace_prefix: str) -> Tuple[str, bool]:
    namespaces: List[str] = []
    for doc in docs:
        if isinstance(doc, dict):
            ns = doc.get("metadata", {}).get("namespace")
            if ns:
                namespaces.append(ns)
    if namespaces:
        return namespaces[0], False
    return random_namespace(namespace_prefix), True


def run_kubectl(
    kubectl: str,
    args: List[str],
    *,
    input_data: Optional[str] = None,
) -> subprocess.CompletedProcess:
    cmd = [kubectl] + args
    return subprocess.run(
        cmd,
        input=input_data.encode("utf-8") if input_data is not None else None,
        capture_output=True,
        check=False,
    )


def simulate_result(manifest_path: pathlib.Path) -> EvaluationRecord:
    seed = hash(manifest_path.as_posix()) & 0xFFFFFFFF
    rng = random.Random(seed)
    dry_pass = rng.random() > 0.08
    live_pass = dry_pass and rng.random() > 0.03
    rollback = dry_pass and not live_pass
    error = None
    if not dry_pass:
        error = "SimulatedDryRunFailure"
    elif not live_pass:
        error = "SimulatedApplyFailure"
    return EvaluationRecord(
        manifest_path=str(manifest_path),
        namespace=None,
        dry_run_pass=dry_pass,
        live_apply_pass=live_pass,
        rollback_triggered=rollback,
        error_class=error,
        notes="Simulated result (no kubectl executed).",
    )


def evaluate_manifest(
    bundle: ManifestBundle,
    namespace_prefix: str,
    kubectl: str,
    namespace_manager: NamespaceManager,
) -> EvaluationRecord:
    preprocess_docs, preprocess_notes, required_service_accounts = preprocess_manifest_docs(
        bundle.docs, bundle.path
    )
    manifest_yaml = dump_yaml_documents(preprocess_docs)

    target_namespace, ephemeral = resolve_namespace(preprocess_docs, namespace_prefix)
    _, namespace_warnings, namespace_error = namespace_manager.ensure(
        target_namespace,
        ephemeral,
    )
    notes: List[str] = list(preprocess_notes)
    notes.extend(namespace_warnings)

    dry_run_proc = None
    dry_pass = None
    live_stdout = None
    live_stderr = None
    live_pass = None
    rollback = None
    error_class = None

    if namespace_error:
        error_class = "NamespaceCreationFailure"
        notes.append(namespace_error)
        return EvaluationRecord(
            manifest_path=str(bundle.path),
            namespace=target_namespace,
            dry_run_pass=None,
            live_apply_pass=None,
            rollback_triggered=None,
            error_class=error_class,
            notes="; ".join(notes) if notes else None,
            kubectl_stdout=None,
            kubectl_stderr=None,
        )

    if required_service_accounts:
        sa_warnings = ensure_named_service_accounts(
            kubectl, target_namespace, required_service_accounts
        )
        notes.extend(sa_warnings)

    dry_args = ["apply", "--dry-run=server", "-f", "-"]
    if ephemeral:
        dry_args.extend(["-n", target_namespace])
    dry_run_proc = run_kubectl(kubectl, dry_args, input_data=manifest_yaml)
    dry_pass = dry_run_proc.returncode == 0
    if not dry_pass:
        error_class = "DryRunFailure"

    try:
        if dry_pass:
            apply_args = ["apply", "-f", "-"]
            if ephemeral:
                apply_args.extend(["-n", target_namespace])
            apply_proc = run_kubectl(kubectl, apply_args, input_data=manifest_yaml)
            live_stdout = apply_proc.stdout.decode()
            live_stderr = apply_proc.stderr.decode()
            live_pass = apply_proc.returncode == 0
            if not live_pass:
                error_class = "LiveApplyFailure"
                rollback = True
                if live_stderr:
                    notes.append(live_stderr.strip())
            else:
                rollback = False
        else:
            live_pass = None
            rollback = None
    finally:
        cleanup_notes = namespace_manager.release(target_namespace, ephemeral)
        notes.extend(cleanup_notes)

    return EvaluationRecord(
        manifest_path=str(bundle.path),
        namespace=target_namespace,
        dry_run_pass=dry_pass,
        live_apply_pass=live_pass,
        rollback_triggered=rollback,
        error_class=error_class,
        notes="; ".join(notes) if notes else None,
        kubectl_stdout=live_stdout or (dry_run_proc.stdout.decode() if dry_run_proc else None),
        kubectl_stderr=live_stderr or (dry_run_proc.stderr.decode() if dry_run_proc else None),
    )


def write_summary(path: pathlib.Path, records: List[EvaluationRecord]) -> None:
    total = len(records)
    dry_pass = sum(1 for r in records if r.dry_run_pass)
    live_pass = sum(1 for r in records if r.live_apply_pass)
    failures = sum(1 for r in records if r.live_apply_pass is False)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        fh.write("generated,manifests,dry_run_pass,live_apply_pass,live_failures\n")
        fh.write(f"{generated},{total},{dry_pass},{live_pass},{failures}\n")


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    manifests = load_manifests(args.manifests)
    records: List[EvaluationRecord] = []

    if args.simulate:
        for manifest in manifests:
            records.append(simulate_result(manifest))
    else:
        filter_rules = load_filter_rules(FILTER_CONFIG_PATH)
        bundles: List[ManifestBundle] = []
        for manifest in manifests:
            raw_yaml = manifest.read_text()
            docs = load_yaml_documents(upgrade_api_versions(raw_yaml))
            priority = calculate_manifest_priority(docs)
            filter_reason = manifest_matches_filter(manifest, docs, filter_rules)
            bundles.append(
                ManifestBundle(
                    path=manifest,
                    docs=docs,
                    priority=priority,
                    filter_reason=filter_reason,
                )
            )

        bundles.sort(key=lambda b: (b.priority, b.path.as_posix()))

        namespace_usage = collect_namespace_usage(bundles)
        namespace_manager = NamespaceManager(args.kubectl, namespace_usage)

        crd_definitions = collect_crd_definitions(bundles)
        installed_crds: List[str] = []

        try:
            if crd_definitions:
                installed_crds = install_crds(args.kubectl, crd_definitions)

            for bundle in bundles:
                if bundle.filter_reason:
                    logging.info(
                        "Skipping %s due to filter: %s",
                        bundle.path,
                        bundle.filter_reason,
                    )
                    records.append(
                        EvaluationRecord(
                            manifest_path=str(bundle.path),
                            namespace=None,
                            dry_run_pass=None,
                            live_apply_pass=None,
                            rollback_triggered=None,
                            error_class=FILTERED_ERROR_CLASS,
                            notes=bundle.filter_reason,
                        )
                    )
                    continue

                record = evaluate_manifest(
                    bundle=bundle,
                    namespace_prefix=args.namespace_prefix,
                    kubectl=args.kubectl,
                    namespace_manager=namespace_manager,
                )
                records.append(record)
        finally:
            if installed_crds:
                uninstall_crds(args.kubectl, installed_crds)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump([record.to_dict() for record in records], fh, indent=2)

    if args.summary:
        write_summary(args.summary, records)


if __name__ == "__main__":
    sys.exit(main())
