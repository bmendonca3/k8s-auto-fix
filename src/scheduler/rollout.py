from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Optional

_COLLECTION_FIELDS = ("ids", "policies", "namespaces", "owners", "root_causes")
_SCALAR_FIELDS = ("id", "group_by", "group_key")


def annotate_rollout_batches(
    batches: Iterable[Mapping[str, object] | object],
    *,
    change_windows: Optional[Mapping[str, Mapping[str, object]]] = None,
    default_window: str = "standard",
    max_count: Optional[int] = None,
    max_total_risk: Optional[float] = None,
    max_namespaces: Optional[int] = None,
    max_policies: Optional[int] = None,
) -> list[dict[str, object]]:
    """Return batch summaries annotated for rollout change-window planning."""
    _validate_limit("max_count", max_count)
    _validate_limit("max_namespaces", max_namespaces)
    _validate_limit("max_policies", max_policies)
    if max_total_risk is not None and max_total_risk < 0:
        raise ValueError("max_total_risk must be non-negative")

    annotated = []
    for batch in batches:
        summary = _summary_to_dict(batch)
        reasons = _blast_radius_reasons(
            summary,
            max_count=max_count,
            max_total_risk=max_total_risk,
            max_namespaces=max_namespaces,
            max_policies=max_policies,
        )
        summary["change_window"] = _select_change_window(
            summary,
            change_windows=change_windows,
            default_window=default_window,
        )
        summary["blast_radius"] = {
            "count": _int_value(summary.get("count")),
            "total_risk": _float_value(summary.get("total_risk")),
            "namespace_count": len(summary["namespaces"]),
            "policy_count": len(summary["policies"]),
            "owner_count": len(summary["owners"]),
        }
        summary["rollout_allowed"] = not reasons
        summary["rollout_reasons"] = reasons
        annotated.append(summary)
    return annotated


def filter_rollout_batches(
    batches: Iterable[Mapping[str, object] | object],
    **kwargs: object,
) -> list[dict[str, object]]:
    """Return only rollout-allowed annotated batch summaries."""
    return [
        batch
        for batch in annotate_rollout_batches(batches, **kwargs)
        if batch["rollout_allowed"]
    ]


def _summary_to_dict(batch: Mapping[str, object] | object) -> dict[str, object]:
    if isinstance(batch, Mapping):
        source = dict(batch)
    else:
        to_dict = getattr(batch, "to_dict", None)
        if not callable(to_dict):
            raise TypeError("batch summaries must be mappings or expose to_dict()")
        source = dict(to_dict())

    summary: dict[str, object] = {}
    for field in _SCALAR_FIELDS:
        summary[field] = _clean_string(source.get(field, ""))
    for field in _COLLECTION_FIELDS:
        values = _string_list(source.get(field))
        summary[field] = values if field == "ids" else _sorted_unique(values)
    summary["count"] = _int_value(source.get("count", len(summary["ids"])))
    summary["total_risk"] = _float_value(source.get("total_risk", 0.0))
    summary["max_score"] = _float_value(source.get("max_score", 0.0))
    return summary


def _select_change_window(
    summary: Mapping[str, object],
    *,
    change_windows: Optional[Mapping[str, Mapping[str, object]]],
    default_window: str,
) -> str:
    if not change_windows:
        return default_window

    for window in sorted(change_windows):
        if _matches_window(summary, change_windows[window]):
            return window
    return default_window


def _matches_window(
    summary: Mapping[str, object],
    criteria: Mapping[str, object],
) -> bool:
    for field, expected in criteria.items():
        if field in _COLLECTION_FIELDS:
            actual_values = set(_string_list(summary.get(field)))
            expected_values = set(_string_list(expected))
            if not actual_values.intersection(expected_values):
                return False
        elif _clean_string(summary.get(field)) != _clean_string(expected):
            return False
    return True


def _blast_radius_reasons(
    summary: Mapping[str, object],
    *,
    max_count: Optional[int],
    max_total_risk: Optional[float],
    max_namespaces: Optional[int],
    max_policies: Optional[int],
) -> list[str]:
    reasons = []
    count = _int_value(summary.get("count"))
    total_risk = _float_value(summary.get("total_risk"))
    namespace_count = len(_string_list(summary.get("namespaces")))
    policy_count = len(_string_list(summary.get("policies")))

    if max_count is not None and count > max_count:
        reasons.append(f"count>{max_count}")
    if max_total_risk is not None and total_risk > max_total_risk:
        reasons.append(f"total_risk>{max_total_risk:g}")
    if max_namespaces is not None and namespace_count > max_namespaces:
        reasons.append(f"namespaces>{max_namespaces}")
    if max_policies is not None and policy_count > max_policies:
        reasons.append(f"policies>{max_policies}")
    return reasons


def _validate_limit(name: str, value: Optional[int]) -> None:
    if value is not None and value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = _clean_string(value)
        return [cleaned] if cleaned else []
    if isinstance(value, Iterable):
        result = []
        for item in value:
            cleaned = _clean_string(item)
            if cleaned:
                result.append(cleaned)
        return result
    cleaned = _clean_string(value)
    return [cleaned] if cleaned else []


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def _clean_string(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _int_value(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _float_value(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


__all__ = ["annotate_rollout_batches", "filter_rollout_batches"]
