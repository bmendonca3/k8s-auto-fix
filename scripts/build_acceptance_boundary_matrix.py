#!/usr/bin/env python3
"""Build an acceptance-boundary matrix from checked-in verifier records.

The matrix reuses existing verifier outputs rather than rerunning proposers or
inventing named-agent baselines. Each weaker boundary is evaluated against the
same candidate patch records, and an escape is any patch a weaker boundary would
accept while the full verifier rejected it.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping


Record = Mapping[str, Any]
Predicate = Callable[[Record], bool]


REGIMES: tuple[tuple[str, str, Predicate], ...] = (
    ("emitted", "Ungated proposer output", lambda item: True),
    ("policy_only", "Scanner/policy re-check only", lambda item: bool(item.get("ok_policy"))),
    (
        "admission_style",
        "Policy + API-admission gates",
        lambda item: bool(item.get("ok_policy")) and bool(item.get("ok_schema")),
    ),
    ("full_verifier", "Full verifier boundary", lambda item: bool(item.get("accepted"))),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build acceptance-boundary matrix artifacts.")
    parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        metavar="LABEL:PATH",
        help="Verified-record dataset, e.g. rules_5k:data/verified_rules_5000.json.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("data/ablation/acceptance_boundary_matrix.json"),
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("data/ablation/acceptance_boundary_matrix.csv"),
    )
    parser.add_argument(
        "--out-tex",
        type=Path,
        default=Path("paper/acceptance_boundary_matrix.tex"),
    )
    return parser.parse_args()


def load_records(path: Path) -> List[Record]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [item for item in data if isinstance(item, dict)]


def summarise(label: str, records: Iterable[Record]) -> Dict[str, Any]:
    items = list(records)
    total = len(items)
    full_accepts = {str(item.get("id")) for item in items if bool(item.get("accepted"))}
    gate_failures = {
        "policy": sum(1 for item in items if not bool(item.get("ok_policy"))),
        "schema": sum(1 for item in items if not bool(item.get("ok_schema"))),
        "safety": sum(1 for item in items if not bool(item.get("ok_safety"))),
        "rescan": sum(1 for item in items if not bool(item.get("ok_rescan"))),
    }

    regimes: List[Dict[str, Any]] = []
    for key, name, predicate in REGIMES:
        accepted_ids = {str(item.get("id")) for item in items if predicate(item)}
        escaped_ids = sorted(accepted_ids - full_accepts)
        regimes.append(
            {
                "key": key,
                "name": name,
                "accepted": len(accepted_ids),
                "acceptance_rate": round(len(accepted_ids) / total if total else 0.0, 6),
                "escapes": len(escaped_ids),
                "escape_rate": round(len(escaped_ids) / total if total else 0.0, 6),
                "escape_ids_sample": escaped_ids[:20],
            }
        )

    return {
        "dataset": label,
        "total": total,
        "full_accepted": len(full_accepts),
        "full_acceptance_rate": round(len(full_accepts) / total if total else 0.0, 6),
        "gate_failures": gate_failures,
        "regimes": regimes,
    }


def write_csv(path: Path, summaries: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset",
                "total",
                "regime",
                "accepted",
                "acceptance_rate",
                "escapes",
                "escape_rate",
                "policy_failures",
                "schema_failures",
                "safety_failures",
                "rescan_failures",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for summary in summaries:
            failures = summary["gate_failures"]
            for regime in summary["regimes"]:
                writer.writerow(
                    {
                        "dataset": summary["dataset"],
                        "total": summary["total"],
                        "regime": regime["key"],
                        "accepted": regime["accepted"],
                        "acceptance_rate": regime["acceptance_rate"],
                        "escapes": regime["escapes"],
                        "escape_rate": regime["escape_rate"],
                        "policy_failures": failures["policy"],
                        "schema_failures": failures["schema"],
                        "safety_failures": failures["safety"],
                        "rescan_failures": failures["rescan"],
                    }
                )


def pct(value: float) -> str:
    return f"{value * 100:.2f}\\%"


def write_tex(path: Path, summaries: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\scriptsize",
        "\\caption{Acceptance-boundary matrix on checked-in 5k verifier-record snapshots. Escapes are records accepted by a weaker boundary but rejected by the corresponding full-verifier snapshot; the API-admission column uses the recorded \\texttt{ok\\_schema} server-side dry-run flag.}",
        "\\label{tab:verifier_ablation}",
        "\\begin{tabular}{@{}l l r r r@{}}",
        "\\toprule",
        "\\textbf{Dataset} & \\textbf{Boundary} & \\textbf{Accepted} & \\textbf{Accept.} & \\textbf{Escapes} \\\\",
        "\\midrule",
    ]
    first = True
    for summary in summaries:
        if not first:
            lines.append("\\midrule")
        first = False
        dataset = str(summary["dataset"]).replace("_", "\\_")
        total = int(summary["total"])
        for regime in summary["regimes"]:
            lines.append(
                f"{dataset} & {regime['name']} & {regime['accepted']}/{total} & "
                f"{pct(float(regime['acceptance_rate']))} & {regime['escapes']} \\\\"
            )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    summaries: List[Dict[str, Any]] = []
    for entry in args.dataset:
        if ":" not in entry:
            raise ValueError(f"Dataset must be LABEL:PATH, got {entry!r}")
        label, raw_path = entry.split(":", 1)
        summaries.append(summarise(label, load_records(Path(raw_path))))

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    write_csv(args.out_csv, summaries)
    write_tex(args.out_tex, summaries)


if __name__ == "__main__":
    main()
