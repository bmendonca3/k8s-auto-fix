from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .guidance_store import GuidanceStore

_WORD_RE = re.compile(r"[A-Za-z0-9]{3,}")


def _extract_keywords(text: str) -> List[str]:
    return [match.group(0).lower() for match in _WORD_RE.finditer(text or "")]


class GuidanceRetriever:
    def __init__(self, store: GuidanceStore) -> None:
        self._store = store
        self._chunks: Dict[str, List[Tuple[str, set[str]]]] = {}
        self._build_index()

    def _build_index(self) -> None:
        for policy_id in self._store.policies():
            guidance = self._store.render(policy_id)
            if not guidance:
                continue
            pieces = [chunk.strip() for chunk in re.split(r"\n\s*\n", guidance) if chunk.strip()]
            if not pieces:
                pieces = [guidance.strip()]
            self._chunks[policy_id] = [
                (piece, set(_extract_keywords(piece))) for piece in pieces
            ]

    def retrieve(self, policy_id: str, failure_text: Optional[str] = None) -> str:
        base = self._store.render(policy_id)
        if not failure_text:
            return base
        keywords = set(_extract_keywords(failure_text))
        if not keywords:
            return base
        candidates = self._chunks.get(policy_id)
        if not candidates:
            return base
        best_piece = None
        best_score = 0
        for piece, piece_words in candidates:
            score = len(piece_words & keywords)
            if score > best_score:
                best_score = score
                best_piece = piece
        if best_piece and best_score > 0:
            return best_piece
        return base


class FailureCache:
    def __init__(self) -> None:
        self._cache: Dict[str, List[str]] = {}

    def record(self, detection_id: str, message: str, *, max_entries: int = 5) -> None:
        if not detection_id or not message:
            return
        entries = self._cache.setdefault(detection_id, [])
        entries.append(message)
        if len(entries) > max_entries:
            del entries[:-max_entries]

    def lookup(self, detection_id: str, *, join_last: int = 3) -> str:
        entries = self._cache.get(detection_id)
        if not entries:
            return ""
        return "; ".join(entries[-join_last:])

    def clear(self, detection_id: str) -> None:
        if detection_id in self._cache:
            self._cache.pop(detection_id, None)


__all__ = ["GuidanceRetriever", "FailureCache"]
