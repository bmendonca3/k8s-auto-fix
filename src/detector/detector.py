from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
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

    def detect(self, manifests: Sequence[Path], jobs: int = 1) -> List[DetectionResult]:
        normalized_manifests = [Path(m).resolve() for m in manifests]
        all_results: List[DetectionResult] = []

        def process_manifest(manifest: Path) -> List[DetectionResult]:
            if not manifest.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest}")
            manifest_results: List[DetectionResult] = []
            manifest_results.extend(self._run_kube_linter(manifest))
            if self.policies_dir:
                manifest_results.extend(self._run_kyverno(manifest))
            manifest_results.extend(self._run_builtin_checks(manifest))
            return manifest_results

        if jobs <= 1:
            for manifest in normalized_manifests:
                all_results.extend(process_manifest(manifest))
        else:
            jobs = min(jobs, len(normalized_manifests))
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = [executor.submit(process_manifest, manifest) for manifest in normalized_manifests]
                for future in futures:
                    all_results.extend(future.result())

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
                manifest_text = self._load_targeted_manifest(manifest_path, result)
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

    def _load_targeted_manifest(self, manifest_path: Path, detection: DetectionResult) -> Optional[str]:
        raw_text = manifest_path.read_text(encoding="utf-8")
        try:
            documents = list(yaml.safe_load_all(raw_text))
        except yaml.YAMLError:
            return raw_text
        if not documents:
            return raw_text

        identity = self._extract_resource_identity(detection)

        if any(identity):
            target_doc = self._select_document(documents, identity)
            if target_doc is not None:
                return yaml.safe_dump(target_doc, sort_keys=False)

        if len(documents) == 1 and isinstance(documents[0], dict):
            pruned = self._prune_document(documents[0], detection)
            return yaml.safe_dump(pruned, sort_keys=False)

        first_mapping = next((doc for doc in documents if isinstance(doc, dict)), None)
        if first_mapping is not None:
            pruned = self._prune_document(first_mapping, detection)
            return yaml.safe_dump(pruned, sort_keys=False)

        first_doc = documents[0]
        if not isinstance(first_doc, (str, bytes)):
            try:
                return yaml.safe_dump(first_doc, sort_keys=False)
            except Exception:
                pass

        return raw_text

    @staticmethod
    def _extract_resource_identity(detection: DetectionResult) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        kind: Optional[str] = None
        namespace: Optional[str] = None
        name: Optional[str] = None

        resource = detection.resource
        if isinstance(resource, str) and resource.strip():
            parts = [part for part in resource.split("/") if part]
            if len(parts) == 2:
                kind, name = parts
            elif len(parts) >= 3:
                kind, namespace, name = parts[0], parts[1], parts[2]

        extra = detection.extra or {}
        if isinstance(extra, dict):
            object_info = extra.get("object")
            if isinstance(object_info, dict):
                kind = kind or Detector._first_string(object_info, "Kind", "kind")
                namespace = namespace or Detector._first_string(object_info, "Namespace", "namespace")
                name = name or Detector._first_string(object_info, "Name", "name")
            resources = extra.get("resources")
            if isinstance(resources, list):
                for resource_entry in resources:
                    if not isinstance(resource_entry, dict):
                        continue
                    kind = kind or Detector._first_string(resource_entry, "kind", "Kind")
                    namespace = namespace or Detector._first_string(resource_entry, "namespace", "Namespace")
                    name = name or Detector._first_string(resource_entry, "name", "Name")
                    if kind and name:
                        break

        return (kind, namespace, name)

    @staticmethod
    def _select_document(
        documents: Sequence[Any], identity: Tuple[Optional[str], Optional[str], Optional[str]]
    ) -> Optional[Any]:
        kind, namespace, name = identity
        lowered_kind = kind.lower() if isinstance(kind, str) else None
        lowered_name = name.lower() if isinstance(name, str) else None
        lowered_namespace = namespace.lower() if isinstance(namespace, str) else None

        for document in documents:
            if not isinstance(document, dict):
                continue
            doc_kind = document.get("kind")
            metadata = document.get("metadata")
            doc_name = metadata.get("name") if isinstance(metadata, dict) else None
            doc_namespace = metadata.get("namespace") if isinstance(metadata, dict) else None

            if lowered_kind and (not isinstance(doc_kind, str) or doc_kind.lower() != lowered_kind):
                continue
            if lowered_name and (not isinstance(doc_name, str) or doc_name.lower() != lowered_name):
                continue
            if lowered_namespace:
                doc_ns_normalised = doc_namespace.lower() if isinstance(doc_namespace, str) else ""
                if doc_ns_normalised != lowered_namespace:
                    continue
            return document
        return None

    @staticmethod
    def _prune_document(document: Dict[str, Any], detection: DetectionResult) -> Dict[str, Any]:
        """
        Reduce large manifests to the minimal context needed for prompting when the detector
        cannot pinpoint an exact resource. Keeps identifying metadata plus policy-relevant
        spec subtrees so downstream patches and verifications still succeed.
        """

        def prune_metadata(meta: Any) -> Dict[str, Any]:
            if not isinstance(meta, dict):
                return {}
            allowed_keys = ("name", "namespace", "labels", "annotations")
            return {key: value for key, value in meta.items() if key in allowed_keys and value is not None}

        def prune_container(container: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(container, dict):
                return {}
            allowed = {
                "name",
                "image",
                "securityContext",
                "resources",
                "env",
                "envFrom",
                "ports",
                "volumeMounts",
                "command",
                "args",
                "livenessProbe",
                "readinessProbe",
                "startupProbe",
                "workingDir",
                "imagePullPolicy",
            }
            return {key: value for key, value in container.items() if key in allowed and value is not None}

        def prune_containers(section: Any) -> Any:
            if not isinstance(section, list):
                return section
            pruned_list = [prune_container(container) for container in section if isinstance(container, dict)]
            return [container for container in pruned_list if container]

        def prune_spec(spec: Any, level: int = 0) -> Dict[str, Any]:
            if not isinstance(spec, dict):
                return {}

            allowed_keys = {
                "containers",
                "initContainers",
                "ephemeralContainers",
                "volumes",
                "securityContext",
                "serviceAccount",
                "serviceAccountName",
                "affinity",
                "selector",
                "replicas",
                "template",
                "jobTemplate",
                "ttlSecondsAfterFinished",
                "unhealthyPodEvictionPolicy",
                "type",
                "externalName",
                "ports",
                "clusterIP",
                "sessionAffinity",
                "data",
                "stringData",
            }

            policy = (detection.rule or "").lower()
            if "host_path" in policy:
                allowed_keys.add("volumeMounts")
            if "env" in policy:
                allowed_keys.add("env")
                allowed_keys.add("envFrom")

            pruned: Dict[str, Any] = {}
            for key, value in spec.items():
                if key not in allowed_keys:
                    continue
                if key in {"containers", "initContainers", "ephemeralContainers"}:
                    pruned_value = prune_containers(value)
                    if pruned_value:
                        pruned[key] = pruned_value
                    continue
                if key in {"template"} and isinstance(value, dict):
                    nested = {
                        "metadata": prune_metadata(value.get("metadata")),
                        "spec": prune_spec(value.get("spec"), level + 1),
                    }
                    nested = {k: v for k, v in nested.items() if v}
                    if nested:
                        pruned[key] = nested
                    continue
                if key == "jobTemplate" and isinstance(value, dict):
                    job_spec = value.get("spec")
                    nested = {}
                    if isinstance(job_spec, dict):
                        template = job_spec.get("template")
                        if isinstance(template, dict):
                            nested_template = {
                                "metadata": prune_metadata(template.get("metadata")),
                                "spec": prune_spec(template.get("spec"), level + 1),
                            }
                            nested_template = {k: v for k, v in nested_template.items() if v}
                            if nested_template:
                                nested["template"] = nested_template
                    if nested:
                        pruned[key] = nested
                    continue
                pruned[key] = value
            return pruned

        pruned_doc: Dict[str, Any] = {}
        for key in ("apiVersion", "kind"):
            if key in document:
                pruned_doc[key] = document[key]

        metadata = prune_metadata(document.get("metadata"))
        if metadata:
            pruned_doc["metadata"] = metadata

        spec = prune_spec(document.get("spec"))
        if spec:
            pruned_doc["spec"] = spec

        # Preserve service-specific fields when spec is absent.
        if "spec" not in pruned_doc and isinstance(document.get("spec"), dict):
            pruned_doc["spec"] = {}

        return pruned_doc or document

    @staticmethod
    def _first_string(data: Dict[str, Any], *keys: str) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

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

    def _run_builtin_checks(self, manifest: Path) -> List[DetectionResult]:
        try:
            raw_text = manifest.read_text(encoding="utf-8")
        except OSError:
            return []

        try:
            documents = list(yaml.safe_load_all(raw_text))
        except yaml.YAMLError:
            return []

        results: List[DetectionResult] = []
        for document in documents:
            if not isinstance(document, dict):
                continue
            specs = list(self._collect_specs(document.get("spec")))
            if not specs:
                continue
            resource_ref = self._format_document_reference(document)
            manifest_str = str(manifest.resolve())

            if any(self._spec_requires_cap_drop(spec, "SYS_ADMIN") for spec in specs):
                results.append(
                    DetectionResult(
                        tool="builtin",
                        manifest=manifest_str,
                        rule="cap-sys-admin",
                        message="container capabilities must drop SYS_ADMIN",
                        resource=resource_ref,
                        severity="warning",
                    )
                )

            if any(self._spec_contains_host_path(spec) for spec in specs):
                results.append(
                    DetectionResult(
                        tool="builtin",
                        manifest=manifest_str,
                        rule="hostpath-volume",
                        message="volume uses hostPath",
                        resource=resource_ref,
                        severity="warning",
                    )
                )

            if any(self._spec_contains_host_port(spec) for spec in specs):
                results.append(
                    DetectionResult(
                        tool="builtin",
                        manifest=manifest_str,
                        rule="host-ports",
                        message="container exposes hostPort",
                        resource=resource_ref,
                        severity="warning",
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

    def _collect_specs(self, spec_root: Any) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []

        def visit(candidate: Any) -> None:
            if not isinstance(candidate, dict):
                return
            specs.append(candidate)

            template = candidate.get("template")
            if isinstance(template, dict):
                visit(template.get("spec"))

            job_template = candidate.get("jobTemplate")
            if isinstance(job_template, dict):
                job_spec = job_template.get("spec")
                if isinstance(job_spec, dict):
                    visit(job_spec.get("template", {}).get("spec"))

        visit(spec_root)
        return specs

    @staticmethod
    def _spec_contains_host_path(spec: Dict[str, Any]) -> bool:
        volumes = spec.get("volumes")
        if isinstance(volumes, list):
            for volume in volumes:
                if isinstance(volume, dict) and isinstance(volume.get("hostPath"), dict):
                    return True
        return False

    @staticmethod
    def _spec_contains_host_port(spec: Dict[str, Any]) -> bool:
        for container in Detector._iter_containers(spec):
                ports = container.get("ports")
                if isinstance(ports, list):
                    for port in ports:
                        if isinstance(port, dict) and port.get("hostPort") is not None:
                            return True
        return False

    @staticmethod
    def _spec_requires_cap_drop(spec: Dict[str, Any], capability: str) -> bool:
        cap = (capability or "").upper()
        if not cap:
            return False
        for container in Detector._iter_containers(spec):
            if not Detector._container_drops_cap(container, cap):
                return True
        return False

    @staticmethod
    def _iter_containers(spec: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        if not isinstance(spec, dict):
            return []
        for key in ("containers", "initContainers", "ephemeralContainers"):
            section = spec.get(key)
            if not isinstance(section, list):
                continue
            for container in section:
                if isinstance(container, dict):
                    yield container

    @staticmethod
    def _container_drops_cap(container: Dict[str, Any], capability: str) -> bool:
        sec = container.get("securityContext")
        if not isinstance(sec, dict):
            return False
        caps = sec.get("capabilities")
        if not isinstance(caps, dict):
            return False
        drop = caps.get("drop")
        if not isinstance(drop, list):
            return False
        normalised = {
            str(entry).strip().upper()
            for entry in drop
            if isinstance(entry, str)
        }
        if "ALL" in normalised:
            return True
        return capability in normalised

    @staticmethod
    def _format_document_reference(document: Dict[str, Any]) -> Optional[str]:
        kind = document.get("kind")
        metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
        name = metadata.get("name") if isinstance(metadata, dict) else None
        namespace = metadata.get("namespace") if isinstance(metadata, dict) else None
        if not isinstance(kind, str) or not isinstance(name, str):
            return None
        if isinstance(namespace, str) and namespace:
            return f"{kind}/{namespace}/{name}"
        return f"{kind}/{name}"

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
