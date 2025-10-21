#!/usr/bin/env python3
"""
Polaris mutate/CLI fix baseline harness with optional simulation mode.

This script evaluates Fairwinds Polaris as an auto-fix baseline in two modes:

- simulate: derive deterministic acceptance numbers from detections only
- real: attempt to invoke the `polaris` CLI to mutate YAML, then pass results
        through the same verifier triad used by k8s-auto-fix

Outputs a CSV summary at data/baselines/polaris_baseline.csv with per-policy
acceptance counts and rates.

Notes:
- The real mode requires `polaris` to be installed and on PATH.
- Polaris CLI flags and subcommands vary by version. This runner tries a small
  set of common invocations and treats failures as non-acceptance for that item.
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
from typing import Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.common.policy_ids import normalise_policy_id
from src.detector.detector import Detector
from src.verifier.verifier import Verifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polaris mutate baseline runner.")
    parser.add_argument(
        "--detections",
        type=Path,
        default=Path("data/detections.json"),
        help="Detections JSON (used to locate manifests and policies).",
    )
    parser.add_argument(
        "--manifests-root",
        type=Path,
        default=Path("data/manifests"),
        help="Root for manifest lookup when detections embed relative paths.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/baselines/polaris_baseline.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--polaris",
        type=str,
        default="polaris",
        help="Polaris CLI binary name/path.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Skip CLI and derive deterministic numbers from detections.",
    )
    parser.add_argument(
        "--require-kubectl",
        action="store_true",
        help="Fail acceptance if server dry-run is unavailable.",
    )
    parser.add_argument(
        "--policies-dir",
        type=Path,
        default=Path("data/policies/kyverno"),
        help="Policies directory for rescans (detector).",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Preserve the staged manifest folder for inspection rather than deleting it.",
    )
    parser.add_argument(
        "--merge-config",
        action="store_true",
        help="Merge the provided config with Polaris defaults (CLI -m flag).",
    )
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Use the Polaris mutating webhook via kubectl server-side apply.",
    )
    parser.add_argument(
        "--kubectl",
        type=str,
        default="kubectl",
        help="Kubectl binary (used for webhook mode and schema checks).",
    )
    return parser.parse_args()


def load_detections(path: Path) -> List[Dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def upgrade_api_versions(manifest_yaml: str) -> str:
    """
    Upgrade deprecated API versions to current equivalents.

    This mirrors the upgrade logic used in live-cluster evaluation so that
    webhook dry-runs succeed even when the source manifest targets legacy
    APIs (e.g. CronJob batch/v1beta1).
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


def simulate(detections: List[Dict]) -> Dict[str, Tuple[int, int]]:
    """Return map policy_id -> (accepted, total) with deterministic acceptance.

    Simulation assumes Polaris performs well on resource requests/limits and
    non-root defaults, but is conservative on hostPath and capability drops.
    """
    totals: Dict[str, int] = {}
    for det in detections:
        policy = normalise_policy_id(det.get("policy_id", "unknown"))
        totals[policy] = totals.get(policy, 0) + 1

    accepted: Dict[str, int] = {}
    for policy, total in totals.items():
        rate = 0.0
        if policy in {"set_requests_limits", "run_as_non_root", "read_only_root_fs"}:
            rate = 0.78
        elif policy in {"no_host_path", "drop_capabilities", "drop_cap_sys_admin"}:
            rate = 0.55
        elif policy in {"no_host_ports", "run_as_user", "enforce_seccomp"}:
            rate = 0.70
        else:
            rate = 0.65
        accepted[policy] = int(total * rate)
    return {p: (accepted[p], totals[p]) for p in totals}


def _try_polaris_fix(polaris: str, manifest_path: Path) -> Optional[str]:
    """Attempt to run Polaris to mutate a manifest.

    Returns mutated YAML text on success, or None on failure.
    Tries a few known invocation patterns across Polaris versions.
    """
    invocations = [
        [polaris, "fix", "-f", str(manifest_path), "-o", "-"],  # hypothetical 'fix'
        [polaris, "audit", "-f", str(manifest_path), "--output-format", "json", "--fix"],
        [polaris, "audit", "-f", str(manifest_path), "--format", "json", "--fix"],
    ]
    for cmd in invocations:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return None
        if proc.returncode != 0:
            continue
        stdout = (proc.stdout or "").strip()
        if not stdout:
            continue
        # If JSON, try to extract mutated manifest if present.
        if stdout.startswith("{") or stdout.startswith("["):
            try:
                data = json.loads(stdout)
                # Heuristic: look for a top-level 'mutatedManifest' or similar key.
                if isinstance(data, dict):
                    for key in ("mutatedManifest", "fixedManifest", "patchedManifest"):
                        text = data.get(key)
                        if isinstance(text, str) and text.strip():
                            return text
                # Otherwise, no structured mutation provided.
            except Exception:
                pass
        else:
            # Assume YAML output on stdout.
            return stdout
    return None


