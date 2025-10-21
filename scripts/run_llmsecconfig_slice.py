#!/usr/bin/env python3
"""
LLMSecConfig-style slice runner.

Runs a matched slice of detections through an LLMSecConfig-inspired prompting
template using the existing ModelClient, then verifies with the triad gates.

Outputs CSV with acceptance and latency per policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.proposer.model_client import ModelClient, ClientOptions
from src.verifier.verifier import Verifier
from src.common.policy_ids import normalise_policy_id


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LLMSecConfig-style evaluation slice")
    p.add_argument("--detections", type=Path, default=Path("data/detections.json"))
    p.add_argument("--out", type=Path, default=Path("data/baselines/llmsecconfig_slice.csv"))
    p.add_argument("--limit", type=int, default=500, help="Max detections to evaluate")
    p.add_argument("--endpoint", type=str, default="https://api.openai.com/v1/chat/completions")
    p.add_argument("--model", type=str, default="gpt-4o-mini")
    p.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--retries", type=int, default=1)
    p.add_argument("--require-kubectl", action="store_true")
    return p.parse_args()


def build_prompt(manifest_yaml: str, policy_id: str, violation_text: str) -> str:
    # LLMSecConfig-inspired instructions: structured, explicit, and conservative
    examples = [
        "Example (run_as_non_root): [ {\"op\": \"add\", \"path\": \"/spec/containers/0/securityContext/runAsNonRoot\", \"value\": true } ]",
        "Example (read_only_root_fs): [ {\"op\": \"add\", \"path\": \"/spec/containers/0/securityContext/readOnlyRootFilesystem\", \"value\": true } ]",
        "Example (label key with '/'): remove app.kubernetes.io/component => path must be /spec/selector/app.kubernetes.io~1component",
    ]
    return "\n\n".join([
        "You are a Kubernetes configuration repair assistant.",
        "Given a manifest and a specific policy violation, produce ONLY a valid RFC6902 JSON Patch array that fixes the violation with the following constraints:",
        "- Minimize changes (fewest operations possible).",
        "- Preserve semantics; do not remove containers, volumes, or services.",
        "- Never introduce privileged=true or add dangerous capabilities (NET_RAW, NET_ADMIN, SYS_ADMIN, SYS_MODULE, SYS_PTRACE, SYS_CHROOT).",
        "- Ensure idempotence: applying the patch twice has no effect the second time.",
        "- Do not include any prose or comments; return only the JSON array.",
        "- Use RFC6901 JSON Pointer encoding in paths: escape '~' as '~0' and '/' as '~1' in key names (never URL-encode).",
        "\n".join(examples),
        "Manifest:",
        manifest_yaml,
        f"Policy: {policy_id}",
        f"Violation: {violation_text}",
    ])


def load_json(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    data = load_json(args.detections)[: args.limit]

    client = ModelClient(
        ClientOptions(
            endpoint=args.endpoint,
            model=args.model,
            api_key_env=args.api_key_env,
            timeout_seconds=args.timeout,
            retries=args.retries,
        )
    )
    verifier = Verifier(require_kubectl=args.require_kubectl)

    per_policy_counts: Dict[str, Tuple[int, int]] = {}
    per_policy_latencies: Dict[str, List[float]] = {}

    for rec in data:
        manifest_yaml = rec.get("manifest_yaml") or ""
        policy_id = normalise_policy_id(rec.get("policy_id") or "")
        violation = rec.get("violation_text") or ""
        if not manifest_yaml or not policy_id:
            continue
        prompt = build_prompt(manifest_yaml, policy_id, violation)
        t0 = time.perf_counter()
        try:
            response = client.request_patch(prompt)
            content = response.get("content")
        except Exception:
            content = None
        verify_ok = False
        if content:
            try:
                patch_ops = json.loads(content)
                if isinstance(patch_ops, list):
                    patch_ops = _sanitize_patch_paths(patch_ops)
                    res = verifier.verify(manifest_yaml, patch_ops, policy_id)
                    verify_ok = res.accepted
            except Exception:
                verify_ok = False
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        acc, tot = per_policy_counts.get(policy_id, (0, 0))
        per_policy_counts[policy_id] = (acc + (1 if verify_ok else 0), tot + 1)
        per_policy_latencies.setdefault(policy_id, []).append(elapsed_ms)

    # Write CSV
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for pol, (acc, tot) in sorted(per_policy_counts.items()):
        lat = per_policy_latencies.get(pol, [])
        rows.append(
            {
                "policy_id": pol,
                "accepted": acc,
                "total": tot,
                "acceptance_rate": (float(acc) / float(tot)) if tot else 0.0,
                "median_latency_ms": round(statistics.median(lat), 2) if lat else None,
            }
        )
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "policy_id",
                "accepted",
                "total",
                "acceptance_rate",
                "median_latency_ms",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

# ---- Helpers (path sanitization) ----
def _rfc6901_escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _decode_percent(s: str) -> str:
    try:
        from urllib.parse import unquote
        return unquote(s)
    except Exception:
        return s


def _sanitize_pointer(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        return path
    raw = _decode_percent(path)
    parts = raw.split("/")
    anchors = (
        ["metadata", "annotations"],
        ["metadata", "labels"],
        ["spec", "selector"],
        ["spec", "template", "metadata", "labels"],
        ["spec", "template", "metadata", "annotations"],
    )
    def match_anchor(prefix):
        n = len(prefix)
        if len(parts) <= 1 + n:
            return None
        if [p for p in parts[1:1+n]] == prefix:
            return 1 + n
        return None
    join_from = None
    for pref in anchors:
        idx = match_anchor(pref)
        if idx is not None:
            join_from = idx
            break
    if join_from is not None and join_from < len(parts):
        head = parts[:join_from]
        tail = parts[join_from:]
        tail_key = "/".join(tail)
        escaped_tail = _rfc6901_escape(tail_key)
        encoded = "/".join(head + [escaped_tail])
    else:
        escaped = [_rfc6901_escape(seg) for seg in parts[1:]]
        encoded = "/" + "/".join(escaped)
    return encoded


def _sanitize_patch_paths(patch_ops):
    if not isinstance(patch_ops, list):
        return patch_ops
    out = []
    for op in patch_ops:
        if not isinstance(op, dict):
            out.append(op)
            continue
        op2 = dict(op)
        for key in ("path", "from"):
            if key in op2 and isinstance(op2[key], str):
                op2[key] = _sanitize_pointer(op2[key])
        out.append(op2)
    return out
