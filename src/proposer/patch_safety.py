from __future__ import annotations

import copy
from typing import Any, Optional

import jsonpatch
import jsonpointer

_MISSING = object()
_COALESCE_PARENT_KEYS = {"resources", "securityContext"}
_PATCH_APPLY_EXCEPTIONS = (jsonpatch.JsonPatchException, jsonpointer.JsonPointerException)


def _rfc6901_escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def _rfc6901_unescape(segment: str) -> str:
    return segment.replace("~1", "/").replace("~0", "~")


def _rfc6901_normalize(segment: str) -> str:
    return _rfc6901_escape(_rfc6901_unescape(segment))


def _decode_percent(value: str) -> str:
    try:
        from urllib.parse import unquote

        return unquote(value)
    except Exception:
        return value


def _document_kind(document: Any) -> str:
    if isinstance(document, dict):
        kind = document.get("kind")
        if isinstance(kind, str):
            return kind
    return ""


def _sanitize_pointer(path: str, document: Any = None) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        return path
    raw = _decode_percent(path)
    parts = raw.split("/")
    anchors: list[list[str]] = [
        ["metadata", "annotations"],
        ["metadata", "labels"],
        ["spec", "template", "metadata", "labels"],
        ["spec", "template", "metadata", "annotations"],
    ]
    if _document_kind(document) == "Service":
        anchors.append(["spec", "selector"])
    else:
        anchors.append(["spec", "selector", "matchLabels"])

    def match_anchor(prefix: list[str]) -> Optional[int]:
        n = len(prefix)
        if len(parts) <= 1 + n:
            return None
        if [p for p in parts[1 : 1 + n]] == prefix:
            return 1 + n
        return None

    join_from = None
    for prefix in anchors:
        idx = match_anchor(prefix)
        if idx is not None:
            join_from = idx
            break
    if join_from is not None and join_from < len(parts):
        head = parts[:join_from]
        tail = parts[join_from:]
        tail_key = "/".join(tail)
        escaped_tail = _rfc6901_normalize(tail_key)
        encoded = "/".join(head + [escaped_tail])
    else:
        escaped = [_rfc6901_normalize(seg) for seg in parts[1:]]
        encoded = "/" + "/".join(escaped)
    return encoded


def sanitize_patch_paths(patch_ops: Any, document: Any = None) -> Any:
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
                op2[key] = _sanitize_pointer(op2[key], document=document)
        out.append(op2)
    return out


def _unescape_pointer_token(token: str) -> str:
    return _rfc6901_unescape(token)


def _resolve_pointer(document: Any, path: str) -> Any:
    if path in {"", "/"}:
        return document
    current = document
    for raw_token in path.strip("/").split("/"):
        token = _unescape_pointer_token(raw_token)
        if isinstance(current, list):
            if not token.isdigit():
                return _MISSING
            index = int(token)
            if index >= len(current):
                return _MISSING
            current = current[index]
        elif isinstance(current, dict):
            if token not in current:
                return _MISSING
            current = current[token]
        else:
            return _MISSING
    return current


def _candidate_parent_paths(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/"):
        return []
    tokens = path.strip("/").split("/")
    parents: list[str] = []
    for index, token in enumerate(tokens):
        if token in _COALESCE_PARENT_KEYS:
            parents.append("/" + "/".join(tokens[: index + 1]))
    return parents


def _op_targets_parent(op: Any, parent_path: str) -> bool:
    if not isinstance(op, dict):
        return False
    path = op.get("path")
    return isinstance(path, str) and (path == parent_path or path.startswith(parent_path + "/"))


def _coalesce_parent_ops(document: Any, patch_ops: list[Any], final_document: Any) -> list[Any]:
    candidate = list(patch_ops)
    parent_paths = {
        parent
        for op in candidate
        if isinstance(op, dict)
        for parent in _candidate_parent_paths(op.get("path", ""))
    }

    for parent_path in sorted(parent_paths, key=lambda item: item.count("/"), reverse=True):
        affected_indexes = [
            index for index, op in enumerate(candidate) if _op_targets_parent(op, parent_path)
        ]
        if len(affected_indexes) < 2:
            continue
        affected_ops = [candidate[index] for index in affected_indexes]
        if any(not isinstance(op, dict) for op in affected_ops):
            continue
        if any(op.get("op") not in {"add", "replace", "remove"} or "from" in op for op in affected_ops):
            continue

        final_value = _resolve_pointer(final_document, parent_path)
        if final_value is _MISSING:
            continue
        original_value = _resolve_pointer(document, parent_path)
        replacement = {
            "op": "replace" if original_value is not _MISSING else "add",
            "path": parent_path,
            "value": copy.deepcopy(final_value),
        }
        first_index = affected_indexes[0]
        affected_set = set(affected_indexes)
        replacement_candidate = [
            replacement if index == first_index else op
            for index, op in enumerate(candidate)
            if index == first_index or index not in affected_set
        ]
        try:
            candidate_document = jsonpatch.apply_patch(
                copy.deepcopy(document), replacement_candidate, in_place=False
            )
        except _PATCH_APPLY_EXCEPTIONS:
            continue
        if candidate_document == final_document and len(replacement_candidate) < len(candidate):
            candidate = replacement_candidate
    return candidate


def minimize_redundant_patch_ops(document: Any, patch_ops: Any) -> Any:
    """Drop patch operations that do not affect the final patched document."""
    if not isinstance(patch_ops, list):
        return patch_ops
    try:
        final_document = jsonpatch.apply_patch(copy.deepcopy(document), patch_ops, in_place=False)
    except _PATCH_APPLY_EXCEPTIONS:
        return patch_ops

    minimized = list(patch_ops)
    for index in reversed(range(len(minimized))):
        candidate = minimized[:index] + minimized[index + 1 :]
        try:
            candidate_document = jsonpatch.apply_patch(copy.deepcopy(document), candidate, in_place=False)
        except _PATCH_APPLY_EXCEPTIONS:
            continue
        if candidate_document == final_document:
            minimized = candidate
    coalesced = _coalesce_parent_ops(document, minimized, final_document)
    if len(coalesced) < len(minimized):
        minimized = minimize_redundant_patch_ops(document, coalesced)
    return minimized


__all__ = ["minimize_redundant_patch_ops", "sanitize_patch_paths"]