def _read_manifest_from_detection(det: Dict, root: Path) -> Optional[str]:
    mpath = det.get("manifest_path")
    if not isinstance(mpath, str) or not mpath:
        inline = det.get("manifest_yaml")
        return inline if isinstance(inline, str) else None
    path = Path(mpath)
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(path)
        candidates.append(root / path)
    for candidate in candidates:
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    inline = det.get("manifest_yaml")
    return inline if isinstance(inline, str) else None


def _run_polaris_fix_folder(
    polaris: str,
    folder: Path,
    checks: List[str],
    *,
    template: bool = False,
    config: Optional[Path] = None,
    label: str = "polaris",
    extra_flags: Optional[List[str]] = None,
) -> Optional[subprocess.CompletedProcess[str]]:
    """Invoke `polaris fix` on a folder with specific checks.

    Polaris modifies files in place. This function is best-effort; errors are
    tolerated so we can still inspect outputs.
    """
    cmd: List[str] = [polaris, "fix", "--files-path", str(folder)]
    if extra_flags:
        cmd.extend(extra_flags)
    if config and config.exists():
        cmd.extend(["-c", str(config)])
    if checks:
        # Polaris expects comma-separated list for --checks strings
        cmd.extend(["--checks", ",".join(checks)])
    if template:
        cmd.append("--template")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        print(f"[polaris][{label}] executable '{polaris}' not found on PATH.", file=sys.stderr)
        return None
    message = f"[polaris][{label}] exit={proc.returncode}"
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        message += f" stdout={stdout!r}"
    if stderr:
        message += f" stderr={stderr!r}"
    print(message, file=sys.stderr)
    return proc


def run_real(
    detections: List[Dict],
    manifests_root: Path,
    polaris: str,
    require_kubectl: bool,
    policies_dir: Optional[Path],
    *,
    keep_temp: bool = False,
    merge_config: bool = False,
    kubectl: str = "kubectl",
) -> Dict[str, Tuple[int, int]]:
    """Run Polaris fix across a staged folder and triad-verify mutated manifests.

    This path uses `polaris fix --files-path <dir> --checks=all` to mutate IaC files,
    then reads the mutated YAML and applies our triad (policy re-check + safety +
    server-side dry-run). We count acceptance when the targeted policy is cleared
    and safety/schema gates pass.
    """
    import tempfile

    verifier = Verifier(kubectl_cmd=kubectl, require_kubectl=require_kubectl, policies_dir=policies_dir)
    detector = Detector(policies_dir=policies_dir)

    # Stage manifests to a temp directory keyed by detection id
    tmpdir = Path(tempfile.mkdtemp(prefix="polaris_fix_"))
    id_to_path: Dict[str, Path] = {}
    id_to_policy: Dict[str, str] = {}
    totals: Dict[str, int] = {}

    for det in detections:
        det_id = str(det.get("id") or "").strip()
        policy = normalise_policy_id(det.get("policy_id", "unknown"))
        totals[policy] = totals.get(policy, 0) + 1
        text = _read_manifest_from_detection(det, manifests_root)
        if not det_id or not text:
            continue
        text = upgrade_api_versions(text)
        out_path = tmpdir / f"{det_id}.yaml"
        out_path.write_text(text, encoding="utf-8")
        id_to_path[det_id] = out_path
        id_to_policy[det_id] = policy

    # Run Polaris fix on the folder with targeted checks first, then fallback to all
    targeted_checks = [
        # Security posture
        "runAsRootAllowed",
        "readOnlyRootFilesystem",
        "privileged",
        "hostPathVolume",
        "hostPortSet",
        # Resource requests/limits
        "cpuRequestsMissing",
        "memoryRequestsMissing",
        "cpuLimitsMissing",
        "memoryLimitsMissing",
        # Image tag hygiene
        "imageTag",
    ]
    # Try with our repo config first
    config_path = (Path.cwd() / "configs" / "polaris.yaml")
    if merge_config:
        extra_flags = ["--merge-config"]
    else:
        extra_flags = []

    _run_polaris_fix_folder(
        polaris,
        tmpdir,
        targeted_checks,
        template=True,
        config=config_path,
        label="targeted",
        extra_flags=extra_flags,
    )
    # Fallback pass with all checks (in case targeted list missed fixable rules)
    _run_polaris_fix_folder(
        polaris,
        tmpdir,
        checks=["all"],
        template=True,
        config=config_path,
        label="all",
        extra_flags=extra_flags,
    )

    accepted: Dict[str, int] = {}
    # Read back mutated files and triad-verify
    for det_id, path in id_to_path.items():
        try:
            mutated_yaml = path.read_text(encoding="utf-8")
        except OSError:
            continue
        policy = id_to_policy.get(det_id, "unknown")
        if not mutated_yaml.strip():
            continue
        ok_policy = _rescan_policy_cleared(detector, mutated_yaml, policy)
        try:
            obj = yaml.safe_load(mutated_yaml)
        except Exception:
            obj = None
        ok_safety = verifier._check_safety(obj if isinstance(obj, dict) else {}, policy)[0]  # type: ignore[attr-defined]
        ok_schema = verifier._kubectl_dry_run(mutated_yaml)[0]
        if ok_policy and ok_safety and ok_schema:
            accepted[policy] = accepted.get(policy, 0) + 1

    if keep_temp:
        print(f"[polaris] staged manifests preserved at {tmpdir}", file=sys.stderr)
    else:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return {p: (accepted.get(p, 0), totals.get(p, 0)) for p in totals}


