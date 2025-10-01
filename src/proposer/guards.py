from __future__ import annotations

import json
import re
from typing import Any, Dict, List


class PatchError(Exception):
    """Raised when the model returns an invalid patch."""


_VALID_OPS = {"add", "remove", "replace", "move", "copy", "test"}
_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json_array(text: str) -> List[Dict[str, Any]]:
    """Extract a JSON array from model text ensuring RFC6902 structure."""

    if text is None:
        raise PatchError("no content returned")
    stripped = text.strip()
    if not stripped:
        raise PatchError("empty response")

    stripped = _CODE_FENCE_PATTERN.sub("", stripped)
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start < 0 or end <= start:
        raise PatchError("no top-level JSON array")

    payload = stripped[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PatchError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise PatchError("top level not array")

    for op in data:
        if not isinstance(op, dict):
            raise PatchError("non-object operation")
        operation = op.get("op")
        if operation not in _VALID_OPS:
            raise PatchError("invalid op")
        if "path" not in op or not isinstance(op["path"], str):
            raise PatchError("missing path")
    return data


__all__ = ["PatchError", "extract_json_array"]
