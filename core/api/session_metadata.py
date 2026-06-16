from __future__ import annotations

from typing import Any


def lacks_verified_operator_success(session_metadata: dict[str, Any]) -> bool:
    last = session_metadata.get("operator_last_action")
    if not isinstance(last, dict):
        return True

    status = str(last.get("status", "")).strip().lower()
    if status in {"failed", "denied", "not_implemented", "cancelled", "pending"}:
        return True
    if status != "success":
        return True

    data = last.get("data")
    if not isinstance(data, dict):
        return True
    return not bool(data)


def is_communication_workflow_focus(session_metadata: dict[str, Any]) -> bool:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return False
    summary = str(focus.get("summary", "")).lower()
    if not summary:
        return False
    return any(
        token in summary
        for token in (
            "communicat",
            "workflow",
            "habit",
            "otis",
            "operator",
        )
    )
