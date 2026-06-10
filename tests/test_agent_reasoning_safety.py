from __future__ import annotations

import pytest

from core.agents.base_agent import BaseAgent
from core.runtime.schemas import ConversationMessage


def test_to_ollama_message_does_not_replay_hidden_reasoning() -> None:
    message = ConversationMessage(
        role="assistant",
        content="visible answer",
        reasoning_content="private hidden reasoning",
    )

    payload = BaseAgent._to_ollama_message(message)

    assert payload == {
        "role": "assistant",
        "content": "visible answer",
    }
    assert "private hidden reasoning" not in payload["content"]
    assert "<|think|>" not in payload["content"]
    assert "</|think|>" not in payload["content"]


def test_to_ollama_message_preserves_visible_user_content() -> None:
    message = ConversationMessage(
        role="user",
        content="visible user request",
        reasoning_content=None,
    )

    payload = BaseAgent._to_ollama_message(message)

    assert payload == {
        "role": "user",
        "content": "visible user request",
    }


def test_agent_resolve_model_uses_registry_profile_for_chat_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "balanced")

    resolved = BaseAgent._resolve_model("default")

    assert resolved.canonical_role == "chat"
    assert resolved.model_tag == "qwen3:8b"


def test_agent_resolve_model_does_not_use_legacy_model_default_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "balanced")
    monkeypatch.setenv("MODEL_DEFAULT", "llama3")

    resolved = BaseAgent._resolve_model("default")

    assert resolved.model_tag == "qwen3:8b"
