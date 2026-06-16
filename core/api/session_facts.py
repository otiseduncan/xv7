from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import aiosqlite


async def ensure_session_facts_table(facts_db_path: Path) -> None:
    async with aiosqlite.connect(facts_db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_facts (
                session_id TEXT PRIMARY KEY,
                facts_json TEXT NOT NULL
            );
            """
        )
        await conn.commit()


async def get_session_facts(facts_db_path: Path, session_id: str) -> dict[str, Any]:
    async with aiosqlite.connect(facts_db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """
            SELECT facts_json
            FROM session_facts
            WHERE session_id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        return {}

    try:
        data = json.loads(row["facts_json"])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def upsert_session_facts(
    facts_db_path: Path,
    session_id: str,
    facts: dict[str, Any],
) -> None:
    payload = json.dumps(facts, ensure_ascii=False)
    async with aiosqlite.connect(facts_db_path) as conn:
        await conn.execute(
            """
            INSERT INTO session_facts (session_id, facts_json)
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                facts_json = excluded.facts_json
            """,
            (session_id, payload),
        )
        await conn.commit()


async def persist_session_focus_fact(
    facts_db_path: Path,
    *,
    session_id: UUID,
    focus_payload: dict[str, Any],
) -> bool:
    try:
        existing = await get_session_facts(facts_db_path, str(session_id))
        existing["xv7_active_focus"] = focus_payload
        await upsert_session_facts(facts_db_path, str(session_id), existing)
        return True
    except Exception:
        return False
