from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

CACHE_VERSION = 1


@dataclass(frozen=True)
class ResponseCacheMetadata:
    key: str
    input_hash: str
    config_hash: str


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_response_cache_metadata(
    *,
    detection: Dict[str, Any],
    generator_config: Dict[str, Any],
    prompt: str,
) -> ResponseCacheMetadata:
    input_payload: Dict[str, Any] = {
        "policy_id": detection.get("policy_id"),
        "manifest_yaml": detection.get("manifest_yaml"),
        "violation_text": detection.get("violation_text"),
        "prompt_hash": stable_hash({"prompt": prompt}),
    }
    retry_feedback = detection.get("retry_feedback")
    if isinstance(retry_feedback, str) and retry_feedback.strip():
        input_payload["retry_feedback"] = retry_feedback.strip()

    input_hash = stable_hash(input_payload)
    config_hash = stable_hash(generator_config)
    key = stable_hash(
        {
            "cache_version": CACHE_VERSION,
            "input": input_payload,
            "generator": generator_config,
        }
    )
    return ResponseCacheMetadata(key=key, input_hash=input_hash, config_hash=config_hash)


class ModelResponseCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def read(self, metadata: ResponseCacheMetadata) -> Optional[Dict[str, Any]]:
        path = self.path_for(metadata.key)
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("cache_version") != CACHE_VERSION:
            return None
        if payload.get("cache_key") != metadata.key:
            return None
        if "raw_response" not in payload:
            return None
        return payload

    def write(
        self,
        metadata: ResponseCacheMetadata,
        *,
        raw_response: Any,
        usage: Optional[Dict[str, Any]] = None,
    ) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(metadata.key)
        payload = {
            "cache_version": CACHE_VERSION,
            "cache_key": metadata.key,
            "input_hash": metadata.input_hash,
            "config_hash": metadata.config_hash,
            "raw_response": raw_response,
            "usage": usage if isinstance(usage, dict) else {},
        }
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(path)
        return path

    def record_fields(self, metadata: ResponseCacheMetadata, *, cache_hit: bool) -> Dict[str, Any]:
        return {
            "cache_hit": cache_hit,
            "cache_key": metadata.key,
            "cache_path": str(self.path_for(metadata.key)),
            "cache_input_hash": metadata.input_hash,
            "cache_config_hash": metadata.config_hash,
        }
