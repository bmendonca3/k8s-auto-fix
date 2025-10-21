#!/usr/bin/env python3
"""
Seed fixtures (namespaces, service accounts, stub volumes/configs) required for
webhook baselines to admit manifests.

Reads staged manifests (e.g., data/staged/kyverno_webhook_staged) and emits a
Kubernetes manifest that creates the missing namespaces and service accounts.
"""
from __future__ import annotations

import argparse
import yaml
from pathlib import Path
from typing import Dict, Set, Tuple

from collections import defaultdict

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed fixtures needed for webhook baselines.")
    parser.add_argument(
        "--staged-dir",
        type=Path,
        default=Path("data/staged/kyverno_webhook_staged"),
        help="Directory containing staged manifests from the baseline run.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/staged/fixtures.yaml"),
        help="Output manifest to apply (namespaces + service accounts).",
    )
    return parser.parse_args()


def gather_fixtures(
    staged_dir: Path,
) -> Tuple[Set[str], Dict[Tuple[str, str], Set[str]], Dict[Tuple[str, str], Set[str]], Dict[str, Tuple[str, Dict[str, str]]]]:
    namespaces: Set[str] = set()
    service_accounts: Dict[Tuple[str, str], Set[str]] = {}
    missing_volumes: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    volume_types: Dict[str, Tuple[str, Dict[str, str]]] = {}

    for path in staged_dir.glob("*.yaml"):
        docs = list(yaml.safe_load_all(path.read_text()))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            kind = doc.get("kind")
            metadata = doc.get("metadata") or {}
            namespace = metadata.get("namespace", "default")
            namespaces.add(namespace)
            if kind in {"Pod", "Deployment", "StatefulSet", "Job"}:
                service_account = None
                if kind == "Pod":
                    spec = doc.get("spec") or {}
                    service_account = spec.get("serviceAccountName") or spec.get("serviceAccount")
                else:
                    spec = doc.get("spec") or {}
                    template = spec.get("template", {})
                    pod_spec = template.get("spec") or {}
                    service_account = pod_spec.get("serviceAccountName") or pod_spec.get("serviceAccount")
                    containers = pod_spec.get("containers", []) or []
                    volumes = pod_spec.get("volumes", []) or []
                if service_account:
                    key = (namespace, service_account)
                    service_accounts.setdefault(key, set())
                    service_accounts[key].add(metadata.get("name", ""))
                if kind in {"Deployment", "StatefulSet"}:
                    mounts = set()
                    for container in containers:
                        for mnt in container.get("volumeMounts", []) or []:
                            name_mount = mnt.get("name")
                            if name_mount:
                                mounts.add(name_mount)
                    volume_by_name = {vol.get("name"): vol for vol in volumes if isinstance(vol, dict)}
                    for mount in mounts:
                        if mount not in volume_by_name:
                            missing_volumes[(namespace, metadata.get("name") or "")].add(mount)
                        else:
                            vol_entry = volume_by_name[mount]
                            vol_type = next((k for k in vol_entry.keys() if k not in {"name"}), "emptyDir")
                            volume_types.setdefault(mount, (namespace, {"type": vol_type}))[1]["type"] = vol_type
    return namespaces, service_accounts, missing_volumes, volume_types


def build_fixture_manifest(
    namespaces: Set[str],
    service_accounts: Dict[Tuple[str, str], Set[str]],
    volume_names: Set[str],
) -> str:
    docs = []
    default_ns = {"default", None, ""}
    for ns in sorted(namespaces):
        if ns in default_ns:
            continue
        docs.append(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": ns},
            }
        )
    for (namespace, sa), _ in sorted(service_accounts.items()):
        if not sa or sa == "default":
            continue
        docs.append(
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": sa, "namespace": namespace},
            }
        )
    # Generate emptyDir fallback for volumes (default namespace only)
    for name in sorted(volume_names):
        docs.append(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": f"fixture-{name}",
                    "namespace": "default",
                },
                "spec": {
                    "containers": [
                        {
                            "name": "fixture",
                            "image": "k8s.gcr.io/pause:3.9",
                            "volumeMounts": [
                                {
                                    "name": name,
                                    "mountPath": f"/mnt/{name}"
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": name,
                            "emptyDir": {},
                        }
                    ],
                },
            }
        )
    return yaml.safe_dump_all(docs, sort_keys=False)


def main() -> None:
    args = parse_args()
    namespaces, service_accounts, missing_volumes, volume_types = gather_fixtures(args.staged_dir)
    if missing_volumes:
        print("WARNING: Missing volumes detected; manual scaffolding required:")
        for (namespace, name), mounts in sorted(missing_volumes.items()):
            joined = ", ".join(sorted(mounts))
            print(f"  {namespace}/{name}: {joined}")
    manifest = build_fixture_manifest(namespaces, service_accounts, set(volume_types.keys()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(manifest, encoding="utf-8")
    print(f"Fixture manifest written to {args.out} (namespaces={len(namespaces)}, serviceAccounts={len(service_accounts)})")


if __name__ == "__main__":
    main()
