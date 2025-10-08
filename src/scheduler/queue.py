from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .schedule import EPSILON, PatchCandidate, schedule_patches


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  policy_id TEXT,
  state TEXT,
  attempts INTEGER,
  max_attempts INTEGER,
  enqueued_at REAL,
  last_update REAL,
  risk REAL,
  probability REAL,
  expected_time REAL,
  kev INTEGER,
  wait REAL DEFAULT 0.0
);
"""


@dataclass
class QueueItem:
    id: str
    policy_id: str
    risk: float
    probability: float
    expected_time: float
    kev: bool
    enqueued_at: float
    attempts: int = 0
    max_attempts: int = 3
    state: str = "queued"


def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(DB_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _load_json_array(path: Path) -> List[Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array")
    return data


def _learn_priors(verified: List[dict], det_map: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    counts: Dict[str, Tuple[int, int]] = {}
    for r in verified:
        if not isinstance(r, dict):
            continue
        pid = str(r.get("id"))
        policy = det_map.get(pid, {}).get("policy_id")
        if not isinstance(policy, str):
            continue
        acc = bool(r.get("accepted", False))
        total, succ = counts.get(policy, (0, 0))
        counts[policy] = (total + 1, succ + (1 if acc else 0))
    return {k: (succ / total) if total > 0 else 0.9 for k, (total, succ) in counts.items()}


def _normalise_policy_id(policy: Optional[str]) -> str:
    key = (policy or "").strip().lower()
    mapping = {
        "no_latest_tag": "no_latest_tag",
        "latest-tag": "no_latest_tag",
        "privileged-container": "no_privileged",
        "privilege-escalation-container": "no_privileged",
        "no_privileged": "no_privileged",
        "no-read-only-root-fs": "read_only_root_fs",
        "check-requests-limits": "set_requests_limits",
        "unset-cpu-requirements": "set_requests_limits",
        "unset-memory-requirements": "set_requests_limits",
        "run-as-non-root": "run_as_non_root",
        "check-runasnonroot": "run_as_non_root",
        "hostnetwork": "no_host_network",
        "host-network": "no_host_network",
        "hostpid": "no_host_pid",
        "host-pid": "no_host_pid",
        "hostipc": "no_host_ipc",
        "host-ipc": "no_host_ipc",
        "hostpath": "no_host_path",
        "host-path": "no_host_path",
        "hostpath-volume": "no_host_path",
        "disallow-hostpath": "no_host_path",
        "hostports": "no_host_ports",
        "host-port": "no_host_ports",
        "host-ports": "no_host_ports",
        "disallow-hostports": "no_host_ports",
        "run-as-user": "run_as_user",
        "check-runasuser": "run_as_user",
        "requires-runasuser": "run_as_user",
        "seccomp": "enforce_seccomp",
        "seccomp-profile": "enforce_seccomp",
        "requires-seccomp": "enforce_seccomp",
        "drop-capabilities": "drop_capabilities",
        "linux-capabilities": "drop_capabilities",
        "invalid-capabilities": "drop_capabilities",
        "cap-sys-admin": "drop_cap_sys_admin",
        "sys-admin-capability": "drop_cap_sys_admin",
    }
    return mapping.get(key, key)


def _map_detection_policies(detections: List[dict]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for d in detections:
        if not isinstance(d, dict):
            continue
        mapping[str(d.get("id"))] = {"policy_id": _normalise_policy_id(d.get("policy_id"))}
    return mapping


def enqueue_from_verified(
    db_path: Path,
    verified_path: Path,
    detections_path: Path,
    risk_path: Optional[Path] = None,
) -> int:
    verified = _load_json_array(verified_path)
    detections = _load_json_array(detections_path)
    det_map = _map_detection_policies(detections)
    risk_map: Dict[str, Dict[str, Any]] = {}
    if risk_path and risk_path.exists():
        risk = _load_json_array(risk_path)
        for r in risk:
            if isinstance(r, dict) and "id" in r:
                risk_map[str(r["id"]) ] = r
    now = time.time()
    conn = sqlite3.connect(str(db_path))
    inserted = 0
    try:
        conn.execute(DB_SCHEMA)
        for v in verified:
            if not isinstance(v, dict) or not v.get("accepted", False):
                continue
            vid = str(v.get("id"))
            policy = det_map.get(vid, {}).get("policy_id") or ""
            metrics = risk_map.get(vid, {})
            risk = float(metrics.get("risk", 40.0))
            prob = float(metrics.get("probability", 0.9))
            et = float(metrics.get("expected_time", 10.0))
            kev = 1 if bool(metrics.get("kev", False)) else 0
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO items (id, policy_id, state, attempts, max_attempts, enqueued_at, last_update, risk, probability, expected_time, kev, wait) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (vid, str(policy), "queued", 0, 3, now, now, risk, prob, et, kev, 0.0),
                )
                inserted += 1
            except sqlite3.DatabaseError:
                continue
        conn.commit()
    finally:
        conn.close()
    return inserted


def pick_next(
    db_path: Path,
    *,
    alpha: float = 1.0,
    epsilon: float = EPSILON,
    kev_weight: float = 1.0,
) -> Optional[QueueItem]:
    now = time.time()
    conn = sqlite3.connect(str(db_path))
    try:
        rows = list(conn.execute("SELECT id, policy_id, state, attempts, max_attempts, enqueued_at, last_update, risk, probability, expected_time, kev, wait FROM items WHERE state='queued'"))
    finally:
        conn.close()
    candidates: List[PatchCandidate] = []
    by_id: Dict[str, Tuple] = {}
    for r in rows:
        (_id, policy, _state, attempts, _max_attempts, enq, last_upd, risk, prob, et, kev, wait) = r
        elapsed = max(0.0, now - enq)
        wait_hours = elapsed / 3600.0
        pc = PatchCandidate(
            id=str(_id),
            risk=float(risk),
            probability=float(prob),
            expected_time=float(et),
            wait=float(wait_hours),
            kev=bool(kev),
            explore=0.0,
        )
        candidates.append(pc)
        by_id[str(_id)] = r
    if not candidates:
        return None
    ordered = schedule_patches(candidates, alpha=alpha, epsilon=epsilon, kev_weight=kev_weight)
    top = ordered[0]
    r = by_id[top.id]
    return QueueItem(
        id=top.id,
        policy_id=str(r[1]),
        risk=top.risk,
        probability=top.probability,
        expected_time=top.expected_time,
        kev=top.kev,
        enqueued_at=float(r[5]),
        attempts=int(r[3]),
        max_attempts=int(r[4]),
        state=str(r[2]),
    )