def _kubectl_apply_dry_run(kubectl: str, manifest: Path) -> Optional[str]:
    backoff = 2.0
    errors: List[str] = []
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
            str(manifest),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            print(f"[webhook] kubectl binary '{kubectl}' not found.", file=sys.stderr)
            return None
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode == 0 and stdout:
            if stderr:
                print(f"[webhook] kubectl dry-run stderr={stderr!r}", file=sys.stderr)
            return stdout

        if proc.returncode == 0 and not stdout:
            return None

        message = f"[webhook] kubectl dry-run failed (exit={proc.returncode})"
        if stderr:
            message += f" stderr={stderr!r}"
            errors.append(stderr)
        print(message, file=sys.stderr)

        retryable = False
        if stderr:
            lowered = stderr.lower()
            retryable = any(
                token in lowered
                for token in (
                    "tls handshake timeout",
                    "context deadline exceeded",
                    "i/o timeout",
                    "the server is currently unable",
                )
            )

        if attempt < 4 and retryable:
            sleep_for = backoff * (attempt + 1)
            print(f"[webhook] retrying dry-run in {sleep_for:.1f}s", file=sys.stderr)
            time.sleep(sleep_for)
            continue
        break

    if errors:
        print(f"[webhook] giving up after retries; last error: {errors[-1]}", file=sys.stderr)
    return None


def run_webhook(
    detections: List[Dict],
    manifests_root: Path,
    kubectl: str,
    require_kubectl: bool,
    policies_dir: Optional[Path],
    *,
    keep_temp: bool = False,
) -> Dict[str, Tuple[int, int]]:
    verifier = Verifier(kubectl_cmd=kubectl, require_kubectl=require_kubectl, policies_dir=policies_dir)
    detector = Detector(policies_dir=policies_dir)

    staged_dir = Path(tempfile.mkdtemp(prefix="polaris_webhook_"))
    totals: Dict[str, int] = {}
    accepted: Dict[str, int] = {}

    for det in detections:
        det_id = str(det.get("id") or "").strip()
        policy = normalise_policy_id(det.get("policy_id", "unknown"))
        totals[policy] = totals.get(policy, 0) + 1
        manifest_text = _read_manifest_from_detection(det, manifests_root)
        if not det_id or not manifest_text:
            continue
        manifest_text = upgrade_api_versions(manifest_text)
        staged_path = staged_dir / f"{det_id}.yaml"
        staged_path.write_text(manifest_text, encoding="utf-8")

        mutated_yaml = _kubectl_apply_dry_run(kubectl, staged_path)
        if not mutated_yaml:
            continue

        # Overwrite staged file with mutated content for later inspection
        staged_path.write_text(mutated_yaml, encoding="utf-8")

        ok_policy = _rescan_policy_cleared(detector, mutated_yaml, policy)

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

    if keep_temp:
        print(f"[webhook] staged manifests preserved at {staged_dir}", file=sys.stderr)
    else:
        shutil.rmtree(staged_dir, ignore_errors=True)

    return {p: (accepted.get(p, 0), totals.get(p, 0)) for p in totals}


def _rescan_policy_cleared(detector: Detector, patched_yaml: str, policy: str) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=True) as tmp:
        tmp.write(patched_yaml)
        tmp.flush()
        results = detector.detect([Path(tmp.name)])
        target = normalise_policy_id(policy)
        for r in results:
            rule = (r.rule or "").strip().lower() if r.rule else ""
            if normalise_policy_id(rule) == target:
                return False
        return True


def write_csv(summary: Dict[str, Tuple[int, int]], out: Path) -> None:
    rows = []
    for policy, (acc, tot) in sorted(summary.items()):
        rate = (float(acc) / float(tot)) if tot else 0.0
        rows.append({"policy_id": policy, "polaris_fixes": acc, "detections": tot, "acceptance_rate": rate})
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["policy_id", "polaris_fixes", "detections", "acceptance_rate"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    dets = load_detections(args.detections)
    if args.simulate:
        summary = simulate(dets)
    elif args.webhook:
        summary = run_webhook(
            dets,
            args.manifests_root,
            args.kubectl,
            args.require_kubectl,
            args.policies_dir,
            keep_temp=args.keep_temp,
        )
    else:
        summary = run_real(
            dets,
            args.manifests_root,
            args.polaris,
            args.require_kubectl,
            args.policies_dir,
            keep_temp=args.keep_temp,
            merge_config=args.merge_config,
            kubectl=args.kubectl,
        )
    write_csv(summary, args.output)


if __name__ == "__main__":
    main()
