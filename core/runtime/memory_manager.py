"""Async in-memory session manager for xv7 runtime state."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from uuid import UUID

from core.runtime.schemas import ConversationMessage, MessageRole, SessionState


_THINK_BLOCK_PATTERN = re.compile(
    r"<\|think\|>(.*?)</\|think\|>",
    flags=re.DOTALL | re.IGNORECASE,
)


class SessionNotFoundError(KeyError):
    """Raised when a requested session does not exist."""


class MemoryManager:
    """Manages short-term session state in memory with async safety.

    This manager is intended for single-process runtime usage. For horizontal
    scaling, replace the backing store with a shared data layer.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, SessionState] = {}
        self._lock = asyncio.Lock()

    async def initialize_session(
        self,
        *,
        session_id: UUID | None = None,
        current_persona: str = "default",
        context_window_tokens: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState:
        """Create and store a new session state.

        Args:
            session_id: Optional explicit UUID. If omitted, one is generated.
            current_persona: Active persona name for the session.
            context_window_tokens: Current token-budget usage.
            metadata: Optional session metadata map.

        Returns:
            The newly created session state.

        Raises:
            ValueError: If the session_id already exists.
        """
        async with self._lock:
            state_data: dict[str, Any] = {
                "current_persona": current_persona,
                "context_window_tokens": context_window_tokens,
                "metadata": metadata or {},
            }
            if session_id is not None:
                state_data["session_id"] = session_id

            state = SessionState(**state_data)
            if state.session_id in self._sessions:
                raise ValueError(f"Session already exists: {state.session_id}")
            self._sessions[state.session_id] = state
            return state

    async def get_session(self, session_id: UUID) -> SessionState:
        """Retrieve a session by id.

        Raises:
            SessionNotFoundError: If no session exists for the UUID.
        """
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError(f"Session not found: {session_id}")
            return state

    async def update_session(self, state: SessionState) -> SessionState:
        """Replace a session state atomically by its own id."""
        async with self._lock:
            if state.session_id not in self._sessions:
                raise SessionNotFoundError(f"Session not found: {state.session_id}")
            self._sessions[state.session_id] = state
            return state

    async def add_message(
        self,
        session_id: UUID,
        role: MessageRole,
        raw_text: str,
    ) -> SessionState:
        """Parse and append a message to session memory.

        This method extracts `<|think|>...</|think|>` blocks into
        `reasoning_content` and stores only visible text in `content`.

        Args:
            session_id: Target session UUID.
            role: Message role (`system`, `user`, or `assistant`).
            raw_text: Unprocessed model/user text.

        Returns:
            Updated session state.

        Raises:
            SessionNotFoundError: If session does not exist.
            ValueError: If visible content is empty after parsing.
        """
        reasoning_content, visible_content = self._split_reasoning(raw_text)

        message = ConversationMessage(
            role=role,
            content=visible_content,
            reasoning_content=reasoning_content,
        )

        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError(f"Session not found: {session_id}")
            state.messages.append(message)
            return state

    async def clear_session(self, session_id: UUID) -> None:
        """Delete a session from memory if it exists."""
        async with self._lock:
            self._sessions.pop(session_id, None)

    @staticmethod
    def _split_reasoning(raw_text: str) -> tuple[str | None, str]:
        """Extract `<|think|>` blocks and return `(reasoning, visible_content)`.

        Multiple reasoning blocks are joined with a blank line.
        """
        text = raw_text.strip()
        reasoning_parts = [
            match.strip()
            for match in _THINK_BLOCK_PATTERN.findall(text)
            if match.strip()
        ]
        visible = _THINK_BLOCK_PATTERN.sub("", text).strip()

        if not visible:
            raise ValueError("Message content is empty after reasoning extraction")

        reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else None
        return reasoning, visible
