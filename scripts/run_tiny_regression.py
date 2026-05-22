#!/usr/bin/env python3
"""Run a tiny stdlib-light regression fixture pack."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, TextIO


if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.common.policy_ids import normalise_policy_id  # noqa: E402
from src.detector.detector import Detector  # noqa: E402
from src.proposer import cli as proposer_cli  # noqa: E402
from src.scheduler.queue import enqueue_from_verified, init_db, pick_next  # noqa: E402
from src.scheduler.schedule import schedule_patches  # noqa: E402
from src.verifier.verifier import Verifier, VerifierGates  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_ROOT = REPO_ROOT / "data/samples/tiny_regression"


class ValidationError(Exception):
    """The fixture pack cannot be loaded or has an invalid schema."""


@dataclass(frozen=True)
class Case:
    id: str
    policy_id: str
    manifest_yaml: str
    manifest_source: str
    expected_accepted: bool
    risk: float
    probability: float
    expected_time: float
    kev: bool
    expected_scheduler_rank: Optional[int]
    expected_queue_next: bool
    patch_override: Optional[list[dict[str, Any]]]
    violation_text: str


@dataclass(frozen=True)
class DetectorExpectation:
    id: str
    manifest_path: Path
    expected_rules: list[str]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a tiny Kubernetes auto-fix regression fixture pack.",
    )
    parser.add_argument(
        "pack_root",
        nargs="?",
        type=Path,
        default=DEFAULT_PACK_ROOT,
        help=f"Fixture pack root (default: {DEFAULT_PACK_ROOT}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print a machine-readable JSON report instead of markdown.",
    )
    return parser.parse_args(argv)


def run_pack(pack_root: Path) -> dict[str, Any]:
    pack_root = pack_root.resolve()
    cases = load_cases(pack_root)
    detector_expectations = load_detector_expectations(pack_root)

    failures: list[dict[str, Any]] = []
    detector_results = _run_detector_expectations(detector_expectations, failures)
    case_results = _run_case_expectations(cases, failures)
    accepted_cases = [
        case
        for case, result in zip(cases, case_results)
        if result["accepted"] is True
    ]
    scheduler_report = _run_scheduler(accepted_cases, failures)
    queue_report = _run_queue(accepted_cases, failures)

    detector_passed = sum(1 for result in detector_results if result["passed"])
    cases_passed = sum(1 for result in case_results if result["passed"])
    return {
        "success": not failures,
        "pack_root": str(pack_root),
        "detector": {
            "checked": len(detector_results),
            "passed": detector_passed,
            "results": detector_results,
        },
        "cases": {
            "checked": len(case_results),
            "passed": cases_passed,
            "results": case_results,
        },
        "scheduler": scheduler_report,
        "queue": queue_report,
        "failures": failures,
    }


def load_cases(pack_root: Path) -> list[Case]:
    source = pack_root / "cases.json"
    payload = _load_json_file(source)
    records = _extract_records(payload, key="cases", source=source)
    if not records:
        raise ValidationError(f"{source.name} must contain at least one case")
    cases: list[Case] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        label = _record_label(source.name, index, record)
        case_id = _require_string(record, "id", label)
        if case_id in seen_ids:
            raise ValidationError(f"{label} duplicates id {case_id!r}")
        seen_ids.add(case_id)
        raw_policy_id = _require_string(record, "policy_id", label)
        expected_accepted = _require_bool(record, "expected_accepted", label)
        manifest_yaml, manifest_source = _load_manifest_yaml(record, pack_root, label)
        risk = _require_number(record, "risk", label)
        probability = _require_number(record, "probability", label)
        expected_time = _require_number(record, "expected_time", label)
        kev = _require_bool(record, "kev", label)
        if risk < 0:
            raise ValidationError(f"{label} field 'risk' must be non-negative")
        if not 0 <= probability <= 1:
            raise ValidationError(f"{label} field 'probability' must be between 0 and 1")
        if expected_time <= 0:
            raise ValidationError(f"{label} field 'expected_time' must be greater than 0")
        expected_scheduler_rank = _optional_positive_int(record, "expected_scheduler_rank", label)
        expected_queue_next = _optional_bool(record, "expected_queue_next", label)
        if not expected_accepted and expected_scheduler_rank is not None:
            raise ValidationError(
                f"{label} field 'expected_scheduler_rank' is only valid for accepted cases"
            )
        if not expected_accepted and expected_queue_next:
            raise ValidationError(
                f"{label} field 'expected_queue_next' is only valid for accepted cases"
            )
        patch_override = _optional_patch_override(record, label)
        violation_text = str(record.get("violation_text") or f"tiny regression case {case_id}")
        cases.append(
            Case(
                id=case_id,
                policy_id=normalise_policy_id(raw_policy_id),
                manifest_yaml=manifest_yaml,
                manifest_source=manifest_source,
                expected_accepted=expected_accepted,
                risk=risk,
                probability=probability,
                expected_time=expected_time,
                kev=kev,
                expected_scheduler_rank=expected_scheduler_rank,
                expected_queue_next=expected_queue_next,
                patch_override=patch_override,
                violation_text=violation_text,
            )
        )
    return cases


def load_detector_expectations(pack_root: Path) -> list[DetectorExpectation]:
    source = pack_root / "detector_expectations.json"
    payload = _load_json_file(source)
    records = _extract_detector_records(payload, source=source)
    if not records:
        raise ValidationError(f"{source.name} must contain at least one detector expectation")
    expectations: list[DetectorExpectation] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        label = _record_label(source.name, index, record)
        manifest_rel = _require_string(record, "manifest_path", label)
        expectation_id = str(record.get("id") or Path(manifest_rel).stem)
        if expectation_id in seen_ids:
            raise ValidationError(f"{label} duplicates id {expectation_id!r}")
        seen_ids.add(expectation_id)
        manifest_path = _resolve_pack_path(pack_root, manifest_rel, label, field="manifest_path")
        rules_value = (
            record.get("expected_rules")
            if "expected_rules" in record
            else record.get("rules", record.get("expected_builtin_rules"))
        )
        if not isinstance(rules_value, list) or not all(isinstance(item, str) for item in rules_value):
            raise ValidationError(
                f"{label} field 'expected_rules' must be a list of strings"
            )
        expectations.append(
            DetectorExpectation(
                id=expectation_id,
                manifest_path=manifest_path,
                expected_rules=sorted(set(rules_value)),
            )
        )
    return expectations


def _run_detector_expectations(
    expectations: Sequence[DetectorExpectation],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    detector = Detector()
    results: list[dict[str, Any]] = []
    for expectation in expectations:
        try:
            detections = detector._run_builtin_checks(expectation.manifest_path)
            actual_rules = sorted({str(result.rule) for result in detections if result.rule})
            passed = actual_rules == expectation.expected_rules
            result = {
                "id": expectation.id,
                "manifest_path": str(expectation.manifest_path),
                "expected_rules": expectation.expected_rules,
                "actual_rules": actual_rules,
                "passed": passed,
            }
            if not passed:
                failures.append(
                    {
                        "component": "detector",
                        "id": expectation.id,
                        "message": (
                            f"expected rules {expectation.expected_rules}, got {actual_rules}"
                        ),
                    }
                )
            results.append(result)
        except Exception as exc:  # noqa: BLE001 - component failure is a regression
            message = f"detector failed: {exc}"
            failures.append({"component": "detector", "id": expectation.id, "message": message})
            results.append(
                {
                    "id": expectation.id,
                    "manifest_path": str(expectation.manifest_path),
                    "expected_rules": expectation.expected_rules,
                    "actual_rules": [],
                    "passed": False,
                    "error": message,
                }
            )
    return results


def _run_case_expectations(
    cases: Sequence[Case],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    verifier = Verifier(require_kubectl=False, gates=VerifierGates(kubectl=False))
    results: list[dict[str, Any]] = []
    for case in cases:
        detection = {
            "id": case.id,
            "manifest_yaml": case.manifest_yaml,
            "policy_id": case.policy_id,
            "violation_text": case.violation_text,
        }
        patch_ops: list[dict[str, Any]]
        errors: list[str] = []
        accepted = False
        patch_source = "override" if case.patch_override is not None else "rules"
        try:
            patch_ops = (
                case.patch_override
                if case.patch_override is not None
                else proposer_cli._rule_based_patch(detection)
            )
            verification = verifier.verify(case.manifest_yaml, patch_ops, case.policy_id)
            accepted = verification.accepted
            errors = list(verification.errors)
        except Exception as exc:  # noqa: BLE001 - generation failure is part of regression output
            patch_ops = []
            errors = [str(exc)]

        passed = accepted == case.expected_accepted
        if not passed:
            failures.append(
                {
                    "component": "proposer_verifier",
                    "id": case.id,
                    "message": (
                        f"expected accepted={case.expected_accepted}, got {accepted}"
                    ),
                    "errors": errors,
                }
            )
        results.append(
            {
                "id": case.id,
                "policy_id": case.policy_id,
                "manifest_source": case.manifest_source,
                "patch_source": patch_source,
                "patch_ops": len(patch_ops),
                "expected_accepted": case.expected_accepted,
                "accepted": accepted,
                "passed": passed,
                "errors": errors,
            }
        )
    return results


def _run_scheduler(cases: Sequence[Case], failures: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        {
            "id": case.id,
            "risk": case.risk,
            "probability": case.probability,
            "expected_time": case.expected_time,
            "kev": case.kev,
        }
        for case in cases
    ]
    if not candidates:
        return {"accepted_count": 0, "top_id": None, "ordered_ids": []}
    try:
        ordered = schedule_patches(candidates)
        ordered_ids = [candidate.id for candidate in ordered]
        for case in cases:
            if case.expected_scheduler_rank is None:
                continue
            actual_rank = ordered_ids.index(case.id) + 1 if case.id in ordered_ids else None
            if actual_rank != case.expected_scheduler_rank:
                failures.append(
                    {
                        "component": "scheduler",
                        "id": case.id,
                        "message": (
                            f"expected rank {case.expected_scheduler_rank}, got {actual_rank}"
                        ),
                    }
                )
        return {
            "accepted_count": len(candidates),
            "top_id": ordered[0].id if ordered else None,
            "ordered_ids": ordered_ids,
        }
    except Exception as exc:  # noqa: BLE001
        failures.append({"component": "scheduler", "id": None, "message": str(exc)})
        return {"accepted_count": len(candidates), "top_id": None, "ordered_ids": [], "error": str(exc)}


def _run_queue(cases: Sequence[Case], failures: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        return {"inserted_count": 0, "next_id": None}
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            db_path = tmp / "queue.db"
            detections_path = tmp / "detections.json"
            verified_path = tmp / "verified.json"
            risk_path = tmp / "risk.json"
            detections = [{"id": case.id, "policy_id": case.policy_id} for case in cases]
            verified = [{"id": case.id, "accepted": True} for case in cases]
            risk = [
                {
                    "id": case.id,
                    "risk": case.risk,
                    "probability": case.probability,
                    "expected_time": case.expected_time,
                    "kev": case.kev,
                }
                for case in cases
            ]
            _write_json(detections_path, detections)
            _write_json(verified_path, verified)
            _write_json(risk_path, risk)
            init_db(db_path)
            inserted = enqueue_from_verified(db_path, verified_path, detections_path, risk_path)
            next_item = pick_next(db_path)
            next_id = next_item.id if next_item is not None else None
            expected_next = [case.id for case in cases if case.expected_queue_next]
            if len(expected_next) > 1:
                failures.append(
                    {
                        "component": "queue",
                        "id": None,
                        "message": f"multiple cases marked expected_queue_next: {expected_next}",
                    }
                )
            elif len(expected_next) == 1 and next_id != expected_next[0]:
                failures.append(
                    {
                        "component": "queue",
                        "id": expected_next[0],
                        "message": f"expected next id {expected_next[0]!r}, got {next_id!r}",
                    }
                )
            return {
                "inserted_count": inserted,
                "next_id": next_id,
            }
    except Exception as exc:  # noqa: BLE001
        failures.append({"component": "queue", "id": None, "message": str(exc)})
        return {"inserted_count": 0, "next_id": None, "error": str(exc)}


def render_markdown(report: Mapping[str, Any]) -> str:
    status = "PASS" if report["success"] else "FAIL"
    detector = report["detector"]
    cases = report["cases"]
    scheduler = report["scheduler"]
    queue = report["queue"]
    lines = [
        "# Tiny Regression Report",
        "",
        f"Status: **{status}**",
        f"Pack: `{report['pack_root']}`",
        "",
        f"- Detector expectations: {detector['passed']}/{detector['checked']}",
        f"- Proposer/verifier cases: {cases['passed']}/{cases['checked']}",
        f"- Accepted cases scheduled: {scheduler['accepted_count']}",
        f"- Scheduler top: {_format_optional_id(scheduler['top_id'])}",
        f"- Queue inserted: {queue['inserted_count']}",
        f"- Queue next: {_format_optional_id(queue['next_id'])}",
    ]
    failures = report.get("failures") or []
    if failures:
        lines.extend(["", "## Failures"])
        for failure in failures:
            component = failure.get("component", "unknown")
            failure_id = failure.get("id")
            prefix = f"{component} `{failure_id}`" if failure_id is not None else str(component)
            lines.append(f"- {prefix}: {failure.get('message', 'failed')}")
    return "\n".join(lines) + "\n"


def _format_optional_id(value: Any) -> str:
    if value is None:
        return "`(none)`"
    return f"`{value}`"


def _load_json_file(path: Path) -> Any:
    if not path.exists():
        raise ValidationError(f"missing required file: {path}")
    if not path.is_file():
        raise ValidationError(f"required path is not a file: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"failed to parse {path}: {exc}") from exc
    except OSError as exc:
        raise ValidationError(f"failed to read {path}: {exc}") from exc


def _extract_records(payload: Any, *, key: str, source: Path) -> list[Mapping[str, Any]]:
    data = payload
    if isinstance(payload, Mapping):
        if key not in payload:
            raise ValidationError(f"{source.name} must be a JSON array or contain a '{key}' array")
        data = payload[key]
    if not isinstance(data, list):
        raise ValidationError(f"{source.name} must contain a JSON array")
    records: list[Mapping[str, Any]] = []
    for index, record in enumerate(data):
        if not isinstance(record, Mapping):
            raise ValidationError(f"{source.name} record {index} must be a JSON object")
        records.append(record)
    return records


def _extract_detector_records(payload: Any, *, source: Path) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping) and "expectations" not in payload:
        records: list[Mapping[str, Any]] = []
        for manifest_path, expected_rules in payload.items():
            if not isinstance(manifest_path, str):
                raise ValidationError(f"{source.name} manifest keys must be strings")
            records.append(
                {
                    "id": Path(manifest_path).stem,
                    "manifest_path": manifest_path,
                    "expected_rules": expected_rules,
                }
            )
        return records
    return _extract_records(payload, key="expectations", source=source)


def _record_label(source_name: str, index: int, record: Mapping[str, Any]) -> str:
    record_id = record.get("id")
    if isinstance(record_id, str) and record_id:
        return f"{source_name} case {record_id!r}"
    return f"{source_name} record {index}"


def _require_string(record: Mapping[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} missing required string field '{field}'")
    return value


def _require_bool(record: Mapping[str, Any], field: str, label: str) -> bool:
    value = record.get(field)
    if not isinstance(value, bool):
        raise ValidationError(f"{label} missing required boolean field '{field}'")
    return value


def _require_number(record: Mapping[str, Any], field: str, label: str) -> float:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} missing required numeric field '{field}'")
    return float(value)


def _optional_bool(record: Mapping[str, Any], field: str, label: str) -> bool:
    if field not in record:
        return False
    value = record[field]
    if not isinstance(value, bool):
        raise ValidationError(f"{label} field '{field}' must be a boolean")
    return value


def _optional_positive_int(record: Mapping[str, Any], field: str, label: str) -> Optional[int]:
    if field not in record or record[field] is None:
        return None
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{label} field '{field}' must be a positive integer")
    return value


def _load_manifest_yaml(record: Mapping[str, Any], pack_root: Path, label: str) -> tuple[str, str]:
    manifest_yaml = record.get("manifest_yaml")
    manifest_path = record.get("manifest_path", record.get("manifest"))
    if isinstance(manifest_yaml, str) and manifest_yaml.strip():
        return manifest_yaml, "inline"
    if isinstance(manifest_path, str) and manifest_path.strip():
        path = _resolve_pack_path(pack_root, manifest_path, label, field="manifest_path")
        try:
            return path.read_text(encoding="utf-8"), str(path)
        except OSError as exc:
            raise ValidationError(f"{label} failed to read manifest_path {manifest_path!r}: {exc}") from exc
    raise ValidationError(f"{label} must include 'manifest_yaml' or 'manifest_path'")


def _resolve_pack_path(pack_root: Path, relative_path: str, label: str, *, field: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValidationError(f"{label} {field} must be relative to the fixture pack: {relative_path}")
    else:
        candidate = (pack_root / path).resolve()
    try:
        candidate.relative_to(pack_root)
    except ValueError as exc:
        raise ValidationError(f"{label} {field} escapes fixture pack: {relative_path}") from exc
    if not candidate.exists():
        raise ValidationError(f"{label} {field} not found: {relative_path}")
    if not candidate.is_file():
        raise ValidationError(f"{label} {field} is not a file: {relative_path}")
    return candidate


def _optional_patch_override(
    record: Mapping[str, Any],
    label: str,
) -> Optional[list[dict[str, Any]]]:
    if "patch_override" not in record or record["patch_override"] is None:
        return None
    value = record["patch_override"]
    if not isinstance(value, list):
        raise ValidationError(f"{label} field 'patch_override' must be a JSON Patch array")
    patch: list[dict[str, Any]] = []
    for index, op in enumerate(value):
        if not isinstance(op, dict):
            raise ValidationError(f"{label} patch_override op {index} must be a JSON object")
        if not isinstance(op.get("op"), str) or not isinstance(op.get("path"), str):
            raise ValidationError(
                f"{label} patch_override op {index} must include string 'op' and 'path'"
            )
        patch.append(dict(op))
    return patch


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = parse_args(argv)
    try:
        report = run_pack(args.pack_root)
    except ValidationError as exc:
        stderr.write(f"error: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001 - unexpected component failure
        stderr.write(f"error: regression runner failed: {exc}\n")
        return 1

    if args.json_output:
        stdout.write(json.dumps(report, indent=2, sort_keys=True))
        stdout.write("\n")
    else:
        stdout.write(render_markdown(report))
    return 0 if report["success"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
