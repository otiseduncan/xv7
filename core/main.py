from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import UUID
from uuid import uuid4

import aiosqlite
import httpx
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core.agents.base_agent import BaseAgent
from core.brain.manager import BrainContextManager
from core.memory.manager import PersistentMemoryManager
from core.operator.history import append_history, get_history
from core.operator.manager import OperatorManager
from core.runtime.memory_manager import MemoryManager, SessionNotFoundError
from core.runtime.auth import require_api_key
from core.runtime.model_profile_selection import (
    clear_runtime_profile_override,
    set_runtime_profile_override,
)
from core.runtime.models_api import (
    build_effective_runtime_models,
    build_runtime_model_profiles,
    fetch_runtime_models,
)
from core.runtime.ollama_status import fetch_ollama_status
from core.runtime.status import build_runtime_status
from core.runtime.schemas import ConversationMessage, SessionState
from core.runtime.vector_store import VectorMemoryEngine
from core.runtime.vector_memory_receipts import persist_vector_memory_round_trip


class CreateSessionRequest(BaseModel):
    """Optional initialization payload for a new session."""

    model_config = ConfigDict(extra="forbid")

    current_persona: str = Field(default="default", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddMessageRequest(BaseModel):
    """Payload for appending a new user message and running inference."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1)


class UpdateFactsRequest(BaseModel):
    """Payload for updating persistent memory facts for a session."""

    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any] = Field(default_factory=dict)


class SetActiveModelProfileRequest(BaseModel):
    """Payload for setting runtime active model profile override."""

    model_config = ConfigDict(extra="forbid")

    profile: str = Field(min_length=1)
    require_available: bool = Field(default=True)


memory_path = Path(os.getenv("MEMORY_DB_PATH", "data/memory"))
if memory_path.suffix == ".db":
    facts_db_path = memory_path
else:
    facts_db_path = memory_path / "session_facts.db"
facts_db_path.parent.mkdir(parents=True, exist_ok=True)


def build_facts_system_prompt(facts: dict[str, Any]) -> str:
    if not facts:
        return ""
    pretty = json.dumps(facts, ensure_ascii=False, indent=2)
    # Adding a clear boundary marker helps the LLM distinguish
    # persistent facts from transient conversation.
    return (
        "--- PERSISTENT SESSION MEMORY ---\n"
        "These facts are your long-term knowledge base for this specific session.\n"
        "Do not explain that you have this memory; simply use the information.\n"
        f"{pretty}\n"
        "----------------------------------\n"
    )


def build_assistant_payload(
    *,
    visible_text: str,
    context_receipt: dict[str, Any] | None = None,
    operator_receipts: list[dict[str, Any]] | None = None,
    memory_receipts: list[str] | None = None,
    model_use_receipt: dict[str, Any] | None = None,
    policy_provenance: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    action_history_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "visible_text": visible_text,
        "context_receipt": context_receipt or {},
        "operator_receipts": operator_receipts or [],
        "memory_receipts": memory_receipts or [],
        "model_use_receipt": model_use_receipt or {},
        "policy_provenance": policy_provenance or {},
        "warnings": warnings or [],
        "action_history_refs": action_history_refs or [],
    }


async def ensure_session_facts_table() -> None:
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


async def get_session_facts(session_id: str) -> dict[str, Any]:
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


async def upsert_session_facts(session_id: str, facts: dict[str, Any]) -> None:
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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Preserve startup and shutdown behavior via lifespan events."""
    await ensure_session_facts_table()
    persistent_memory_manager.bootstrap_seed_records()
    try:
        yield
    finally:
        await base_agent.aclose()
        await vector_store.aclose()


app = FastAPI(title="xv7-core", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory_manager = MemoryManager()
base_agent = BaseAgent()
vector_store = VectorMemoryEngine()
brain_context_manager = BrainContextManager()
persistent_memory_manager = PersistentMemoryManager()
_operator_repo_root = Path(os.getenv("XV7_OPERATOR_REPO_ROOT", str(Path.cwd())))
operator_manager = OperatorManager(repo_root=_operator_repo_root)

@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(
    request: Request,
    exc: SessionNotFoundError,
) -> JSONResponse:
    """Return HTTP 404 for missing session requests."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return HTTP 400 for domain-level validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """Return HTTP 500 for inference/runtime failures."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


@app.exception_handler(httpx.HTTPError)
async def http_error_handler(request: Request, exc: httpx.HTTPError) -> JSONResponse:
    """Return HTTP 500 for uncaught transport-level failures."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Upstream connection error: {exc}"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runtime/status")
async def runtime_status() -> dict:
    return build_runtime_status()


@app.get("/runtime/ollama")
async def runtime_ollama() -> dict:
    return await fetch_ollama_status()


@app.get("/runtime/models")
async def runtime_models(profile: str | None = None) -> dict[str, Any]:
    return await fetch_runtime_models(profile_override=profile)


@app.get("/runtime/models/profiles")
async def runtime_model_profiles() -> dict[str, Any]:
    return build_runtime_model_profiles()


@app.get("/runtime/models/active")
async def runtime_active_model_profile(profile: str | None = None) -> dict[str, Any]:
    payload = await fetch_runtime_models(profile_override=profile)
    return {
        "active_profile": payload["active_profile"],
        "profile_source": payload["profile_source"],
        "resolved_models": payload["resolved_models"],
        "role_aliases": payload["role_aliases"],
        "availability": payload["availability"],
        "ollama": payload["ollama"],
        "config_error": payload["config_error"],
    }


@app.put(
    "/runtime/models/active",
    dependencies=[Depends(require_api_key)],
)
async def set_runtime_active_model_profile(
    payload: SetActiveModelProfileRequest,
) -> dict[str, Any]:
    profiles_payload = build_runtime_model_profiles()
    available_profiles = set(profiles_payload.get("available_profiles", []))

    set_runtime_profile_override(payload.profile, available_profiles)

    runtime_payload = await fetch_runtime_models()
    if payload.require_available:
        if not runtime_payload.get("ollama", {}).get("reachable", False):
            clear_runtime_profile_override()
            raise ValueError(
                "Cannot apply profile with require_available=true because Ollama is unreachable."
            )

        availability = runtime_payload.get("availability", {})
        missing = [
            role
            for role in ("chat", "reasoning", "code", "embedding")
            if not bool(availability.get(role, False))
        ]
        if missing:
            clear_runtime_profile_override()
            raise ValueError(
                "Cannot apply profile with require_available=true; missing required "
                f"models for roles: {', '.join(missing)}."
            )

    return {
        "active_profile": runtime_payload["active_profile"],
        "profile_source": runtime_payload["profile_source"],
        "resolved_models": runtime_payload["resolved_models"],
        "role_aliases": runtime_payload["role_aliases"],
        "availability": runtime_payload["availability"],
        "ollama": runtime_payload["ollama"],
        "config_error": runtime_payload["config_error"],
    }


@app.delete(
    "/runtime/models/active",
    dependencies=[Depends(require_api_key)],
)
async def clear_runtime_active_model_profile() -> dict[str, Any]:
    clear_runtime_profile_override()
    payload = await fetch_runtime_models()
    return {
        "active_profile": payload["active_profile"],
        "profile_source": payload["profile_source"],
        "resolved_models": payload["resolved_models"],
        "role_aliases": payload["role_aliases"],
        "availability": payload["availability"],
        "ollama": payload["ollama"],
        "config_error": payload["config_error"],
    }


@app.get("/runtime/models/effective")
async def runtime_effective_models(profile: str | None = None) -> dict[str, Any]:
    return build_effective_runtime_models(profile_override=profile)


@app.get("/runtime/context/active")
async def runtime_active_context() -> dict[str, Any]:
    context = brain_context_manager.build_active_context()
    return {
        "prompt": context.prompt,
        "receipt": context.receipt,
        "compact_receipt": context.receipt.get("compact", ""),
    }


@app.get("/personas")
async def get_personas() -> dict[str, Any]:
    """Return registered persona configurations for local discovery/debugging."""
    return {
        "count": len(base_agent.personas),
        "personas": base_agent.personas,
    }


@app.post(
    "/sessions",
    response_model=SessionState,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_session(payload: CreateSessionRequest) -> SessionState:
    """Initialize and return a new active session state."""
    return await memory_manager.initialize_session(
        current_persona=payload.current_persona,
        metadata=payload.metadata,
    )


@app.get(
    "/sessions/{session_id}",
    response_model=SessionState,
    dependencies=[Depends(require_api_key)],
)
async def get_session(session_id: UUID) -> SessionState:
    """Retrieve the current session state by id."""
    return await memory_manager.get_session(session_id)


@app.put(
    "/sessions/{session_id}/facts",
    dependencies=[Depends(require_api_key)],
)
async def update_session_facts(
    session_id: UUID, payload: UpdateFactsRequest
) -> dict[str, str]:
    """Upsert session-scoped persistent memory facts."""
    await upsert_session_facts(str(session_id), payload.facts)
    return {"status": "ok", "session_id": str(session_id)}


@app.post(
    "/sessions/{session_id}/messages",
    response_model=SessionState,
    dependencies=[Depends(require_api_key)],
)
async def add_session_message(
    session_id: UUID,
    payload: AddMessageRequest,
) -> SessionState:
    """Run a full user -> inference -> assistant memory round trip."""
    user_state = await memory_manager.add_message(
        session_id=session_id,
        role="user",
        raw_text=payload.raw_text,
    )
    user_visible_content = user_state.messages[-1].content
    user_role = user_state.messages[-1].role

    session_state = await memory_manager.get_session(session_id)
    inference_state = session_state.model_copy(deep=True)

    operator_action = operator_manager.try_handle_chat(
        payload.raw_text,
        session_metadata=session_state.metadata,
    )
    if operator_action is not None:
        visible_text = operator_action.answer.strip()
        operator_receipt = operator_action.result.receipt()
        assistant_output = f"{visible_text}\n\n{operator_receipt}"
        structured_receipt = operator_action.result.structured_receipt()

        current_history = get_history(session_state.metadata)
        if operator_action.record_history:
            current_history = append_history(session_state.metadata, structured_receipt)
        action_history_refs = [
            str(item.get("action_id", ""))
            for item in current_history[-5:]
            if isinstance(item, dict) and str(item.get("action_id", ""))
        ]

        warnings: list[str] = []
        limitation = structured_receipt.get("limitation")
        if isinstance(limitation, str) and limitation.strip():
            warnings.append(limitation)

        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "operator_manager",
            "brain_answer_source": "operator_action",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt={},
            operator_receipts=[structured_receipt],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=warnings,
            action_history_refs=action_history_refs,
        )

        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=assistant_output,
            message_metadata=assistant_payload,
        )
        assistant_message = updated_state.messages[-1]

        vector_memory_receipt = await persist_vector_memory_round_trip(
            vector_store,
            session_id=str(session_id),
            user_role=user_role,
            user_content=user_visible_content,
            assistant_role=assistant_message.role,
            assistant_content=assistant_message.content,
        )
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["operator_last_action"] = operator_action.result.model_dump(mode="json")
        updated_state.metadata["operator_action_history"] = current_history
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        if (
            operator_action.result.action_name == "repo_status"
            and operator_action.result.status == "success"
        ):
            updated_state.metadata["live_repo_check"] = True
            current_tool_results = updated_state.metadata.get("tool_results", [])
            if not isinstance(current_tool_results, list):
                current_tool_results = []
            current_tool_results.append(
                {
                    "type": "repo_check",
                    "action_id": operator_action.result.action_id,
                    "status": operator_action.result.status,
                }
            )
            updated_state.metadata["tool_results"] = current_tool_results
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        await memory_manager.update_session(updated_state)
        return updated_state

    memory_action = persistent_memory_manager.try_handle_chat(
        payload.raw_text,
        session_metadata=session_state.metadata,
    )
    if memory_action is not None:
        visible_text = memory_action.answer.strip()
        assistant_output = visible_text
        if memory_action.receipt:
            assistant_output = f"{assistant_output}\n\n{memory_action.receipt}"

        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "persistent_memory",
            "brain_answer_source": "memory_records",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt={},
            operator_receipts=[],
            memory_receipts=[memory_action.receipt] if memory_action.receipt else [],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=[],
            action_history_refs=[
                str(item.get("action_id", ""))
                for item in get_history(session_state.metadata)[-5:]
                if isinstance(item, dict) and str(item.get("action_id", ""))
            ],
        )

        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=assistant_output,
            message_metadata=assistant_payload,
        )
        assistant_message = updated_state.messages[-1]

        vector_memory_receipt = await persist_vector_memory_round_trip(
            vector_store,
            session_id=str(session_id),
            user_role=user_role,
            user_content=user_visible_content,
            assistant_role=assistant_message.role,
            assistant_content=assistant_message.content,
        )
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        for key, value in memory_action.metadata_updates.items():
            updated_state.metadata[key] = value
        await memory_manager.update_session(updated_state)
        return updated_state

    brain_context = brain_context_manager.build_context_for_question(payload.raw_text)
    inference_state.messages.insert(
        0,
        ConversationMessage(role="system", content=brain_context.prompt),
    )

    compact_receipt = str(brain_context.receipt.get("compact", "")).strip()
    brain_answer = brain_context_manager.answer_from_records(
        payload.raw_text,
        session_metadata=session_state.metadata,
    )
    if brain_answer is not None:
        visible_text = brain_answer.strip()
        assistant_output = visible_text
        if compact_receipt:
            assistant_output = f"{assistant_output}\n\n{compact_receipt}"

        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "answer_contract",
            "brain_answer_source": "brain_records",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=brain_context.receipt,
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=[],
            action_history_refs=[
                str(item.get("action_id", ""))
                for item in get_history(session_state.metadata)[-5:]
                if isinstance(item, dict) and str(item.get("action_id", ""))
            ],
        )

        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=assistant_output,
            message_metadata=assistant_payload,
        )
        assistant_message = updated_state.messages[-1]

        vector_memory_receipt = await persist_vector_memory_round_trip(
            vector_store,
            session_id=str(session_id),
            user_role=user_role,
            user_content=user_visible_content,
            assistant_role=assistant_message.role,
            assistant_content=assistant_message.content,
        )
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = brain_context.receipt
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    try:
        facts = await get_session_facts(str(session_id))
    except Exception:
        facts = {}

    facts_prompt = build_facts_system_prompt(facts)
    if facts_prompt:
        inference_state.messages.insert(
            0,
            ConversationMessage(role="system", content=facts_prompt),
        )

    try:
        memories = await vector_store.query_similar_memories(payload.raw_text, limit=3)
    except Exception:
        memories = []

    if memories:
        context_lines = ["Relevant Historical Context:"]
        for item in memories:
            role = str(item.get("role", "unknown")).capitalize()
            content = str(item.get("content", "")).strip()
            if content:
                context_lines.append(f"- [{role}]: {content}")

        context_block = "\n".join(context_lines)
        transient_context = ConversationMessage(role="system", content=context_block)
        inference_state.messages.append(transient_context)

    raw_response, model_use_receipt = await base_agent.generate_response(
        inference_state
    )

    visible_text = raw_response.strip()
    assistant_output = visible_text
    if compact_receipt:
        assistant_output = f"{assistant_output}\n\n{compact_receipt}"

    updated_state = await memory_manager.add_message(
        session_id=session_id,
        role="assistant",
        raw_text=assistant_output,
        message_metadata=build_assistant_payload(
            visible_text=visible_text,
            context_receipt=brain_context.receipt,
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt=model_use_receipt,
            policy_provenance={
                "answer_source": "runtime_model_inference",
                "policy_source": "none",
                "brain_answer_source": "context_assisted",
                "request_id": model_use_receipt.get("request_id"),
                "session_id": str(session_id),
                "runtime_model_inference_proven": True,
            },
            warnings=[],
            action_history_refs=[
                str(item.get("action_id", ""))
                for item in get_history(session_state.metadata)[-5:]
                if isinstance(item, dict) and str(item.get("action_id", ""))
            ],
        ),
    )

    assistant_message = updated_state.messages[-1]

    vector_memory_receipt = await persist_vector_memory_round_trip(
        vector_store,
        session_id=str(session_id),
        user_role=user_role,
        user_content=user_visible_content,
        assistant_role=assistant_message.role,
        assistant_content=assistant_message.content,
    )
    model_use_receipt["session_id"] = str(session_id)
    updated_state.metadata["model_use_receipt"] = model_use_receipt
    updated_state.metadata["answer_provenance"] = {
        "answer_source": "runtime_model_inference",
        "policy_source": "none",
        "brain_answer_source": "context_assisted",
        "request_id": model_use_receipt.get("request_id"),
        "session_id": str(session_id),
        "runtime_model_inference_proven": True,
    }
    updated_state.metadata["vector_memory"] = vector_memory_receipt
    updated_state.metadata["context_receipt"] = brain_context.receipt
    updated_state.metadata["last_assistant_payload"] = updated_state.messages[-1].metadata
    await memory_manager.update_session(updated_state)

    return updated_state
