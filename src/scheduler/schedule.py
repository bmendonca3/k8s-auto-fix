from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence

EPSILON = 1e-6


@dataclass
class PatchCandidate:
    id: str
    risk: float
    probability: float
    expected_time: float
    wait: float = 0.0
    kev: bool = False
    explore: float = 0.0

    def score(self, alpha: float = 1.0, epsilon: float = EPSILON, kev_weight: float = 1.0) -> float:
        denominator = max(self.expected_time, epsilon)
        kev_value = kev_weight if self.kev else 0.0
        return (self.risk * self.probability) / denominator + self.explore + alpha * self.wait + kev_value

    def to_output(self, alpha: float, epsilon: float) -> dict:
        return {
            "id": self.id,
            "score": round(self.score(alpha=alpha, epsilon=epsilon), 6),
            "R": self.risk,
            "p": self.probability,
            "Et": self.expected_time,
            "wait": self.wait,
            "kev": bool(self.kev),
        }


def schedule_patches(
    patches: Sequence[PatchCandidate | Mapping[str, object]],
    *,
    alpha: float = 1.0,
    epsilon: float = EPSILON,
    kev_weight: float = 1.0,
) -> List[PatchCandidate]:
    candidates = [
        patch if isinstance(patch, PatchCandidate) else _coerce_patch_candidate(patch)
        for patch in patches
    ]
    return sorted(
        candidates,
        key=lambda candidate: candidate.score(alpha=alpha, epsilon=epsilon, kev_weight=kev_weight),
        reverse=True,
    )


def _coerce_patch_candidate(data: Mapping[str, object]) -> PatchCandidate:
    required = {"id", "risk", "probability", "expected_time"}
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Patch candidate missing required field(s): {', '.join(missing)}")
    return PatchCandidate(
        id=str(data["id"]),
        risk=float(data["risk"]),
        probability=float(data["probability"]),
        expected_time=float(data["expected_time"]),
        wait=float(data.get("wait", 0.0)),
        kev=bool(data.get("kev", False)),
        explore=float(data.get("explore", 0.0)),
    )


__all__ = ["PatchCandidate", "schedule_patches"]
