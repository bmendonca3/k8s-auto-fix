from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Optional

UNKNOWN_GROUP = "unknown"

_GROUP_FIELDS = {
    "namespace": ("namespace",),
    "owner": ("owner", "team"),
    "policy_id": ("policy_id", "policy"),
    "root_cause": ("root_cause", "rootCause", "cause"),
    "team": ("team", "owner"),
}

_GROUP_ALIASES = {
    "namespace": "namespace",
    "owner": "owner",
    "owner/team": "owner",
    "owner_team": "owner",
    "policy": "policy_id",
    "policy-id": "policy_id",
    "policy_id": "policy_id",
    "root_cause": "root_cause",
    "root-cause": "root_cause",
    "team": "team",
    "team/owner": "owner",
    "team_owner": "owner",
}


@dataclass(frozen=True)
class BatchSummary:
    id: str
    group_by: str
    group_key: str
    ids: tuple[str, ...]
    count: int
    total_risk: float
    max_score: float
    policies: tuple[str, ...]
    namespaces: tuple[str, ...]
    owners: tuple[str, ...]
    root_causes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "group_by": self.group_by,
            "group_key": self.group_key,
            "ids": list(self.ids),
            "count": self.count,
            "total_risk": self.total_risk,
            "max_score": self.max_score,
            "policies": list(self.policies),
            "namespaces": list(self.namespaces),
            "owners": list(self.owners),
            "root_causes": list(self.root_causes),
        }


@dataclass(frozen=True)
class _Candidate:
    id: str
    score: float
    risk: float
    policy_id: Optional[str]
    namespace: Optional[str]
    owner: Optional[str]
    team: Optional[str]
    root_cause: Optional[str]
    group_key: str


def schedule_batches(
    candidates: Iterable[Mapping[str, object]],
    *,
    group_by: str,
    metadata: Optional[
        Iterable[Mapping[str, object]] | Mapping[str, Mapping[str, object]]
    ] = None,
    max_batch_size: Optional[int] = None,
) -> list[BatchSummary]:
    """Group schedule candidates into deterministic batch summaries."""
    canonical_group = _normalise_group_by(group_by)
    if max_batch_size is not None and max_batch_size < 1:
        raise ValueError("max_batch_size must be a positive integer")

    metadata_by_id = _metadata_by_id(metadata)
    groups: dict[str, list[_Candidate]] = {}

    for candidate in candidates:
        record = _merge_metadata(candidate, metadata_by_id)
        batch_candidate = _coerce_candidate(record, canonical_group)
        groups.setdefault(batch_candidate.group_key, []).append(batch_candidate)

    batch_items: list[tuple[int, BatchSummary]] = []
    for group_key, group_candidates in groups.items():
        ordered_candidates = sorted(
            group_candidates,
            key=lambda item: (-item.score, item.id),
        )
        chunks = _split_candidates(ordered_candidates, max_batch_size)
        for part_index, chunk in enumerate(chunks, start=1):
            batch_items.append(
                (
                    part_index,
                    _summarise_chunk(
                        canonical_group,
                        group_key,
                        chunk,
                        part_index=part_index,
                        part_count=len(chunks),
                    ),
                )
            )

    return [
        summary
        for _part_index, summary in sorted(
            batch_items,
            key=lambda item: (-item[1].max_score, item[1].group_key, item[0]),
        )
    ]


def _normalise_group_by(group_by: str) -> str:
    key = str(group_by).strip().lower().replace(" ", "_")
    try:
        return _GROUP_ALIASES[key]
    except KeyError as exc:
        allowed = ", ".join(sorted(_GROUP_ALIASES))
        raise ValueError(f"group_by must be one of: {allowed}") from exc


def _metadata_by_id(
    metadata: Optional[
        Iterable[Mapping[str, object]] | Mapping[str, Mapping[str, object]]
    ],
) -> dict[str, dict[str, object]]:
    if metadata is None:
        return {}

    if isinstance(metadata, Mapping):
        if "id" in metadata:
            metadata_id = _clean_string(_lookup(metadata, "id"))
            return {metadata_id: dict(metadata)} if metadata_id else {}

        result: dict[str, dict[str, object]] = {}
        for metadata_id, record in metadata.items():
            if not isinstance(record, Mapping):
                continue
            record_copy = dict(record)
            record_copy.setdefault("id", str(metadata_id))
            result[str(metadata_id)] = record_copy
        return result

    result = {}
    for record in metadata:
        if not isinstance(record, Mapping):
            continue
        metadata_id = _clean_string(_lookup(record, "id"))
        if metadata_id:
            result[metadata_id] = dict(record)
    return result


