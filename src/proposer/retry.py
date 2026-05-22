from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from src.common.policy_ids import normalise_policy_id

DEFAULT_RETRY_BUDGET_KEY = "default"


def resolve_retry_budget(config: Mapping[str, Any], policy_id: str, fallback: int) -> int:
    """Resolve the attempt budget for a policy, preserving fallback behavior by default."""
    budgets = _retry_budget_config(config)
    if budgets is None:
        return _coerce_positive_int(fallback, "max_attempts")

    normalized_policy = normalise_policy_id(policy_id)
    raw_budget = _lookup_policy_budget(budgets, normalized_policy)
    if raw_budget is None:
        raw_budget = budgets.get(DEFAULT_RETRY_BUDGET_KEY)
    if raw_budget is None:
        return _coerce_positive_int(fallback, "max_attempts")
    return _coerce_positive_int(raw_budget, f"retry budget for {normalized_policy or DEFAULT_RETRY_BUDGET_KEY}")


def _retry_budget_config(config: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    merged: dict[str, Any] = {}
    top_level = config.get("retry_budgets")
    if top_level is not None:
        if not isinstance(top_level, Mapping):
            raise ValueError("retry_budgets must be a mapping")
        merged.update(top_level)

    proposer = config.get("proposer")
    if isinstance(proposer, Mapping):
        nested = proposer.get("retry_budgets")
        if nested is not None:
            if not isinstance(nested, Mapping):
                raise ValueError("proposer.retry_budgets must be a mapping")
            merged.update(nested)

    return merged or None


def _lookup_policy_budget(budgets: Mapping[str, Any], policy_id: str) -> Optional[Any]:
    if policy_id in budgets:
        return budgets[policy_id]
    for key, value in budgets.items():
        if key == DEFAULT_RETRY_BUDGET_KEY:
            continue
        if normalise_policy_id(str(key)) == policy_id:
            return value
    return None


def _coerce_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        budget = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if budget < 1:
        raise ValueError(f"{label} must be a positive integer")
    return budget
