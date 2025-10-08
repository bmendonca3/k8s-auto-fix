from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


def _default_index_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "policy_guidance" / "index.json"


def _normalise_policy_id(policy: str) -> str:
    key = (policy or "").strip().lower()
    mapping = {
        "latest-tag": "no_latest_tag",
        "no-privileged": "no_privileged",
        "privilege-escalation-container": "no_privileged",
        "privileged-container": "no_privileged",
        "no-read-only-root-fs": "read_only_root_fs",
        "check-requests-limits": "set_requests_limits",
        "unset-cpu-requirements": "set_requests_limits",
        "unset-memory-requirements": "set_requests_limits",
        "run-as-non-root": "run_as_non_root",
        "check-runasnonroot": "run_as_non_root",
        "run-as-user": "run_as_user",
        "check-runasuser": "run_as_user",
        "requires-runasuser": "run_as_user",
        "seccomp": "enforce_seccomp",
        "seccomp-profile": "enforce_seccomp",
        "requires-seccomp": "enforce_seccomp",
        "env-var-secret": "env_var_secret",
        "envvar-secret": "env_var_secret",
        "host-path": "no_host_path",
        "hostpath": "no_host_path",
        "hostports": "no_host_ports",
        "host-port": "no_host_ports",
        "host-ports": "no_host_ports",
    }
    return mapping.get(key, key)


@dataclass(frozen=True)
class GuidanceSnippet:
    text: str
    source: str
    citation: str

    def render(self) -> str:
        citation_bits = []
        if self.source:
            citation_bits.append(self.source)
        if self.citation:
            citation_bits.append(self.citation)
        citation_text = " | ".join(citation_bits)
        if citation_text:
            return f"{self.text}\n[Source: {citation_text}]"
        return self.text


class GuidanceStore:
    def __init__(self, entries: Dict[str, List[GuidanceSnippet]]) -> None:
        self._entries = entries

    @classmethod
    def default(cls) -> "GuidanceStore":
        index_path = _default_index_path()
        if not index_path.exists():
            return cls({})
        try:
            with index_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return cls({})
        entries: Dict[str, List[GuidanceSnippet]] = {}
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            policies = item.get("policies") or []
            text = item.get("text")
            if not text or not isinstance(text, str):
                continue
            snippet = GuidanceSnippet(
                text=text.strip(),
                source=str(item.get("source") or "").strip(),
                citation=str(item.get("citation") or "").strip(),
            )
            for policy in policies:
                norm = _normalise_policy_id(str(policy))
                entries.setdefault(norm, []).append(snippet)
        return cls(entries)

    def lookup(self, policy_id: str) -> List[GuidanceSnippet]:
        if not policy_id:
            return []
        norm = _normalise_policy_id(policy_id)
        return list(self._entries.get(norm, []))

    def render(self, policy_id: str) -> str:
        snippets = self.lookup(policy_id)
        if not snippets:
            return ""
        return "\n\n".join(snippet.render() for snippet in snippets)


__all__ = ["GuidanceStore", "GuidanceSnippet"]
