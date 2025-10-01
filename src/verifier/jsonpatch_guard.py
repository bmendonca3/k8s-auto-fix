from __future__ import annotations

from typing import List

import jsonpatch
import yaml

from src.proposer.guards import PatchError


def validate_paths_exist(base_yaml: str, patch_ops: List[dict]) -> None:
    if base_yaml is None:
        raise PatchError("manifest YAML unavailable for validation")
    documents = list(yaml.safe_load_all(base_yaml))
    if not documents:
        raise PatchError("manifest YAML empty")
    obj = documents[0]
    try:
        jsonpatch.apply_patch(obj, patch_ops, in_place=False)
    except Exception as exc:
        raise PatchError(f"bad path or conflict: {exc}") from exc


__all__ = ["validate_paths_exist"]
