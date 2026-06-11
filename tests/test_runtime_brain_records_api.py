from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from core.brain.schema import BrainRecord
from core.main import app


def _record(payload: dict) -> BrainRecord:
    return BrainRecord.model_validate(payload)


def test_runtime_brain_records_list_filters_by_layer(monkeypatch: MonkeyPatch) -> None:
    focus = _record(
        {
            "record_id": "XV7-FOCUS-0005",
            "layer": "active_focus",
            "title": "Focus",
            "summary": "Focus summary",
            "body": "Focus body",
            "status": "active",
            "priority": 300,
            "tags": ["focus"],
            "facts": [],
            "evidence": [],
        }
    )
    knowledge = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0006",
            "layer": "knowledge",
            "title": "Knowledge",
            "summary": "Knowledge summary",
            "body": "Knowledge body",
            "status": "active",
            "priority": 200,
            "tags": ["knowledge"],
            "facts": [],
            "evidence": [],
        }
    )

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.load_records_with_source",
        lambda: [
            (focus, "runtime_override", Path("runtime/focus.json")),
            (knowledge, "seed", Path("seed/knowledge.json")),
        ],
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.record_updated_at",
        lambda _path: "2026-06-11T00:00:00Z",
    )

    client = TestClient(app)
    response = client.get("/runtime/brain/records?layer=active_focus")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["records"][0]["record_id"] == "XV7-FOCUS-0005"
    assert payload["records"][0]["source"] == "runtime_override"


def test_runtime_brain_record_mutations_require_api_key(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)

    client = TestClient(app)

    put_response = client.put(
        "/runtime/brain/records/XV7-FOCUS-0005",
        json={"title": "Updated"},
    )
    deactivate_response = client.post(
        "/runtime/brain/records/XV7-FOCUS-0005/deactivate"
    )
    activate_response = client.post("/runtime/brain/records/XV7-FOCUS-0005/set-active")

    assert put_response.status_code == 401
    assert deactivate_response.status_code == 401
    assert activate_response.status_code == 401


def test_runtime_brain_record_update_creates_runtime_override(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)

    current = _record(
        {
            "record_id": "XV7-FOCUS-0005",
            "layer": "active_focus",
            "title": "Old title",
            "summary": "Old summary",
            "body": "Old body",
            "status": "active",
            "priority": 300,
            "tags": ["focus"],
            "facts": [],
            "evidence": [],
        }
    )

    store = {"record": current}

    def fake_get_record_with_source(_record_id: str):
        return (
            store["record"],
            "runtime_override",
            Path("runtime/XV7-FOCUS-0005.json"),
        )

    def fake_save_runtime_override(record: BrainRecord) -> BrainRecord:
        store["record"] = record
        return record

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.get_record_with_source",
        fake_get_record_with_source,
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.save_runtime_override",
        fake_save_runtime_override,
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.record_updated_at",
        lambda _path: "2026-06-11T00:00:00Z",
    )

    client = TestClient(app)
    response = client.put(
        "/runtime/brain/records/XV7-FOCUS-0005",
        json={
            "layer": "active_focus",
            "title": "New focus title",
            "body": "New focus body for runtime override testing",
            "tags": ["focus", "runtime"],
            "status": "active",
        },
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["record_id"] == "XV7-FOCUS-0005"
    assert payload["title"] == "New focus title"
    assert payload["source"] == "runtime_override"
    assert payload["body"] == "New focus body for runtime override testing"
