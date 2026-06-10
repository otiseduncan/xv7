"""Open WebUI manifold pipe bridging chats to xv7-core sessions."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from pydantic import BaseModel, Field


class Pipe:
    """Manifold pipe that exposes xv7 personas as selectable child models."""

    class Valves(BaseModel):
        """Runtime-tunable settings for connectivity and fallback behavior."""

        core_base_url: str = Field(
            default="http://xv7-core:8000",
            description="Base URL for the xv7-core API inside the Docker network.",
        )
        default_persona: str = Field(
            default="default",
            description="Fallback persona ID when no child profile is selected.",
        )
        fallback_personas: str = Field(
            default="default,coding,creative",
            description="Comma-separated persona IDs returned if core is unreachable.",
        )
        request_timeout_seconds: float = Field(
            default=180.0,
            ge=5.0,
            description="HTTP timeout for calls to xv7-core.",
        )
        fallback_reply: str = Field(
            default="xv7-core is temporarily unreachable. Please try again shortly.",
            description="Message returned when the bridge cannot reach core.",
        )

    def __init__(self) -> None:
        self.type = "manifold"
        self.name = "xv7: "
        self.valves = self.Valves()
        self._session_map: dict[str, str] = {}

    async def pipes(self) -> list[dict[str, str]]:
        """Return child persona profiles discoverable from xv7-core."""
        try:
            data = await self._request_json("GET", "/personas")
            personas = data.get("personas", {}) if isinstance(data, dict) else {}
            if isinstance(personas, dict) and personas:
                items: list[dict[str, str]] = []
                for key, meta in sorted(personas.items()):
                    if not isinstance(key, str):
                        continue
                    display_name = key
                    if isinstance(meta, dict):
                        raw_name = meta.get("name")
                        if isinstance(raw_name, str) and raw_name.strip():
                            display_name = raw_name.strip()
                    display_name = display_name.replace("_", " ").title()
                    items.append({"id": key, "name": display_name})
                if items:
                    return items
        except Exception:
            pass

        return [
            {"id": persona.strip(), "name": persona.strip().replace("_", " ").title()}
            for persona in self.valves.fallback_personas.split(",")
            if persona.strip()
        ]

    async def pipe(self, body: dict[str, Any]) -> str:
        """Forward latest user turn into xv7-core and return assistant output."""
        try:
            persona_id = self._extract_persona_id(body)
            session_key = self._extract_session_key(body, persona_id)
            session_id = await self._ensure_session(session_key, persona_id)
            user_text = self._extract_latest_user_text(body)

            if not user_text:
                return "No user message was found in the incoming payload."

            response = await self._request_json(
                "POST",
                f"/sessions/{session_id}/messages",
                {
                    "raw_text": user_text,
                },
            )

            messages = response.get("messages", []) if isinstance(response, dict) else []
            if isinstance(messages, list) and messages:
                last = messages[-1]
                if isinstance(last, dict):
                    content = last.get("content")
                    if isinstance(content, str) and content.strip():
                        return content

            return self.valves.fallback_reply
        except Exception:
            return self.valves.fallback_reply

    async def _ensure_session(self, session_key: str, persona_id: str) -> str:
        """Get or create a persistent xv7-core session mapped to chat context."""
        existing = self._session_map.get(session_key)
        if existing:
            return existing

        payload = {
            "current_persona": persona_id,
            "metadata": {
                "source": "open-webui-pipe",
                "session_key": session_key,
            },
        }
        response = await self._request_json("POST", "/sessions", payload)
        session_id = response.get("session_id") if isinstance(response, dict) else None
        if not isinstance(session_id, str) or not session_id.strip():
            raise RuntimeError("xv7-core did not return a valid session_id")

        self._session_map[session_key] = session_id
        return session_id

    async def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a JSON request to xv7-core and parse response payload."""
        timeout = httpx.Timeout(self.valves.request_timeout_seconds)
        url = f"{self.valves.core_base_url.rstrip('/')}{path}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method=method, url=url, json=payload)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError("Expected dictionary JSON payload from xv7-core")
        return data

    def _extract_persona_id(self, body: dict[str, Any]) -> str:
        """Extract selected manifold child ID from model identifier."""
        model = body.get("model")
        if isinstance(model, str) and model.strip():
            parsed = model.strip()
            if ":" in parsed:
                parsed = parsed.split(":", 1)[1].strip()
            if "." in parsed:
                parsed = parsed.rsplit(".", 1)[-1].strip()
            if parsed:
                return parsed
        return self.valves.default_persona

    def _extract_session_key(self, body: dict[str, Any], persona_id: str) -> str:
        """Derive a stable session key from Open WebUI chat context IDs."""
        for key in ("chat_id", "conversation_id", "id", "session_id"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return f"{persona_id}:{value.strip()}"

        metadata = body.get("metadata")
        if isinstance(metadata, dict):
            for key in ("chat_id", "conversation_id", "session_id"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    return f"{persona_id}:{value.strip()}"

        return f"{persona_id}:{uuid.uuid4()}"

    @staticmethod
    def _extract_latest_user_text(body: dict[str, Any]) -> str:
        """Pull the latest user-visible prompt from the Open WebUI body."""
        messages = body.get("messages")
        if isinstance(messages, list):
            for item in reversed(messages):
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                content = item.get("content")
                if role == "user" and isinstance(content, str) and content.strip():
                    return content.strip()

        for key in ("prompt", "input", "query"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return ""
