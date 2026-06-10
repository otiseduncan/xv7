from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4


def _error_payload(exc: Exception) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


async def persist_vector_memory_round_trip(
    vector_store: Any,
    *,
    session_id: str,
    user_role: str,
    user_content: str,
    assistant_role: str,
    assistant_content: str,
    message_id_factory: Callable[[], object] = uuid4,
) -> dict[str, Any]:
    """Persist user/assistant vector memories and return a visible receipt."""

    writes = [
        {
            "label": "user",
            "role": user_role,
            "content": user_content,
        },
        {
            "label": "assistant",
            "role": assistant_role,
            "content": assistant_content,
        },
    ]

    receipt: dict[str, Any] = {
        "status": "ok",
        "attempted": len(writes),
        "stored": 0,
        "errors": [],
    }

    for item in writes:
        try:
            await vector_store.store_memory(
                session_id=session_id,
                message_id=str(message_id_factory()),
                role=item["role"],
                content=item["content"],
            )
            receipt["stored"] += 1
        except Exception as exc:
            receipt["errors"].append(
                {
                    "label": item["label"],
                    "error": _error_payload(exc),
                }
            )

    if receipt["stored"] == receipt["attempted"]:
        receipt["status"] = "ok"
    elif receipt["stored"] > 0:
        receipt["status"] = "partial"
    else:
        receipt["status"] = "failed"

    return receipt
