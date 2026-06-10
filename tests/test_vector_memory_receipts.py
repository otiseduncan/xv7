from __future__ import annotations

import asyncio
from typing import Any

from core.runtime.vector_memory_receipts import persist_vector_memory_round_trip


class FakeVectorStore:
    def __init__(self, *, fail_roles: set[str] | None = None) -> None:
        self.fail_roles = fail_roles or set()
        self.calls: list[dict[str, Any]] = []

    async def store_memory(
        self,
        *,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
    ) -> None:
        if role in self.fail_roles:
            raise RuntimeError(f"failed role: {role}")

        self.calls.append(
            {
                "session_id": session_id,
                "message_id": message_id,
                "role": role,
                "content": content,
            }
        )


def test_vector_memory_receipt_reports_success() -> None:
    store = FakeVectorStore()

    receipt = asyncio.run(
        persist_vector_memory_round_trip(
            store,
            session_id="session-1",
            user_role="user",
            user_content="hello",
            assistant_role="assistant",
            assistant_content="hi",
            message_id_factory=lambda: "fixed-id",
        )
    )

    assert receipt["status"] == "ok"
    assert receipt["attempted"] == 2
    assert receipt["stored"] == 2
    assert receipt["errors"] == []
    assert len(store.calls) == 2


def test_vector_memory_receipt_reports_partial_failure() -> None:
    store = FakeVectorStore(fail_roles={"assistant"})

    receipt = asyncio.run(
        persist_vector_memory_round_trip(
            store,
            session_id="session-1",
            user_role="user",
            user_content="hello",
            assistant_role="assistant",
            assistant_content="hi",
            message_id_factory=lambda: "fixed-id",
        )
    )

    assert receipt["status"] == "partial"
    assert receipt["attempted"] == 2
    assert receipt["stored"] == 1
    assert receipt["errors"][0]["label"] == "assistant"
    assert receipt["errors"][0]["error"]["type"] == "RuntimeError"


def test_vector_memory_receipt_reports_total_failure() -> None:
    store = FakeVectorStore(fail_roles={"user", "assistant"})

    receipt = asyncio.run(
        persist_vector_memory_round_trip(
            store,
            session_id="session-1",
            user_role="user",
            user_content="hello",
            assistant_role="assistant",
            assistant_content="hi",
        )
    )

    assert receipt["status"] == "failed"
    assert receipt["attempted"] == 2
    assert receipt["stored"] == 0
    assert len(receipt["errors"]) == 2
