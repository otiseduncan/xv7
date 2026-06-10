from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient
import pytest

from core.agents.base_agent import BaseAgent
from core.main import app
from core.runtime.model_profile_selection import (
    clear_runtime_profile_override,
    set_runtime_profile_override,
)
from core.runtime.model_registry import resolve_model_for_runtime_role
from core.runtime.schemas import ConversationMessage, SessionState


class _FakeOllamaResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"message": {"content": "XV7_MODEL_PROOF"}}


class _CapturingClient:
    def __init__(self) -> None:
        self.last_payload: dict[str, Any] | None = None

    async def post(self, _path: str, json: dict[str, Any]) -> _FakeOllamaResponse:
        self.last_payload = json
        return _FakeOllamaResponse()

    async def aclose(self) -> None:
        return None


def _run_agent_once(
    agent: BaseAgent,
) -> tuple[str, dict[str, str], dict[str, Any] | None]:
    state = SessionState(
        current_persona="default",
        messages=[
            ConversationMessage(role="user", content="Return exactly: XV7_MODEL_PROOF")
        ],
    )
    response, receipt = asyncio.run(agent.generate_response(state))
    client = agent._client
    payload = client.last_payload if isinstance(client, _CapturingClient) else None
    return response, receipt, payload


def test_chat_runtime_uses_balanced_profile_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "balanced")

    agent = BaseAgent()
    agent._client = _CapturingClient()

    response, receipt, payload = _run_agent_once(agent)

    assert response == "XV7_MODEL_PROOF"
    assert payload is not None
    assert payload["model"] == "qwen3:8b"
    assert receipt["model_profile"] == "balanced"
    assert receipt["runtime_role"] == "chat"
    assert receipt["model_tag"] == "qwen3:8b"
    assert receipt["model_selection_source"] == "registry_effective_profile"


def test_chat_runtime_uses_local_test_profile_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "local_test")

    agent = BaseAgent()
    agent._client = _CapturingClient()

    _response, receipt, payload = _run_agent_once(agent)

    assert payload is not None
    assert payload["model"] == "qwen3:14b"
    assert receipt["model_profile"] == "local_test"
    assert receipt["model_tag"] == "qwen3:14b"


def test_large_code_profile_resolves_chat_and_code_roles() -> None:
    chat = resolve_model_for_runtime_role("chat", profile="large_code")
    code = resolve_model_for_runtime_role("code", profile="large_code")

    assert chat.model_tag == "qwen3-coder:30b"
    assert code.model_tag == "qwen3-coder:30b"


def test_runtime_override_beats_env_and_clear_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "balanced")
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    set_runtime_profile_override(
        "local_test",
        {"low_resource", "balanced", "local_test", "large_code"},
    )

    agent = BaseAgent()
    agent._client = _CapturingClient()

    _response, receipt_override, payload_override = _run_agent_once(agent)

    assert payload_override is not None
    assert payload_override["model"] == "qwen3:14b"
    assert receipt_override["model_profile"] == "local_test"
    assert receipt_override["profile_source"] == "runtime_override"

    clear_runtime_profile_override()

    _response, receipt_fallback, payload_fallback = _run_agent_once(agent)

    assert payload_fallback is not None
    assert payload_fallback["model"] == "qwen3:8b"
    assert receipt_fallback["model_profile"] == "balanced"
    assert receipt_fallback["profile_source"] == "env"


def test_legacy_model_env_keys_do_not_override_chat_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "balanced")
    monkeypatch.setenv("MODEL_DEFAULT", "llama3")
    monkeypatch.setenv("MODEL_CODE", "qwen2.5-coder:14b")
    monkeypatch.setenv("MODEL_REASONING", "deepseek-r1:8b")
    monkeypatch.setenv("MODEL_EMBED", "nomic-embed-text")

    agent = BaseAgent()
    agent._client = _CapturingClient()

    _response, receipt, payload = _run_agent_once(agent)

    assert payload is not None
    assert payload["model"] == "qwen3:8b"
    assert receipt["model_tag"] == "qwen3:8b"


def test_session_message_response_includes_safe_model_use_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")

    class _FakeAgent:
        personas = {"default": {"name": "default"}}

        async def generate_response(
            self, _session_state: SessionState
        ) -> tuple[str, dict[str, str]]:
            return (
                "XV7_MODEL_PROOF",
                {
                    "model_profile": "local_test",
                    "profile_source": "runtime_override",
                    "runtime_role": "chat",
                    "model_tag": "qwen3:14b",
                    "model_selection_source": "registry_effective_profile",
                    "request_id": "req-test-1",
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
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]
    message_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Return exactly: XV7_MODEL_PROOF"},
    )

    assert message_response.status_code == 200
    payload = message_response.json()
    receipt = payload["metadata"]["model_use_receipt"]

    assert receipt["model_profile"] == "local_test"
    assert receipt["profile_source"] == "runtime_override"
    assert receipt["runtime_role"] == "chat"
    assert receipt["model_tag"] == "qwen3:14b"
    assert receipt["model_selection_source"] == "registry_effective_profile"
    assert receipt["request_id"] == "req-test-1"
    assert "session_id" in receipt

    payload_text = str(payload)
    assert "test-secret" not in payload_text
    assert "<|think|>" not in payload_text
