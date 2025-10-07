from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import typer
import yaml


def _normalise_policy_id(policy: Optional[str]) -> str:
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
        "hostnetwork": "no_host_network",
        "host-network": "no_host_network",
        "hostpid": "no_host_pid",
        "host-pid": "no_host_pid",
        "hostipc": "no_host_ipc",
        "host-ipc": "no_host_ipc",
        "hostpath": "no_host_path",
        "host-path": "no_host_path",
        "hostpath-volume": "no_host_path",
        "disallow-hostpath": "no_host_path",
        "hostports": "no_host_ports",
        "host-port": "no_host_ports",
        "host-ports": "no_host_ports",
        "disallow-hostports": "no_host_ports",
        "run-as-user": "run_as_user",
        "check-runasuser": "run_as_user",
        "requires-runasuser": "run_as_user",
        "seccomp": "enforce_seccomp",
        "seccomp-profile": "enforce_seccomp",
        "requires-seccomp": "enforce_seccomp",
        "drop-capabilities": "drop_capabilities",
        "linux-capabilities": "drop_capabilities",
        "invalid-capabilities": "drop_capabilities",
        "cap-sys-admin": "drop_cap_sys_admin",
        "sys-admin-capability": "drop_cap_sys_admin",
    }
    return mapping.get(key, key)


