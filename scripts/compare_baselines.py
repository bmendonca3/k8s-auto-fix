#!/usr/bin/env python3
"""
Build a unified baseline comparison table.

Inputs (optional but expected):
- data/verified.json (k8s-auto-fix triad results)
- data/detections.json (for totals)
- data/baselines/kyverno_baseline.csv
- data/baselines/polaris_baseline.csv
- data/baselines/map_baseline.csv
- data/baselines/llmsecconfig_slice.csv

Outputs:
- data/baselines/baseline_summary.csv (wide table by policy)
- docs/reproducibility/baselines.md (human-readable summary)
- docs/reproducibility/baselines.tex (LaTeX table)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CANONICAL_POLICY_MAP: Dict[str, str] = {
    "cap-sys-admin": "drop_cap_sys_admin",
    "drop-net-raw-capability": "drop_capabilities",
    "host-ports": "no_host_ports",
    "hostpath-volume": "no_host_path",
    "latest-tag": "no_latest_tag",
    "no-read-only-root-fs": "read_only_root_fs",
    "privilege-escalation-container": "no_privileged",
    "privileged-container": "no_privileged",
    "run-as-non-root": "run_as_non_root",
    "unset-cpu-requirements": "set_requests_limits",
    "unset-memory-requirements": "set_requests_limits",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare baselines vs triad")
    p.add_argument("--detections", type=Path, default=Path("data/detections.json"))
    p.add_argument("--verified", type=Path, default=Path("data/verified.json"))
    p.add_argument("--kyverno", type=Path, default=Path("data/baselines/kyverno_baseline.csv"))
    p.add_argument("--polaris-cli", type=Path, default=Path("data/baselines/polaris_baseline.csv"))
    p.add_argument("--polaris-webhook", type=Path, default=Path("data/baselines/polaris_baseline_webhook.csv"))
    p.add_argument("--map", type=Path, default=Path("data/baselines/map_baseline.csv"))
    p.add_argument("--llmsec", type=Path, default=Path("data/baselines/llmsecconfig_slice.csv"))
    p.add_argument("--out-csv", type=Path, default=Path("data/baselines/baseline_summary.csv"))
    p.add_argument("--out-md", type=Path, default=Path("docs/reproducibility/baselines.md"))
    p.add_argument("--out-tex", type=Path, default=Path("docs/reproducibility/baselines.tex"))
    return p.parse_args()


def load_json_array(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    return [x for x in data if isinstance(x, dict)]


def load_csv(path: Path, key_field: str, value_fields: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = str(row.get(key_field) or "").strip().lower()
            if not raw:
                continue
            key = CANONICAL_POLICY_MAP.get(raw, raw.replace("-", "_"))
            if not key:
                continue
            out[key] = {field: row.get(field) for field in value_fields}
    return out


def summarise_triad(detections: List[Dict[str, Any]], verified: List[Dict[str, Any]]) -> Dict[str, Tuple[int, int]]:
    totals: Counter[str] = Counter()
    accepted: Counter[str] = Counter()

    for d in detections:
        raw = str(d.get("policy_id") or "").strip().lower()
        canonical = CANONICAL_POLICY_MAP.get(raw, raw.replace("-", "_"))
        if canonical:
            totals[canonical] += 1

    for v in verified:
        raw = str(v.get("policy_id") or "").strip().lower()
        canonical = CANONICAL_POLICY_MAP.get(raw, raw.replace("-", "_"))
        if not canonical:
            continue
        if bool(v.get("accepted")):
            accepted[canonical] += 1
        totals.setdefault(canonical, totals.get(canonical, 0))

    return {policy: (accepted.get(policy, 0), totals.get(policy, 0)) for policy in totals}


def write_wide_csv(summary: Dict[str, Dict[str, Any]], out: Path) -> None:
    fields = [
        "policy_id",
        "k8s_accept",
        "k8s_total",
        "k8s_rate",
        "kyverno_accept",
        "kyverno_total",
        "kyverno_rate",
        "polaris_cli_accept",
        "polaris_cli_total",
        "polaris_cli_rate",
        "polaris_webhook_accept",
        "polaris_webhook_total",
        "polaris_webhook_rate",
        "map_accept",
        "map_total",
        "map_rate",
        "llmsec_accept",
        "llmsec_total",
        "llmsec_rate",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for pol, row in sorted(summary.items()):
            writer.writerow({"policy_id": pol, **row})


def format_rate(n: Optional[float]) -> str:
    if n is None:
        return "n/a"
    return f"{100.0 * n:.2f}%"


def write_md(summary: Dict[str, Dict[str, Any]], out: Path) -> None:
    lines = [
        "# Baseline Comparison (per-policy)",
        "",
        "| Policy | k8s-auto-fix | Kyverno | Polaris CLI | Polaris webhook | MutatingAdmissionPolicy | LLMSecConfig slice |",
        "| ------ | ------------- | ------- | ----------- | --------------- | ---------------------- | ------------------ |",
    ]
    for pol, row in sorted(summary.items()):
        cells = []
        for pref in ("k8s", "kyverno", "polaris_cli", "polaris_webhook", "map", "llmsec"):
            a = row.get(f"{pref}_accept")
            t = row.get(f"{pref}_total")
            r = row.get(f"{pref}_rate")
            cell = "n/a"
            try:
                if a is not None and t is not None and int(t) > 0:
                    cell = f"{int(a)}/{int(t)}"
                    if r is not None:
                        cell += f" ({format_rate(float(r))})"
            except Exception:
                pass
            cells.append(cell)
        lines.append(f"| {pol} | " + " | ".join(cells) + " |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_tex(summary: Dict[str, Dict[str, Any]], out: Path) -> None:
    row_sep = "\\\\"
    lines: List[str] = []
    lines.append("\\begin{tabularx}{\\textwidth}{@{}l c c c c c c@{}}")
    lines.append("\\toprule")
    lines.append("\\textbf{Policy} & \\textbf{k8s-auto-fix} & \\textbf{Kyverno} & \\textbf{Polaris CLI} & \\textbf{Polaris webhook} & \\textbf{MAP} & \\textbf{LLMSecConfig} " + row_sep)
    lines.append("\\midrule")

    def latex_escape(s: str) -> str:
        repl = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }
        return "".join(repl.get(ch, ch) for ch in s)

    for pol, row in sorted(summary.items()):
        def cell(pref: str) -> str:
            a = row.get(f"{pref}_accept")
            t = row.get(f"{pref}_total")
            r = row.get(f"{pref}_rate")
            if a is None or t is None or t == 0:
                return "n/a"
            try:
                base = f"{int(a)}/{int(t)}"
                if r is not None:
                    base += f" ({100.0*float(r):.1f}" + "\\%" + ")"
                return base
            except Exception:
                return "n/a"

        pol_escaped = latex_escape(pol)
        row_tex = (
            f"{pol_escaped} & {cell('k8s')} & {cell('kyverno')} & {cell('polaris_cli')} & "
            f"{cell('polaris_webhook')} & {cell('map')} & {cell('llmsec')} {row_sep}"
        )
        lines.append(row_tex)

    lines.append("\\bottomrule")
    lines.append("\\end{tabularx}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
def main() -> None:
    args = parse_args()
    detections = load_json_array(args.detections)
    verified = load_json_array(args.verified)
    triad = summarise_triad(detections, verified)

    # Load baselines
    kyverno = load_csv(args.kyverno, "policy_id", ["kyverno_mutations", "detections", "acceptance_rate"])  # type: ignore
    polaris_cli = load_csv(args.polaris_cli, "policy_id", ["polaris_fixes", "detections", "acceptance_rate"])  # type: ignore
    polaris_webhook = load_csv(args.polaris_webhook, "policy_id", ["polaris_fixes", "detections", "acceptance_rate"])  # type: ignore
    mapb = load_csv(args.map, "policy_id", ["map_mutations", "detections", "acceptance_rate"])  # type: ignore
    llmsec = load_csv(args.llmsec, "policy_id", ["accepted", "total", "acceptance_rate"])  # type: ignore

    # Merge by union of policies we know about
    policies = set(triad) | set(kyverno) | set(polaris_cli) | set(polaris_webhook) | set(mapb) | set(llmsec)
    summary: Dict[str, Dict[str, Any]] = {}
    for pol in policies:
        row: Dict[str, Any] = {}
        # k8s triad
        ta, tt = triad.get(pol, (None, None))
        row["k8s_accept"] = ta
        row["k8s_total"] = tt
        row["k8s_rate"] = (float(ta) / float(tt)) if (isinstance(ta, int) and isinstance(tt, int) and tt > 0) else None

        # kyverno
        if pol in kyverno:
            a = kyverno[pol].get("kyverno_mutations")
            t = kyverno[pol].get("detections")
            r = kyverno[pol].get("acceptance_rate")
            row["kyverno_accept"] = int(float(a)) if a is not None and str(a) != "" else None
            row["kyverno_total"] = int(float(t)) if t is not None and str(t) != "" else None
            row["kyverno_rate"] = float(r) if r not in (None, "") else None
        else:
            row["kyverno_accept"] = row["kyverno_total"] = row["kyverno_rate"] = None

        # polaris CLI
        if pol in polaris_cli:
            a = polaris_cli[pol].get("polaris_fixes")
            t = polaris_cli[pol].get("detections")
            r = polaris_cli[pol].get("acceptance_rate")
            row["polaris_cli_accept"] = int(float(a)) if a not in (None, "") else None
            row["polaris_cli_total"] = int(float(t)) if t not in (None, "") else None
            row["polaris_cli_rate"] = float(r) if r not in (None, "") else None
        else:
            row["polaris_cli_accept"] = row["polaris_cli_total"] = row["polaris_cli_rate"] = None

        # polaris webhook
        if pol in polaris_webhook:
            a = polaris_webhook[pol].get("polaris_fixes")
            t = polaris_webhook[pol].get("detections")
            r = polaris_webhook[pol].get("acceptance_rate")
            row["polaris_webhook_accept"] = int(float(a)) if a not in (None, "") else None
            row["polaris_webhook_total"] = int(float(t)) if t not in (None, "") else None
            row["polaris_webhook_rate"] = float(r) if r not in (None, "") else None
        else:
            row["polaris_webhook_accept"] = row["polaris_webhook_total"] = row["polaris_webhook_rate"] = None

        # MAP
        if pol in mapb:
            a = mapb[pol].get("map_mutations")
            t = mapb[pol].get("detections")
            r = mapb[pol].get("acceptance_rate")
            row["map_accept"] = int(float(a)) if a not in (None, "") else None
            row["map_total"] = int(float(t)) if t not in (None, "") else None
            row["map_rate"] = float(r) if r not in (None, "") else None
        else:
            row["map_accept"] = row["map_total"] = row["map_rate"] = None

        # LLMSec slice
        if pol in llmsec:
            a = llmsec[pol].get("accepted")
            t = llmsec[pol].get("total")
            r = llmsec[pol].get("acceptance_rate")
            row["llmsec_accept"] = int(float(a)) if a not in (None, "") else None
            row["llmsec_total"] = int(float(t)) if t not in (None, "") else None
            row["llmsec_rate"] = float(r) if r not in (None, "") else None
        else:
            row["llmsec_accept"] = row["llmsec_total"] = row["llmsec_rate"] = None

        summary[pol] = row

    write_wide_csv(summary, args.out_csv)
    write_md(summary, args.out_md)
    write_tex(summary, args.out_tex)


if __name__ == "__main__":
    main()
