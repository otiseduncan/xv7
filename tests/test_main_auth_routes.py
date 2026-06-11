from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from core.main import app
from core.runtime.schemas import SessionState


def test_diagnostics_routes_remain_public_when_api_key_is_set(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/runtime/status").status_code == 200
    assert client.get("/runtime/ollama").status_code == 200
    assert client.get("/runtime/models").status_code == 200
    assert client.get("/runtime/models/profiles").status_code == 200
    assert client.get("/runtime/models/active").status_code == 200
    assert client.get("/runtime/models/effective").status_code == 200
    assert client.get("/personas").status_code == 200


def test_create_session_requires_api_key_when_configured(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/sessions",
        json={"current_persona": "default"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "XV7 API key required"}


def test_create_session_accepts_xv7_api_key_header(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/sessions",
        json={"current_persona": "default"},
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert response.status_code == 201
    assert response.json()["current_persona"] == "default"


def test_create_session_accepts_core_api_key_when_xv7_not_set(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("XV7_API_KEY", raising=False)
    monkeypatch.setenv("CORE_API_KEY", "core-only-secret")
    client = TestClient(app)

    response = client.post(
        "/sessions",
        json={"current_persona": "default"},
        headers={"X-XV7-API-Key": "core-only-secret"},
    )

    assert response.status_code == 201
    assert response.json()["current_persona"] == "default"


def test_runtime_active_model_mutation_requires_api_key(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    client = TestClient(app)

    put_response = client.put(
        "/runtime/models/active",
        json={"profile": "balanced", "require_available": False},
    )
    delete_response = client.delete("/runtime/models/active")

    assert put_response.status_code == 401
    assert delete_response.status_code == 401


def test_runtime_active_model_mutation_accepts_api_key(
    monkeypatch: MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    async def fake_fetch_runtime_models(**_kwargs: object) -> dict[str, object]:
        return {
            "active_profile": "balanced",
            "profile_source": "runtime_override",
            "resolved_models": {
                "chat": "qwen3:8b",
                "reasoning": "qwen3:14b",
                "code": "qwen3:14b",
                "embedding": "nomic-embed-text:latest",
            },
            "role_aliases": {"default": "chat"},
            "availability": {
                "chat": True,
                "reasoning": True,
                "code": True,
                "embedding": True,
            },
            "ollama": {
                "reachable": True,
                "base_url": "http://ollama:11434",
                "models": ["qwen3:8b"],
                "error": None,
            },
            "config_error": None,
        }

    monkeypatch.setattr("core.main.fetch_runtime_models", fake_fetch_runtime_models)

    client = TestClient(app)

    put_response = client.put(
        "/runtime/models/active",
        json={"profile": "balanced", "require_available": True},
        headers={"X-XV7-API-Key": "test-secret"},
    )
    delete_response = client.delete(
        "/runtime/models/active",
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert put_response.status_code == 200
    assert put_response.json()["profile_source"] == "runtime_override"
    assert delete_response.status_code == 200


def test_session_message_requires_api_key_when_configured(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    client = TestClient(app)

    session_response = client.post(
        "/sessions",
        json={"current_persona": "default"},
        headers={"X-XV7-API-Key": "test-secret"},
    )
    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]
    message_response = client.post(
        f"/sessions/{session_id}/messages",
        json={"raw_text": "hello"},
    )

    assert message_response.status_code == 401
    assert message_response.json() == {"detail": "XV7 API key required"}


def test_session_message_accepts_api_key_when_configured(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.delenv("CORE_API_KEY", raising=False)

    class _FakeAgent:
        personas = {"default": {"name": "default"}}

        async def generate_response(
            self, _session_state: SessionState
        ) -> tuple[str, dict[str, str]]:
            return (
                "ok",
                {
                    "model_profile": "balanced",
                    "profile_source": "env",
                    "runtime_role": "chat",
                    "model_tag": "qwen3:8b",
                    "model_selection_source": "registry_effective_profile",
                    "request_id": "req-auth-route",
                },
            )

        async def aclose(self) -> None:
            return None

    async def _fake_query_similar_memories(
        _text: str, limit: int = 3
    ) -> list[dict[str, str]]:
        return []

    async def _fake_persist_vector_memory_round_trip(
        *_args: Any, **_kwargs: Any
    ) -> dict[str, Any]:
        return {"status": "ok"}

    monkeypatch.setattr("core.main.base_agent", _FakeAgent())
    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories",
        _fake_query_similar_memories,
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )

    client = TestClient(app)

    session_response = client.post(
        "/sessions",
        json={"current_persona": "default"},
        headers={"X-XV7-API-Key": "test-secret"},
    )
    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]
    message_response = client.post(
        f"/sessions/{session_id}/messages",
        json={"raw_text": "hello"},
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert message_response.status_code == 200
    payload = message_response.json()
    assert payload["messages"][-1]["role"] == "assistant"
    assert payload["metadata"]["model_use_receipt"]["request_id"] == "req-auth-route"