def build(
    detections: Path = typer.Option(
        Path("data/detections.json"),
        "--detections",
        "-d",
        help="Path to detections JSON file.",
    ),
    out: Path = typer.Option(
        Path("data/risk.json"),
        "--out",
        "-o",
        help="Where to write risk JSON.",
    ),
    enable_trivy: bool = typer.Option(
        False,
        "--enable-trivy/--no-enable-trivy",
        help="Enable Trivy image scans to enrich risk (requires trivy in PATH).",
    ),
    trivy_cmd: str = typer.Option(
        "trivy",
        help="Trivy command name.",
    ),
    epss_csv: Optional[Path] = typer.Option(
        None,
        "--epss-csv",
        help="Optional FIRST EPSS CSV to join (expects CVE, EPSS score column).",
    ),
    kev_json: Optional[Path] = typer.Option(
        None,
        "--kev-json",
        help="Optional CISA KEV JSON to join (expects list with cveID fields).",
    ),
) -> None:
    records = _load_array(detections, "detections")
    id_to_images = _map_detection_to_images(records)
    epss_map = _load_epss_map(epss_csv) if epss_csv else {}
    kev_set = _load_kev_set(kev_json) if kev_json else set()

    image_vulns: Dict[str, Dict[str, Any]] = {}
    if enable_trivy:
        image_vulns = _scan_images_with_trivy(sorted({img for imgs in id_to_images.values() for img in imgs}), trivy_cmd)

    output: List[Dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        detection_id = str(record.get("id"))
        policy_id = _normalise_policy_id(record.get("policy_id"))
        images = id_to_images.get(detection_id, [])
        metrics = _compute_risk(policy_id, images, image_vulns, epss_map, kev_set)
        output.append({"id": detection_id, **metrics})

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    typer.echo(f"Wrote risk for {len(output)} item(s) to {out.resolve()}")


def _load_array(path: Path, kind: str) -> List[Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"{kind.title()} file not found: {path}") from exc
    if not isinstance(data, list):
        raise typer.BadParameter(f"{kind.title()} file must contain a JSON array")
    return data


def _extract_images_from_manifest(manifest_yaml: str) -> List[str]:
    images: List[str] = []
    try:
        documents = list(yaml.safe_load_all(manifest_yaml))
    except Exception:
        return images
    if not documents:
        return images
    obj = documents[0]
    def visit(spec_obj: Any) -> None:
        if not isinstance(spec_obj, dict):
            return
        raw_containers = spec_obj.get("containers")
        if isinstance(raw_containers, list):
            for c in raw_containers:
                if isinstance(c, dict):
                    image = c.get("image")
                    if isinstance(image, str):
                        images.append(image)
        template = spec_obj.get("template")
        if isinstance(template, dict):
            visit(template.get("spec"))
    if isinstance(obj, dict):
        visit(obj.get("spec"))
    return images


def _map_detection_to_images(records: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        det_id = str(record.get("id"))
        manifest_yaml = record.get("manifest_yaml")
        if isinstance(manifest_yaml, str):
            mapping[det_id] = _extract_images_from_manifest(manifest_yaml)
    return mapping


def _scan_images_with_trivy(images: List[str], trivy_cmd: str) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for image in images:
        try:
            completed = subprocess.run(
                [trivy_cmd, "image", "--quiet", "--format", "json", "--severity", "CRITICAL,HIGH,MEDIUM", image],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(completed.stdout) if completed.stdout else {}
        except FileNotFoundError:
            break
        except subprocess.CalledProcessError:
            data = {}
        except json.JSONDecodeError:
            data = {}
        results[image] = _summarize_trivy(data)
    return results


def _summarize_trivy(data: Dict[str, Any]) -> Dict[str, Any]:
    vulns = []
    if not isinstance(data, dict):
        return {"counts": {}, "cves": []}
    # Trivy JSON: Results[].Vulnerabilities[] with Severity and VulnerabilityID
    for res in data.get("Results", []) or []:
        for v in (res.get("Vulnerabilities") or []):
            if isinstance(v, dict):
                vulns.append({
                    "cve": v.get("VulnerabilityID"),
                    "severity": v.get("Severity"),
                })
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
    cves = []
    for v in vulns:
        sev = str(v.get("severity") or "").upper()
        if sev in counts:
            counts[sev] += 1
        cve = v.get("cve")
        if isinstance(cve, str):
            cves.append(cve)
    return {"counts": counts, "cves": cves}


def _load_epss_map(csv_path: Path) -> Dict[str, float]:
    mapping: Dict[str, float] = {}
    try:
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cve = row.get("CVE") or row.get("cve") or row.get("cve_id")
                score = row.get("EPSS") or row.get("epss") or row.get("score")
                if cve and score:
                    try:
                        mapping[str(cve).strip()] = float(score)
                    except ValueError:
                        continue
    except Exception:
        return {}
    return mapping


def _load_kev_set(json_path: Path) -> set:
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return set()
    kev: set = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cve = item.get("cveID") or item.get("cve_id")
                if isinstance(cve, str):
                    kev.add(cve)
    elif isinstance(data, dict):
        for item in data.get("vulnerabilities", []) or []:
            if isinstance(item, dict):
                cve = item.get("cveID") or item.get("cve_id")
                if isinstance(cve, str):
                    kev.add(cve)
    return kev


def _policy_defaults(policy_id: str) -> float:
    return {
        "no_privileged": 85.0,
        "no_latest_tag": 60.0,
        "run_as_non_root": 70.0,
        "no_host_path": 80.0,
        "no_host_ports": 65.0,
        "run_as_user": 72.0,
        "enforce_seccomp": 75.0,
        "drop_capabilities": 85.0,
        "drop_cap_sys_admin": 85.0,
    }.get(policy_id, 40.0)


def _compute_risk(
    policy_id: str,
    images: List[str],
    image_vulns: Dict[str, Dict[str, Any]],
    epss_map: Dict[str, float],
    kev_set: set,
) -> Dict[str, Any]:
    base = _policy_defaults(policy_id)
    total_score = 0.0
    max_epss = 0.0
    kev = False
    for image in images:
        summary = image_vulns.get(image, {})
        counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
        cves = summary.get("cves", []) if isinstance(summary, dict) else []
        total_score += counts.get("CRITICAL", 0) * 5.0
        total_score += counts.get("HIGH", 0) * 3.0
        total_score += counts.get("MEDIUM", 0) * 1.0
        for cve in cves:
            score = epss_map.get(cve, 0.0)
            if score > max_epss:
                max_epss = score
            if cve in kev_set:
                kev = True
    # Scale EPSS contribution into [0, 10]
    epss_bonus = min(10.0, 10.0 * max_epss)
    risk = min(100.0, base + total_score + epss_bonus + (10.0 if kev else 0.0))
    return {
        "risk": round(risk, 2),
        "probability": 0.9,
        "expected_time": 10.0,
        "wait": 0.0,
        "kev": kev,
        "explore": 0.0,
    }


if __name__ == "__main__":  # pragma: no cover
    typer.run(build)
