from __future__ import annotations

from typing import Any


HISTORY_KEY = "operator_action_history"
MAX_HISTORY = 40


def get_history(session_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    history = session_metadata.get(HISTORY_KEY, [])
    if not isinstance(history, list):
        return []
    return [item for item in history if isinstance(item, dict)]


def append_history(
    session_metadata: dict[str, Any],
    receipt: dict[str, Any],
    *,
    max_items: int = MAX_HISTORY,
) -> list[dict[str, Any]]:
    history = get_history(session_metadata)
    history.append(receipt)
    if len(history) > max_items:
        history = history[-max_items:]
    session_metadata[HISTORY_KEY] = history
    return history


def latest_action(session_metadata: dict[str, Any]) -> dict[str, Any] | None:
    history = get_history(session_metadata)
    if not history:
        return None
    return history[-1]


def latest_action_by_name(
    session_metadata: dict[str, Any], action_name: str
) -> dict[str, Any] | None:
    history = get_history(session_metadata)
    for item in reversed(history):
        if str(item.get("action_name", "")) == action_name:
            return item
    return None
