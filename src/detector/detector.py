from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


@dataclass(frozen=True)
class DetectionResult:
    tool: str
    manifest: str
    rule: Optional[str]
    message: str
    resource: Optional[str] = None
    severity: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "tool": self.tool,
            "manifest": self.manifest,
            "rule": self.rule,
            "message": self.message,
        }
        if self.resource is not None:
            data["resource"] = self.resource
        if self.severity is not None:
            data["severity"] = self.severity
        if self.extra:
            data["extra"] = self.extra
        return data


class Detector:
    def __init__(
        self,
        kube_linter_cmd: str = "kube-linter",
        kyverno_cmd: str = "kyverno",
        policies_dir: Optional[Path] = None,
    ) -> None:
        self.kube_linter_cmd = kube_linter_cmd
        self.kyverno_cmd = kyverno_cmd
        self.policies_dir = policies_dir

    def detect(self, manifests: Sequence[Path]) -> List[DetectionResult]:
        normalized_manifests = [Path(m).resolve() for m in manifests]
        all_results: List[DetectionResult] = []

        for manifest in normalized_manifests:
            if not manifest.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest}")
            all_results.extend(self._run_kube_linter(manifest))
            if self.policies_dir:
                all_results.extend(self._run_kyverno(manifest))

        return self._deduplicate(all_results)

    def write_results(self, results: Sequence[DetectionResult], output_path: Path) -> None:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = list(self._render_detection_records(results))
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(rendered, handle, indent=2)

    def _render_detection_records(self, results: Sequence[DetectionResult]):
        cwd = Path.cwd()
        for idx, result in enumerate(results, start=1):
            manifest_path = Path(result.manifest).resolve()
            try:
                manifest_text = manifest_path.read_text(encoding="utf-8")
            except OSError:
                manifest_text = None
            try:
                manifest_rel = manifest_path.relative_to(cwd)
                manifest_rel_str = manifest_rel.as_posix()
            except ValueError:
                manifest_rel_str = str(manifest_path)

            policy_id = result.rule or f"{result.tool}_violation"

            record = {
                "id": f"{idx:03d}",
                "manifest_path": manifest_rel_str,
                "manifest_yaml": manifest_text,
                "policy_id": policy_id,
                "violation_text": result.message,
            }
            yield record

    def _run_kube_linter(self, manifest: Path) -> List[DetectionResult]:
        stdout = self._run_command(
            [
                self.kube_linter_cmd,
                "lint",
                str(manifest),
                "--format",
                "json",
            ]
        )
        documents = self._load_documents(stdout)
        results: List[DetectionResult] = []
        for document in documents:
            reports = document.get("Reports") if isinstance(document, dict) else None
            if not reports:
                continue
            for report in reports:
                if not isinstance(report, dict):
                    continue
                diagnostic = report.get("Diagnostic", {}) if isinstance(report, dict) else {}
                object_info = diagnostic.get("Object", {}) if isinstance(diagnostic, dict) else {}
                resource_ref = self._format_resource_reference(object_info)
                message = self._first_defined(
                    diagnostic.get("Message"),
                    report.get("Message"),
                    "Unknown kube-linter issue",
                )
                severity = report.get("Severity") if isinstance(report.get("Severity"), str) else None
                rule_name = report.get("Check") if isinstance(report.get("Check"), str) else None
                extra: Dict[str, Any] = {}
                if object_info:
                    extra["object"] = object_info
                if report.get("Remediation"):
                    extra["remediation"] = report["Remediation"]
                if report.get("Category"):
                    extra["category"] = report["Category"]
                results.append(
                    DetectionResult(
                        tool="kube-linter",
                        manifest=str(manifest),
                        rule=rule_name,
                        message=message,
                        resource=resource_ref,
                        severity=severity,
                        extra=extra or None,
                    )
                )
        return results

    def _run_kyverno(self, manifest: Path) -> List[DetectionResult]:
        if not self.policies_dir:
            return []
        stdout = self._run_command(
            [
                self.kyverno_cmd,
                "apply",
                str(self.policies_dir),
                "--resource",
                str(manifest),
                "--policy-report",
                "-o",
                "json",
            ]
        )
        documents = self._load_documents(stdout)
        results: List[DetectionResult] = []
        for entry in self._extract_policy_report_entries(documents):
            result_state = entry.get("result")
            if isinstance(result_state, str) and result_state.lower() in {"pass", "skip"}:
                continue
            policy_name = entry.get("policy") if isinstance(entry.get("policy"), str) else None
            rule_name = entry.get("rule") if isinstance(entry.get("rule"), str) else policy_name
            severity = entry.get("severity") if isinstance(entry.get("severity"), str) else None
            message = self._first_defined(
                entry.get("message"),
                "Kyverno reported a violation",
            )
            resource_ref = None
            if isinstance(entry.get("resources"), list) and entry["resources"]:
                resource_ref = self._format_resource_reference(entry["resources"][0])
            extra: Dict[str, Any] = {
                key: value
                for key, value in entry.items()
                if key
                not in {"policy", "rule", "result", "message", "severity", "resources"}
            }
            if policy_name:
                extra.setdefault("policy", policy_name)
            if entry.get("resources"):
                extra.setdefault("resources", entry["resources"])
            results.append(
                DetectionResult(
                    tool="kyverno",
                    manifest=str(manifest),
                    rule=rule_name,
                    message=message,
                    resource=resource_ref,
                    severity=severity,
                    extra=extra or None,
                )
            )
        return results

    @staticmethod
    def _extract_policy_report_entries(documents: List[Any]) -> Iterable[Dict[str, Any]]:
        for document in documents:
            if isinstance(document, dict) and document.get("results"):
                for entry in document["results"]:
                    if isinstance(entry, dict):
                        yield entry
            elif isinstance(document, list):
                for item in document:
                    if isinstance(item, dict) and item.get("results"):
                        for entry in item["results"]:
                            if isinstance(entry, dict):
                                yield entry

    @staticmethod
    def _run_command(command: Sequence[str]) -> str:
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Required binary not found: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            # Some tools return non-zero when findings exist. If stdout parses as YAML/JSON, return it.
            stdout = exc.stdout or ""
            if stdout.strip():
                try:
                    docs = list(yaml.safe_load_all(stdout))
                    if any(isinstance(doc, (dict, list)) for doc in docs):
                        return stdout
                except Exception:
                    pass
            stderr = exc.stderr.strip() if exc.stderr else ""
            raise RuntimeError(
                f"Command failed ({' '.join(command)}): {stderr or stdout}"
            ) from exc
        return completed.stdout

    @staticmethod
    def _load_documents(raw_output: str) -> List[Dict[str, Any]]:
        if not raw_output.strip():
            return []
        return [
            doc
            for doc in yaml.safe_load_all(raw_output)
            if isinstance(doc, (dict, list))
        ]

    @staticmethod
    def _format_resource_reference(data: Any) -> Optional[str]:
        if not isinstance(data, dict):
            return None
        kind = data.get("Kind") or data.get("kind")
        name = data.get("Name") or data.get("name")
        namespace = data.get("Namespace") or data.get("namespace")
        if not isinstance(kind, str) or not isinstance(name, str):
            return None
        if isinstance(namespace, str) and namespace:
            return f"{kind}/{namespace}/{name}"
        return f"{kind}/{name}"

    @staticmethod
    def _first_defined(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _deduplicate(results: Iterable[DetectionResult]) -> List[DetectionResult]:
        unique: Dict[Tuple[Any, ...], DetectionResult] = {}
        for result in results:
            key = (
                result.tool,
                result.manifest,
                result.rule,
                result.message,
                result.resource,
            )
            if key not in unique:
                unique[key] = result
                continue
            existing = unique[key]
            if not existing.extra and result.extra:
                unique[key] = result
        return sorted(
            unique.values(),
            key=lambda r: (r.manifest, r.tool, r.rule or "", r.message),
        )
