from __future__ import annotations

from typing import Any, Callable


def build_operator_history_update(
    *,
    session_metadata: dict[str, Any],
    result: Any,
    append_history_fn: Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    structured_receipt = result.structured_receipt()
    history = append_history_fn(session_metadata, structured_receipt)
    session_metadata["operator_last_action"] = result.model_dump(mode="json")
    session_metadata["operator_action_history"] = history
    return structured_receipt, history


def should_clear_pending_after_confirm(result: Any) -> bool:
    if result.status in {"success", "cancelled", "not_implemented"}:
        return True
    if result.status == "failed":
        err = str(result.stderr_summary or "").lower()
        return "typed confirmation did not match" not in err
    return False


def stage_operator_response(
    *,
    session_id: str,
    answer: str,
    executed: bool,
    pending_action: dict[str, Any] | None,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "answer": answer,
        "executed": executed,
        "pending_action": pending_action,
        "receipt": receipt,
    }


def operator_action_response(
    *,
    session_id: str,
    answer: str,
    receipt: dict[str, Any],
    pending_action: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "answer": answer,
        "receipt": receipt,
        "pending_action": pending_action,
    }
