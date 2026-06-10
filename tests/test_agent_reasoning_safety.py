from __future__ import annotations

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
