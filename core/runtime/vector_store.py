"""Long-term semantic memory engine backed by SQLite vectors."""

from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import httpx

# Maximum number of embeddings to keep in the per-process cache.
# At ~768 floats each (nomic-embed-text) this costs ≈1.5 MB for 512 entries.
_EMBEDDING_CACHE_MAX = 512


class VectorMemoryEngine:
    """Asynchronous semantic memory engine with Ollama embeddings.

    Embeddings are generated via Ollama's `/api/embeddings` endpoint and stored
    in a local file-backed SQLite database as JSON arrays.
    """

    def __init__(self) -> None:
        vector_db_path = os.getenv("VECTOR_DB_PATH", "data/vectors")
        db_path = Path(vector_db_path)
        if db_path.suffix != ".db":
            db_path = db_path / "vector_memory.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db_path = db_path
        self._model_embed = os.getenv("MODEL_EMBED", "nomic-embed-text")
        self._ollama_base_url = os.getenv(
            "OLLAMA_BASE_URL", "http://ollama:11434"
        ).rstrip("/")
        self._init_lock = asyncio.Lock()
        self._initialized = False

        # Embedding cache: avoids re-embedding the same text twice per turn.
        # Key: stripped text; Value: embedding vector.
        # Eviction: FIFO once the cache exceeds _EMBEDDING_CACHE_MAX entries.
        self._embed_cache: dict[str, list[float]] = {}
        self._embed_cache_keys: list[str] = []

        timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
        self._client = httpx.AsyncClient(
            base_url=self._ollama_base_url,
            timeout=timeout,
            limits=limits,
        )

    async def aclose(self) -> None:
        """Close the pooled HTTP client."""
        await self._client.aclose()

    async def _ensure_db(self) -> None:
        """Create schema and indexes once per process."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            async with aiosqlite.connect(self._db_path) as conn:
                await conn.execute("PRAGMA journal_mode=WAL;")
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id TEXT NOT NULL UNIQUE,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding TEXT NOT NULL,
                        timestamp_utc TEXT NOT NULL
                    );
                    """
                )
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_session_timestamp
                    ON memories(session_id, timestamp_utc DESC);
                    """
                )
                await conn.commit()

            self._initialized = True

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector via Ollama `/api/embeddings`.

        Results are cached in-process so the same text is never sent to Ollama
        more than once per process lifetime (e.g. user query embedded for
        similarity search and then again for storage in the same turn).
        """
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Cannot embed empty text")

        if cleaned in self._embed_cache:
            return self._embed_cache[cleaned]

        payload = {
            "model": self._model_embed,
            "prompt": cleaned,
            "options": {
                "num_thread": 4,
            },
        }

        try:
            response = await self._client.post("/api/embeddings", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Timed out while calling Ollama /api/embeddings"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise RuntimeError(
                f"Ollama /api/embeddings failed with status {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to call Ollama /api/embeddings: {exc}") from exc

        data: dict[str, Any] = response.json()
        vector = data.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError(
                "Invalid embedding response: missing non-empty 'embedding' array"
            )

        try:
            floats = [float(value) for value in vector]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid embedding response: non-numeric embedding values"
            ) from exc

        # Write to cache with FIFO eviction.
        if len(self._embed_cache) >= _EMBEDDING_CACHE_MAX:
            oldest = self._embed_cache_keys.pop(0)
            self._embed_cache.pop(oldest, None)
        self._embed_cache[cleaned] = floats
        self._embed_cache_keys.append(cleaned)

        return floats

    async def store_memory(
        self,
        session_id: str,
        message_id: str,
        role: str,
        content: str,
    ) -> None:
        """Embed and persist one memory record with metadata."""
        await self._ensure_db()

        embedding = await self._get_embedding(content)
        timestamp_utc = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                    message_id,
                    session_id,
                    role,
                    content,
                    embedding,
                    timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    json.dumps(embedding),
                    timestamp_utc,
                ),
            )
            await conn.commit()

    async def query_similar_memories(
        self, query_text: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Return top-N stored memories by cosine similarity to the query."""
        await self._ensure_db()

        query_vector = await self._get_embedding(query_text)

        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT message_id, session_id, role, content, embedding, timestamp_utc
                FROM memories
                """
            )
            rows = await cursor.fetchall()

        scored: list[dict[str, Any]] = []
        for row in rows:
            stored_vector = json.loads(row["embedding"])
            if not isinstance(stored_vector, list) or not stored_vector:
                continue

            try:
                memory_vector = [float(value) for value in stored_vector]
            except (TypeError, ValueError):
                continue

            similarity = self._cosine_similarity(query_vector, memory_vector)
            scored.append(
                {
                    "message_id": row["message_id"],
                    "session_id": row["session_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp_utc"],
                    "similarity": similarity,
                }
            )

        scored.sort(key=lambda item: item["similarity"], reverse=True)
        return scored[: max(1, limit)]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        """Compute cosine similarity using native math utilities."""
        size = min(len(left), len(right))
        if size == 0:
            return 0.0

        dot = sum(left[i] * right[i] for i in range(size))
        left_norm = math.sqrt(sum(left[i] * left[i] for i in range(size)))
        right_norm = math.sqrt(sum(right[i] * right[i] for i in range(size)))

        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0

        return dot / (left_norm * right_norm)
