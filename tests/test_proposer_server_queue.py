import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.proposer.server import app, get_model_client
from src.scheduler.queue import enqueue_from_verified, init_db, pick_next


class _FakeModelClient:
    def request_patch(self, prompt: str):  # noqa: D401 - simple stub
        return "[{\"op\": \"add\", \"path\": \"/spec/containers/0/image\", \"value\": \"nginx:stable\"}]"


class TestProposerServerQueueE2E:
    def setup_method(self) -> None:
        self._original_override = app.dependency_overrides.get(get_model_client)
        app.dependency_overrides[get_model_client] = lambda: _FakeModelClient()

    def teardown_method(self) -> None:
        if self._original_override is not None:
            app.dependency_overrides[get_model_client] = self._original_override
        else:
            app.dependency_overrides.pop(get_model_client, None)

    def test_fastapi_propose_endpoint(self) -> None:
        client = TestClient(app)
        payload = {
            "violation": {"id": "001", "policy_id": "no_latest_tag"},
            "manifest": {"spec": {"containers": [{"image": "nginx:latest"}]}},
        }
        response = client.post("/propose", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["patch"][0]["value"] == "nginx:stable"

    def test_queue_enqueue_and_pick_next(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            db_path = tmp / "queue.db"
            detections_path = tmp / "detections.json"
            verified_path = tmp / "verified.json"
            risk_path = tmp / "risk.json"

            detections = [
                {"id": "01", "policy_id": "no_latest_tag"},
                {"id": "02", "policy_id": "no_privileged"},
            ]
            verified = [
                {"id": "01", "accepted": True},
                {"id": "02", "accepted": True},
            ]
            risk = [
                {"id": "01", "risk": 50.0, "probability": 0.8, "expected_time": 12.0, "kev": False},
                {"id": "02", "risk": 60.0, "probability": 0.7, "expected_time": 15.0, "kev": True},
            ]

            detections_path.write_text(json.dumps(detections), encoding="utf-8")
            verified_path.write_text(json.dumps(verified), encoding="utf-8")
            risk_path.write_text(json.dumps(risk), encoding="utf-8")

            init_db(db_path)
            inserted = enqueue_from_verified(db_path, verified_path, detections_path, risk_path)
            assert inserted == 2

            # ensure KEV-weighted item is selected first
            next_item = pick_next(db_path, kev_weight=5.0)
            assert next_item is not None
            assert next_item.id == "02"

