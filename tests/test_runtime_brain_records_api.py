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


def test_runtime_brain_records_pending_learned_filters(
    monkeypatch: MonkeyPatch,
) -> None:
    pending_learned = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0007",
            "layer": "knowledge",
            "title": "Require evidence for build claims",
            "summary": "Need proof before claiming build status.",
            "body": "Learned diagnostic rule for evidence-first status claims.",
            "status": "pending_review",
            "priority": 180,
            "tags": ["learned-rule", "proof-required", "diagnostic-rule"],
            "facts": [],
            "evidence": [],
        }
    )
    active_non_learned = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0008",
            "layer": "knowledge",
            "title": "Seed knowledge",
            "summary": "Normal seed knowledge.",
            "body": "Seed knowledge body.",
            "status": "active",
            "priority": 120,
            "tags": ["knowledge"],
            "facts": [],
            "evidence": [],
        }
    )

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.load_records_with_source",
        lambda: [
            (
                pending_learned,
                "runtime_override",
                Path("runtime/XV7-KNOWLEDGE-0007.json"),
            ),
            (active_non_learned, "seed", Path("seed/XV7-KNOWLEDGE-0008.json")),
        ],
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.record_updated_at",
        lambda _path: "2026-06-11T00:00:00Z",
    )

    client = TestClient(app)
    response = client.get(
        "/runtime/brain/records?include_archived=true&pending_only=true&learned_only=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["records"][0]["record_id"] == "XV7-KNOWLEDGE-0007"
    assert payload["records"][0]["status"] == "pending_review"


def test_runtime_brain_record_approve_and_reject(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)

    pending = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0009",
            "layer": "knowledge",
            "title": "Pending learned rule",
            "summary": "Pending learned summary",
            "body": "Pending learned body",
            "status": "pending_review",
            "priority": 160,
            "tags": ["learned-rule"],
            "facts": [],
            "evidence": [],
        }
    )

    archived = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0010",
            "layer": "knowledge",
            "title": "Pending learned rule to reject",
            "summary": "Reject me",
            "body": "Reject body",
            "status": "pending_review",
            "priority": 160,
            "tags": ["learned-rule"],
            "facts": [],
            "evidence": [],
        }
    )

    state = {
        pending.record_id: pending,
        archived.record_id: archived,
    }

    def fake_approve(record_id: str) -> BrainRecord:
        current = state[record_id]
        updated = current.model_copy(update={"status": "active"})
        state[record_id] = updated
        return updated

    def fake_reject(record_id: str) -> BrainRecord:
        current = state[record_id]
        updated = current.model_copy(update={"status": "archived"})
        state[record_id] = updated
        return updated

    def fake_get_record_with_source(record_id: str):
        record = state[record_id]
        return (
            record,
            "runtime_override",
            Path(f"runtime/{record_id}.json"),
        )

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.approve_record",
        fake_approve,
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.reject_record",
        fake_reject,
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.get_record_with_source",
        fake_get_record_with_source,
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.record_updated_at",
        lambda _path: "2026-06-11T00:00:00Z",
    )

    client = TestClient(app)

    approve_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0009/approve",
        headers={"X-XV7-API-Key": "test-secret"},
    )
    reject_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0010/reject",
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "active"
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "archived"


