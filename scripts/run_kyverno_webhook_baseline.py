#!/usr/bin/env python3
"""
Kyverno mutating webhook baseline (triad-verified).

This runner assumes Kyverno is installed in-cluster and that the mutation rules
from `policies/kyverno-mutating.yaml` are applied. It stages the selected
detections, submits each manifest through `kubectl create --dry-run=server -o yaml`,
and then triad-verifies the mutated output using the same detector and verifier
stack as k8s-auto-fix.

Outputs a CSV mirroring the other baselines plus optional staging of mutated YAML.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.common.policy_ids import normalise_policy_id
from src.detector.detector import Detector
from src.verifier.verifier import Verifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kyverno mutating webhook baseline")
    parser.add_argument(
        "--detections",
        type=Path,
        default=Path("tmp/detections_polaris_500.json"),
        help="Detections JSON to replay (defaults to the 500-manifest slice).",
    )
    parser.add_argument(
        "--manifests-root",
        type=Path,
        default=Path("data/manifests"),
        help="Manifest root when detections reference relative paths.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/baselines/kyverno_baseline_webhook.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--kubectl",
        type=str,
        default="kubectl",
        help="Kubectl binary.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Preserve staged manifests for inspection.",
    )
    parser.add_argument(
        "--require-kubectl",
        action="store_true",
        help="Treat kubectl failures as fatal (default: tolerate).",
    )
    return parser.parse_args()


def load_detections(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def upgrade_api_versions(manifest_yaml: str) -> str:
    """Upgrade deprecated apiVersions to help admission succeed."""
    migrations = {
        "apiVersion: batch/v1beta1": "apiVersion: batch/v1",
        "apiVersion: extensions/v1beta1": "apiVersion: apps/v1",
        "apiVersion: apps/v1beta1": "apiVersion: apps/v1",
        "apiVersion: apps/v1beta2": "apiVersion: apps/v1",
    }
    for old, new in migrations.items():
        manifest_yaml = manifest_yaml.replace(old, new)
    return manifest_yaml


def _ensure_volumes(doc: Dict) -> Dict:
    kind = doc.get("kind")
    spec = doc.get("spec") or {}

    def _normalise_mounts(containers: List[Dict[str, Any]]) -> None:
        for container in containers or []:
            mounts = container.get("volumeMounts") or []
            if not isinstance(mounts, list):
                continue
            for mount in mounts:
                if isinstance(mount, dict):
                    mount.pop("mountPropagation", None)

    if kind in {"Deployment", "StatefulSet", "DaemonSet"}:
        template = spec.get("template", {}) or {}
        pod_spec = template.get("spec") or {}
        containers = pod_spec.get("containers", []) or []
        volumes = pod_spec.get("volumes", []) or []
        volume_names = {vol.get("name") for vol in volumes if isinstance(vol, dict)}
        normalized_vols = []
        for vol in volumes:
            if isinstance(vol, dict):
                normalized_vols.append({"name": vol.get("name"), "emptyDir": {}})
            else:
                normalized_vols.append(vol)
        volumes = normalized_vols
        volume_names = {vol.get("name") for vol in volumes if isinstance(vol, dict)}
        for container in containers:
            for mount in container.get("volumeMounts", []) or []:
                name = mount.get("name")
                if name and name not in volume_names:
                    volumes.append({"name": name, "emptyDir": {}})
                    volume_names.add(name)
        _normalise_mounts(containers)
        _normalise_mounts(pod_spec.get("initContainers", []) or [])
        pod_spec["volumes"] = volumes
        template["spec"] = pod_spec
        spec["template"] = template
        doc["spec"] = spec
    elif kind == "Pod":
        pod_spec = spec
        containers = pod_spec.get("containers", []) or []
        volumes = pod_spec.get("volumes", []) or []
        normalized_vols = []
        for vol in volumes:
            if isinstance(vol, dict):
                normalized_vols.append({"name": vol.get("name"), "emptyDir": {}})
            else:
                normalized_vols.append(vol)
        volumes = normalized_vols
        volume_names = {vol.get("name") for vol in volumes if isinstance(vol, dict)}
        for container in containers:
            for mount in container.get("volumeMounts", []) or []:
                name = mount.get("name")
                if name and name not in volume_names:
                    volumes.append({"name": name, "emptyDir": {}})
                    volume_names.add(name)
        _normalise_mounts(containers)
        _normalise_mounts(pod_spec.get("initContainers", []) or [])
        pod_spec["volumes"] = volumes
        doc["spec"] = pod_spec
    if kind == "Job":
        template = spec.get("template", {}) or {}
        pod_spec = template.get("spec") or {}
        if isinstance(pod_spec, dict):
            if not pod_spec.get("restartPolicy"):
                pod_spec["restartPolicy"] = "OnFailure"
            _normalise_mounts(pod_spec.get("containers", []) or [])
            _normalise_mounts(pod_spec.get("initContainers", []) or [])
        template["spec"] = pod_spec
        spec["template"] = template
        doc["spec"] = spec
    elif kind == "CronJob":
        if not isinstance(spec, dict):
            spec = {}
        if not spec.get("schedule"):
            spec["schedule"] = "* * * * *"
        job_template_raw = spec.get("jobTemplate") or {}
        job_template = job_template_raw if isinstance(job_template_raw, dict) else {}
        template_from_deprecated = job_template.get("template")
        job_spec_raw = job_template.get("spec") or {}
        job_spec = job_spec_raw if isinstance(job_spec_raw, dict) else {}
        if isinstance(template_from_deprecated, dict):
            template = template_from_deprecated
        else:
            template = job_spec.get("template") or {}
            if not isinstance(template, dict):
                template = {}
        pod_spec = template.get("spec") or {}
        if isinstance(pod_spec, dict):
            if not pod_spec.get("restartPolicy"):
                pod_spec["restartPolicy"] = "OnFailure"
            _normalise_mounts(pod_spec.get("containers", []) or [])
            _normalise_mounts(pod_spec.get("initContainers", []) or [])
        template["spec"] = pod_spec
        job_spec["template"] = template
        job_template["spec"] = job_spec
        job_template.pop("template", None)
        spec["jobTemplate"] = job_template
        doc["spec"] = spec
    return doc


def preprocess_manifest(manifest_yaml: str) -> str:
    docs = list(yaml.safe_load_all(manifest_yaml))
    patched_docs = []
    for doc in docs:
        if isinstance(doc, dict):
            doc = _ensure_volumes(doc)
        patched_docs.append(doc)
    return yaml.safe_dump_all(patched_docs, sort_keys=False)


def _kubectl_dry_run(kubectl: str, manifest_path: Path) -> Optional[str]:
    """Return mutated YAML from server-side dry-run or None on failure."""
    backoff = 2.0
    for attempt in range(5):
        cmd = [
            kubectl,
            "create",
            "--dry-run=server",
            "-o",
            "yaml",
            "--request-timeout=180s",
            "--validate=false",
            "-f",
            str(manifest_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode == 0 and stdout:
            if stderr:
                print(f"[kyverno-webhook] kubectl dry-run stderr={stderr!r}", file=sys.stderr)
            return stdout
        if proc.returncode != 0:
            retryable = any(
                token in stderr.lower()
                for token in (
                    "tls handshake timeout",
                    "context deadline exceeded",
                    "i/o timeout",
                    "the server is currently unable",
                )
            )
            msg = f"[kyverno-webhook] dry-run failed (exit={proc.returncode})"
            if stderr:
                msg += f" stderr={stderr!r}"
            print(msg, file=sys.stderr)
            if retryable and attempt < 4:
                sleep_for = backoff * (attempt + 1)
                print(f"[kyverno-webhook] retrying in {sleep_for:.1f}s", file=sys.stderr)
                time.sleep(sleep_for)
                continue
        break
    return None


def run_webhook(
    detections: List[Dict],
    manifests_root: Path,
    kubectl: str,
    require_kubectl: bool,
    *,
    keep_temp: bool = False,
) -> Tuple[Dict[str, Tuple[int, int]], Path]:
    detector = Detector()
    verifier = Verifier(kubectl_cmd=kubectl, require_kubectl=require_kubectl)

    staged_dir = Path(tempfile.mkdtemp(prefix="kyverno_webhook_"))
    totals: Dict[str, int] = {}
    accepted: Dict[str, int] = {}

    for det in detections:
        policy = normalise_policy_id(det.get("policy_id", "unknown"))
        totals[policy] = totals.get(policy, 0) + 1
        manifest_yaml = det.get("manifest_yaml")
        path = det.get("manifest_path")
        if isinstance(path, str) and path:
            mpath = Path(path)
            if not mpath.is_absolute():
                mpath = manifests_root / mpath
            try:
                manifest_yaml = mpath.read_text(encoding="utf-8")
            except OSError:
                pass
        if not isinstance(manifest_yaml, str) or not manifest_yaml.strip():
            continue
        manifest_yaml = preprocess_manifest(upgrade_api_versions(manifest_yaml))
        staged_path = staged_dir / f"{det.get('id') or len(totals)}.yaml"
        staged_path.write_text(manifest_yaml, encoding="utf-8")

        mutated_yaml = _kubectl_dry_run(kubectl, staged_path)
        if not mutated_yaml:
            continue
        staged_path.write_text(mutated_yaml, encoding="utf-8")

        if not mutated_yaml.strip():
            continue

        ok_policy = _rescan_policy(detector, mutated_yaml, policy)
        try:
            docs = [doc for doc in yaml.safe_load_all(mutated_yaml) if isinstance(doc, dict)]
            primary_obj = docs[0] if docs else {}
        except Exception:
            primary_obj = {}
        ok_safety = verifier._check_safety(primary_obj if isinstance(primary_obj, dict) else {}, policy)[0]  # type: ignore[attr-defined]
        if require_kubectl:
            ok_schema = verifier._kubectl_dry_run(mutated_yaml)[0]
        else:
            ok_schema = True
        if ok_policy and ok_safety and ok_schema:
            accepted[policy] = accepted.get(policy, 0) + 1

    if not keep_temp:
        shutil.rmtree(staged_dir, ignore_errors=True)
    else:
        print(f"[kyverno-webhook] staged manifests preserved at {staged_dir}", file=sys.stderr)

    summary = {p: (accepted.get(p, 0), totals.get(p, 0)) for p in totals}
    return summary, staged_dir


def _rescan_policy(detector: Detector, mutated_yaml: str, policy: str) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=True) as tmp:
        tmp.write(mutated_yaml)
        tmp.flush()
        results = detector.detect([Path(tmp.name)])
    target = normalise_policy_id(policy)
    for res in results:
        rule = (res.rule or "").strip().lower() if res.rule else ""
        if normalise_policy_id(rule) == target:
            return False
    return True


def write_csv(summary: Dict[str, Tuple[int, int]], out_path: Path) -> None:
    rows = []
    for policy, (acc, tot) in sorted(summary.items()):
        rate = (float(acc) / float(tot)) if tot else 0.0
        rows.append(
            {
                "policy_id": policy,
                "kyverno_webhook_accept": acc,
                "detections": tot,
                "acceptance_rate": rate,
            }
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["policy_id", "kyverno_webhook_accept", "detections", "acceptance_rate"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    detections = load_detections(args.detections)
    summary, staged_dir = run_webhook(
        detections,
        args.manifests_root,
        args.kubectl,
        args.require_kubectl,
        keep_temp=args.keep_temp,
    )
    write_csv(summary, args.output)
    if not args.keep_temp:
        print(f"[kyverno-webhook] summary written to {args.output}")
    else:
        print(f"[kyverno-webhook] summary written to {args.output}; staged at {staged_dir}")


if __name__ == "__main__":
    main()