def _merge_metadata(
    candidate: Mapping[str, object],
    metadata_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if not isinstance(candidate, Mapping):
        raise TypeError("candidates must be mapping records")
    candidate_id = _clean_string(_lookup(candidate, "id"))
    if not candidate_id:
        raise ValueError("schedule candidate missing required field: id")

    merged = dict(metadata_by_id.get(candidate_id, {}))
    for key, value in candidate.items():
        if _is_blank(value) and key in merged:
            continue
        merged[key] = value
    merged["id"] = candidate_id
    return merged


def _coerce_candidate(record: Mapping[str, object], group_by: str) -> _Candidate:
    candidate_id = _clean_string(_lookup(record, "id"))
    if not candidate_id:
        raise ValueError("schedule candidate missing required field: id")

    risk = _number_from(record, ("risk", "R"), default=0.0, candidate_id=candidate_id)
    score = _number_from(record, ("score",), default=risk, candidate_id=candidate_id)
    policy_id = _first_string(record, ("policy_id", "policy"))
    namespace = _first_string(record, ("namespace",))
    owner = _first_string(record, ("owner",))
    team = _first_string(record, ("team",))
    root_cause = _first_string(record, ("root_cause", "rootCause", "cause"))
    group_key = _first_string(record, _GROUP_FIELDS[group_by]) or UNKNOWN_GROUP

    return _Candidate(
        id=candidate_id,
        score=score,
        risk=risk,
        policy_id=policy_id,
        namespace=namespace,
        owner=owner,
        team=team,
        root_cause=root_cause,
        group_key=group_key,
    )


def _summarise_chunk(
    group_by: str,
    group_key: str,
    candidates: list[_Candidate],
    *,
    part_index: int,
    part_count: int,
) -> BatchSummary:
    batch_id = f"{group_by}:{group_key}"
    if part_count > 1:
        batch_id = f"{batch_id}:{part_index}"

    return BatchSummary(
        id=batch_id,
        group_by=group_by,
        group_key=group_key,
        ids=tuple(candidate.id for candidate in candidates),
        count=len(candidates),
        total_risk=round(sum(candidate.risk for candidate in candidates), 6),
        max_score=round(max(candidate.score for candidate in candidates), 6),
        policies=_sorted_unique(candidate.policy_id for candidate in candidates),
        namespaces=_sorted_unique(candidate.namespace for candidate in candidates),
        owners=_sorted_unique(
            owner
            for candidate in candidates
            for owner in (candidate.owner, candidate.team)
        ),
        root_causes=_sorted_unique(candidate.root_cause for candidate in candidates),
    )


def _split_candidates(
    candidates: list[_Candidate],
    max_batch_size: Optional[int],
) -> list[list[_Candidate]]:
    if max_batch_size is None:
        return [candidates]
    return [
        candidates[index : index + max_batch_size]
        for index in range(0, len(candidates), max_batch_size)
    ]


def _number_from(
    record: Mapping[str, object],
    fields: tuple[str, ...],
    *,
    default: float,
    candidate_id: str,
) -> float:
    for field in fields:
        value = _lookup(record, field)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"schedule candidate {candidate_id!r} has non-numeric {field}: {value!r}"
            ) from exc
    return default


def _first_string(record: Mapping[str, object], fields: tuple[str, ...]) -> Optional[str]:
    for field in fields:
        value = _clean_string(_lookup(record, field))
        if value:
            return value
    return None


def _lookup(record: Mapping[str, object], field: str) -> object:
    if field in record:
        return record[field]
    nested_metadata = record.get("metadata")
    if isinstance(nested_metadata, Mapping):
        return nested_metadata.get(field)
    return None


def _clean_string(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return str(value)


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _sorted_unique(values: Iterable[Optional[str]]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))


__all__ = ["BatchSummary", "UNKNOWN_GROUP", "schedule_batches"]