def test_runtime_brain_records_relevance_filters_and_effective_state(
    monkeypatch: MonkeyPatch,
) -> None:
    current = _record(
        {
            "record_id": "XV7-MEMORY-0101",
            "layer": "memory",
            "title": "Current runtime rule",
            "summary": "Use concise status answers.",
            "body": "Current operational rule.",
            "status": "active",
            "relevance_state": "current",
            "priority": 200,
            "tags": ["runtime"],
            "facts": [],
            "evidence": [],
        }
    )
    needs_review = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0102",
            "layer": "knowledge",
            "title": "B7 milestone completed and still says must enforce",
            "summary": "B7 completed milestone should be split for current behavior.",
            "body": "B7 completed and shipped, but from now on must enforce proof.",
            "status": "active",
            "relevance_state": "current",
            "priority": 160,
            "tags": ["learned-rule"],
            "facts": [],
            "evidence": [],
        }
    )
    historical = _record(
        {
            "record_id": "XV7-VERIFIED-0103",
            "layer": "verified_status",
            "title": "Old verified milestone",
            "summary": "B6 passed and completed.",
            "body": "B6 milestone completed and done.",
            "status": "archived",
            "relevance_state": "historical",
            "priority": 80,
            "tags": ["seed"],
            "facts": [],
            "evidence": [],
        }
    )

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.load_records_with_source",
        lambda: [
            (current, "runtime_override", Path("runtime/XV7-MEMORY-0101.json")),
            (needs_review, "seed", Path("seed/XV7-KNOWLEDGE-0102.json")),
            (historical, "seed", Path("seed/XV7-VERIFIED-0103.json")),
        ],
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.record_updated_at",
        lambda _path: "2026-06-11T00:00:00Z",
    )

    client = TestClient(app)

    review_response = client.get("/runtime/brain/records?review_only=true")
    assert review_response.status_code == 200
    review_payload = review_response.json()
    review_ids = {item["record_id"] for item in review_payload["records"]}
    assert "XV7-KNOWLEDGE-0102" in review_ids
    needs_review_item = next(
        item
        for item in review_payload["records"]
        if item["record_id"] == "XV7-KNOWLEDGE-0102"
    )
    assert needs_review_item["effective_relevance_state"] == "needs_review"

    history_response = client.get("/runtime/brain/records?history_only=true")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["count"] == 1
    assert history_payload["records"][0]["record_id"] == "XV7-VERIFIED-0103"
    assert history_payload["records"][0]["effective_relevance_state"] == "historical"


def test_runtime_brain_records_review_and_history_use_computed_hygiene(
    monkeypatch: MonkeyPatch,
) -> None:
    seed_verified = _record(
        {
            "record_id": "XV7-VERIFIED-0991",
            "layer": "verified_status",
            "title": "Verified milestones and current phase status",
            "summary": "Verified: B9.5/B9.7 passed; current in progress B9.8 bridge.",
            "body": "Proven: B3.2 passed. Proven: B9.7 passed. Current in progress: B9.8 local bridge behavior.",
            "status": "active",
            "priority": 210,
            "tags": ["verified", "b3.2", "b9.7", "b9.8"],
            "facts": [],
            "evidence": [],
        }
    )
    pending = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0992",
            "layer": "knowledge",
            "title": "Pending item",
            "summary": "Awaiting review",
            "body": "Pending review body.",
            "status": "pending_review",
            "priority": 120,
            "tags": ["learned-rule"],
            "facts": [],
            "evidence": [],
        }
    )

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.load_records_with_source",
        lambda: [
            (seed_verified, "seed", Path("seed/XV7-VERIFIED-0991.json")),
            (pending, "runtime_override", Path("runtime/XV7-KNOWLEDGE-0992.json")),
        ],
    )
    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.record_updated_at",
        lambda _path: "2026-06-11T00:00:00Z",
    )

    client = TestClient(app)

    review_response = client.get("/runtime/brain/records?review_only=true")
    assert review_response.status_code == 200
    review_payload = review_response.json()
    review_ids = {item["record_id"] for item in review_payload["records"]}
    assert "XV7-KNOWLEDGE-0992" in review_ids
    assert "XV7-VERIFIED-0991" in review_ids

    seed_review = next(
        item
        for item in review_payload["records"]
        if item["record_id"] == "XV7-VERIFIED-0991"
    )
    assert seed_review["effective_relevance_state"] == "needs_review"
    assert "mixed_historical_and_current" in set(seed_review["hygiene_flags"])
    recommendation_types = {
        str(item.get("type", "")) for item in seed_review["hygiene_recommendations"]
    }
    assert (
        "split_record" in recommendation_types
        or "mark_historical_via_runtime_override" in recommendation_types
    )


def test_runtime_brain_record_relevance_actions_and_apply_recommendation(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)

    seed = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0201",
            "layer": "knowledge",
            "title": "Mixed record",
            "summary": "B7 completed and from now on do this.",
            "body": "B7 completed, from now on enforce proof.",
            "status": "active",
            "relevance_state": "current",
            "priority": 170,
            "tags": ["learned-rule"],
            "facts": [],
            "evidence": [],
        }
    )

    state = {"record": seed}

    def fake_get_record_with_source(_record_id: str):
        return (
            state["record"],
            "runtime_override",
            Path("runtime/XV7-KNOWLEDGE-0201.json"),
        )

    def fake_save_runtime_override(record: BrainRecord) -> BrainRecord:
        state["record"] = record
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

    mark_historical_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0201/mark-historical",
        headers={"X-XV7-API-Key": "test-secret"},
    )
    assert mark_historical_response.status_code == 200
    assert mark_historical_response.json()["relevance_state"] == "historical"

    mark_current_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0201/mark-current",
        headers={"X-XV7-API-Key": "test-secret"},
    )
    assert mark_current_response.status_code == 200
    assert mark_current_response.json()["relevance_state"] == "current"

    mark_superseded_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0201/mark-superseded",
        json={"relevance_state": "superseded", "superseded_by": "XV7-KNOWLEDGE-0999"},
        headers={"X-XV7-API-Key": "test-secret"},
    )
    assert mark_superseded_response.status_code == 200
    assert mark_superseded_response.json()["relevance_state"] == "superseded"
    assert mark_superseded_response.json()["status"] == "disabled"

    apply_reco_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0201/apply-recommendation",
        json={
            "recommendation_type": "mark_historical_via_runtime_override",
            "approve": True,
        },
        headers={"X-XV7-API-Key": "test-secret"},
    )
    assert apply_reco_response.status_code == 200
    apply_payload = apply_reco_response.json()
    assert apply_payload["applied"] is True
    assert apply_payload["record"]["relevance_state"] == "historical"


def test_runtime_brain_record_split_creates_current_operational_record(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)

    source = _record(
        {
            "record_id": "XV7-KNOWLEDGE-0301",
            "layer": "knowledge",
            "title": "Mixed historical and operational",
            "summary": "B7 completed and from now on enforce proof.",
            "body": "B7 completed and from now on enforce proof for CI claims.",
            "status": "active",
            "relevance_state": "current",
            "priority": 190,
            "tags": ["learned-rule"],
            "facts": [],
            "evidence": [],
        }
    )

    state: dict[str, BrainRecord] = {source.record_id: source}

    def fake_load_records() -> list[BrainRecord]:
        return list(state.values())

    def fake_get_record_with_source(record_id: str):
        record = state.get(record_id)
        if record is None:
            return None
        return (
            record,
            "runtime_override",
            Path(f"runtime/{record_id}.json"),
        )

    def fake_save_runtime_override(record: BrainRecord) -> BrainRecord:
        state[record.record_id] = record
        return record

    monkeypatch.setattr(
        "core.main.brain_context_manager.loader.load_records",
        fake_load_records,
    )
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

    split_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0301/split",
        json={
            "operational_title": "Operational: Proof rule",
            "operational_body": "Require proof before claiming CI state.",
            "layer": "knowledge",
        },
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert split_response.status_code == 200
    payload = split_response.json()
    assert payload["applied"] is True
    assert payload["source_record"]["relevance_state"] == "historical"
    assert payload["created_record"]["relevance_state"] == "current"
    assert payload["created_record"]["status"] == "active"
    assert payload["created_record"]["record_id"] != "XV7-KNOWLEDGE-0301"

    split_recommendation_response = client.post(
        "/runtime/brain/records/XV7-KNOWLEDGE-0301/apply-recommendation",
        json={
            "recommendation_type": "split_record",
            "approve": True,
            "operational_title": "Operational: split recommendation",
        },
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert split_recommendation_response.status_code == 200
    rec_payload = split_recommendation_response.json()
    assert rec_payload["applied"] is True
    assert rec_payload["status"] == "applied"
    assert rec_payload["created_record"]["relevance_state"] == "current"
