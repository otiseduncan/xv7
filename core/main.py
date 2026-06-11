from __future__ import annotations

import json
import os
import re
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


class OperatorStageRequest(BaseModel):
    """Stage a slash command action with optional operator mode enabled."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    command_text: str = Field(min_length=1)
    operator_mode: bool = False


class OperatorConfirmRequest(BaseModel):
    """Confirm a previously staged operator action."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    action_id: str = Field(min_length=1)
    typed_confirmation: str | None = None


class OperatorCancelRequest(BaseModel):
    """Cancel a previously staged operator action."""

    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    action_id: str = Field(min_length=1)


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


def sanitize_visible_answer_text(text: str) -> str:
    """Remove receipt/debug lines from user-visible assistant text."""
    if not text:
        return ""

    text = re.sub(r"\*\*sources\*\*\s*:\s*.*$", "", str(text), flags=re.IGNORECASE)
    text = re.sub(r"\bsources\s*:\s*.*$", "", text, flags=re.IGNORECASE)

    blocked_prefixes = (
        "operator receipt:",
        "context receipt:",
        "memory receipt:",
        "model receipt:",
        "sources:",
        "**sources**:",
        "- *xv7-",
        "- xv7-",
    )
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith(blocked_prefixes):
            continue
        cleaned_lines.append(raw_line)

    return "\n".join(cleaned_lines).strip()


ACTIVE_FOCUS_UPDATE_PREFIXES = (
    "focus on ",
    "from now on focus on ",
    "change your active focus to ",
    "change active focus to ",
    "set your focus to ",
    "set active focus to ",
    "change your focus to ",
    "change my focus to ",
    "make your focus ",
    "your active focus is ",
)

INTENT_CLASSES = {
    "active_focus_update",
    "user_correction",
    "communication_preference",
    "workflow_habit_learning",
    "protected_mutation_request",
    "status_question",
    "normal_question",
    "implementation_task",
}

PROTECTED_MUTATION_PATTERN = re.compile(
    r"\b("
    r"delete|remove|drop|destroy|format|wipe|erase|"
    r"shutdown|restart service|reset hard|git reset|"
    r"truncate|overwrite|force remove|rm -rf|"
    r"delete the memory database|delete memory database"
    r")\b",
    flags=re.IGNORECASE,
)

IMPLEMENTATION_TASK_PATTERN = re.compile(
    r"\b(implement|build|create|add|update|fix|refactor|wire|ship|patch|test)\b",
    flags=re.IGNORECASE,
)

STATUS_QUESTION_PATTERN = re.compile(
    r"^(what|which|who|when|where|why|how|did|do|does|is|are|can)\b",
    flags=re.IGNORECASE,
)

CORRECTION_PREFIXES = (
    "no, that is wrong",
    "no that is wrong",
    "that is wrong",
    "you're wrong",
    "you are wrong",
    "incorrect",
)

COMMUNICATION_PREFERENCE_MARKERS = (
    "i don't want",
    "i do not want",
    "i want you to",
    "prefer",
    "keep answers",
    "don't over-explain",
    "do not over-explain",
    "be direct",
)

WORKFLOW_HABIT_MARKERS = (
    "my habits",
    "my workflow",
    "my workflows",
    "how i work",
    "how i build",
    "how i make decisions",
    "the way i work",
)


def _normalize_intent_text(text: str) -> str:
    lowered = text.lower().strip().replace("’", "'")
    lowered = re.sub(r"[\s,]+", " ", lowered)
    return lowered

ACTIVE_FOCUS_PROTECTED_PATTERN = re.compile(
    r"\b("
    r"delete|remove|destroy|format|wipe|erase|"
    r"bypass safety|disable safety|ignore safety|"
    r"exfiltrate|steal|credential theft|malware|ransomware|"
    r"without confirmation|without approval|without receipts"
    r")\b",
    flags=re.IGNORECASE,
)


def _extract_active_focus_instruction(question: str) -> str | None:
    stripped = question.strip()
    normalized = _normalize_intent_text(stripped)

    if normalized.startswith("please "):
        normalized = normalized[len("please ") :]
    for prefix in ACTIVE_FOCUS_UPDATE_PREFIXES:
        if normalized.startswith(prefix):
            focus_text = normalized[len(prefix) :].strip(" .!?")
            if len(focus_text) >= 3:
                return focus_text

    from_now_on_match = re.match(r"^from now on\s*,?\s*focus on\s+(.+)$", normalized)
    if from_now_on_match:
        focus_text = from_now_on_match.group(1).strip(" .!?")
        if len(focus_text) >= 3:
            return focus_text

    return None


def _extract_after_prefixes(normalized: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip(" .!?")
    return normalized.strip(" .!?")


def _classify_speech_act(question: str) -> str:
    normalized = _normalize_intent_text(question)

    if _extract_active_focus_instruction(question) is not None:
        return "active_focus_update"

    if any(normalized.startswith(prefix) for prefix in CORRECTION_PREFIXES):
        return "user_correction"

    if "you are not responsible for building yourself" in normalized:
        return "user_correction"

    if any(marker in normalized for marker in WORKFLOW_HABIT_MARKERS):
        return "workflow_habit_learning"

    if any(marker in normalized for marker in COMMUNICATION_PREFERENCE_MARKERS):
        return "communication_preference"

    if PROTECTED_MUTATION_PATTERN.search(normalized):
        return "protected_mutation_request"

    if STATUS_QUESTION_PATTERN.match(normalized) or normalized.endswith("?"):
        return "status_question"

    if IMPLEMENTATION_TASK_PATTERN.search(normalized):
        return "implementation_task"

    return "normal_question"


def _extract_correction_text(question: str) -> str:
    normalized = _normalize_intent_text(question)
    return _extract_after_prefixes(normalized, CORRECTION_PREFIXES)


def _extract_preference_text(question: str) -> str:
    normalized = _normalize_intent_text(question)
    return normalized.strip(" .!?")


def _extract_workflow_habit_text(question: str) -> str:
    normalized = _normalize_intent_text(question)
    return normalized.strip(" .!?")


def _append_learning_signal(session_metadata: dict[str, Any], signal: dict[str, Any]) -> None:
    current = session_metadata.get("learning_signals")
    if not isinstance(current, list):
        current = []
    current.append(signal)
    session_metadata["learning_signals"] = current[-50:]


def _intent_context_receipt(
    *,
    intent_class: str,
    record_id: str,
    source: str,
    persistence: str,
    status: str,
) -> dict[str, Any]:
    return {
        "compact": (
            f"Context receipt: Intent {intent_class} "
            f"(record={record_id}; source={source}; persistence={persistence}; status={status})."
        ),
        "context_receipts": [
            {
                "layer": "memory",
                "record_id": record_id,
                "source": source,
                "persistence": persistence,
                "status": status,
                "intent_class": intent_class,
            }
        ],
        "record_ids": [record_id],
    }


def _focus_violates_protected_rules(focus_text: str) -> bool:
    return bool(ACTIVE_FOCUS_PROTECTED_PATTERN.search(focus_text))


def _focus_label_for_text(focus_text: str) -> str:
    lowered = focus_text.lower()
    if any(token in lowered for token in ("communicat", "habit", "workflow")):
        return "COMM-01"
    return "FOCUS-USER"


def _active_focus_system_prompt(session_metadata: dict[str, Any]) -> str:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return ""

    label = str(focus.get("id", "FOCUS-USER")).strip() or "FOCUS-USER"
    summary = str(focus.get("summary", "")).strip()
    if not summary:
        return ""

    return (
        "--- ACTIVE FOCUS (DIRECT USER INSTRUCTION) ---\n"
        f"{label} — {summary}\n"
        "Treat this as the current working priority until the user changes it.\n"
        "Do not confuse roadmap phase with active user focus.\n"
        "----------------------------------------------\n"
    )


async def _persist_session_focus_fact(
    *,
    session_id: UUID,
    focus_payload: dict[str, Any],
) -> bool:
    try:
        existing = await get_session_facts(str(session_id))
        existing["xv7_active_focus"] = focus_payload
        await upsert_session_facts(str(session_id), existing)
        return True
    except Exception:
        return False


def _is_focus_status_question(question: str) -> bool:
    normalized = " ".join(question.lower().strip().split())
    return normalized in {
        "what are we working on?",
        "what are we working on",
        "what are we working on right now?",
        "what are we working on right now",
        "what is your current active focus?",
        "what is your current active focus",
        "what is your active focus?",
        "what is your active focus",
        "what did i just change your focus to?",
        "what did i just change your focus to",
    }


def _session_focus_context_receipt(session_metadata: dict[str, Any]) -> dict[str, Any] | None:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return None

    focus_id = str(focus.get("id", "")).strip()
    focus_summary = str(focus.get("summary", "")).strip()
    source = str(focus.get("source", "direct_user_instruction")).strip() or "direct_user_instruction"
    persistence = str(focus.get("persistence", "session-only")).strip() or "session-only"
    if not focus_id or not focus_summary:
        return None

    return {
        "compact": (
            f"Context receipt: Active Focus {focus_id} "
            f"(source={source}; persistence={persistence})."
        ),
        "context_receipts": [
            {
                "layer": "active_focus",
                "record_id": focus_id,
                "source": source,
                "persistence": persistence,
                "status": "active",
            }
        ],
        "record_ids": [focus_id],
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


@app.get(
    "/operator/commands",
    dependencies=[Depends(require_api_key)],
)
async def list_operator_commands(operator_mode: bool = False) -> dict[str, Any]:
    return {
        "operator_mode": operator_mode,
        "commands": operator_manager.list_slash_commands(operator_mode=operator_mode),
    }


@app.post(
    "/operator/stage",
    dependencies=[Depends(require_api_key)],
)
async def stage_operator_action(payload: OperatorStageRequest) -> dict[str, Any]:
    session_state = await memory_manager.get_session(payload.session_id)
    stage_result = operator_manager.stage_slash_command(
        payload.command_text,
        operator_mode=payload.operator_mode,
        session_metadata=session_state.metadata,
    )

    structured_receipt = stage_result["result"].structured_receipt()
    history = append_history(session_state.metadata, structured_receipt)
    session_state.metadata["operator_last_action"] = stage_result["result"].model_dump(mode="json")
    session_state.metadata["operator_action_history"] = history
    await memory_manager.update_session(session_state)

    return {
        "session_id": str(payload.session_id),
        "answer": stage_result["answer"],
        "executed": stage_result["executed"],
        "pending_action": stage_result["pending_action"],
        "receipt": structured_receipt,
    }


@app.post(
    "/operator/confirm",
    dependencies=[Depends(require_api_key)],
)
async def confirm_operator_action(payload: OperatorConfirmRequest) -> dict[str, Any]:
    session_state = await memory_manager.get_session(payload.session_id)
    pending = operator_manager.get_pending_action(session_state.metadata)

    if pending is None or str(pending.get("action_id", "")) != payload.action_id:
        raise ValueError("No matching pending operator action found for confirmation.")

    confirmation = operator_manager.confirm_pending_action(
        pending,
        typed_confirmation=payload.typed_confirmation,
    )
    result = confirmation["result"]
    structured_receipt = result.structured_receipt()

    should_clear = result.status in {"success", "cancelled", "not_implemented"}
    if result.status == "failed":
        err = str(result.stderr_summary or "").lower()
        should_clear = not ("typed confirmation did not match" in err)

    if should_clear:
        operator_manager.clear_pending_action(session_state.metadata)

    history = append_history(session_state.metadata, structured_receipt)
    session_state.metadata["operator_last_action"] = result.model_dump(mode="json")
    session_state.metadata["operator_action_history"] = history
    await memory_manager.update_session(session_state)

    return {
        "session_id": str(payload.session_id),
        "answer": confirmation["answer"],
        "receipt": structured_receipt,
        "pending_action": operator_manager.get_pending_action(session_state.metadata),
    }


@app.post(
    "/operator/cancel",
    dependencies=[Depends(require_api_key)],
)
async def cancel_operator_action(payload: OperatorCancelRequest) -> dict[str, Any]:
    session_state = await memory_manager.get_session(payload.session_id)
    pending = operator_manager.get_pending_action(session_state.metadata)

    if pending is None or str(pending.get("action_id", "")) != payload.action_id:
        raise ValueError("No matching pending operator action found for cancel request.")

    cancellation = operator_manager.cancel_pending_action(pending)
    operator_manager.clear_pending_action(session_state.metadata)

    structured_receipt = cancellation["result"].structured_receipt()
    history = append_history(session_state.metadata, structured_receipt)
    session_state.metadata["operator_last_action"] = cancellation["result"].model_dump(mode="json")
    session_state.metadata["operator_action_history"] = history
    await memory_manager.update_session(session_state)

    return {
        "session_id": str(payload.session_id),
        "answer": cancellation["answer"],
        "receipt": structured_receipt,
        "pending_action": None,
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
    intent_class = _classify_speech_act(payload.raw_text)

    current_history = get_history(session_state.metadata)
    action_history_refs = [
        str(item.get("action_id", ""))
        for item in current_history[-5:]
        if isinstance(item, dict) and str(item.get("action_id", ""))
    ]

    if intent_class == "user_correction":
        correction_text = _extract_correction_text(payload.raw_text)
        persisted = True
        record_id = "MEMORY-UNAVAILABLE"
        try:
            record = persistent_memory_manager.create_active_memory(
                content=f"User correction (high priority): {correction_text}",
                source="user_explicit",
                memory_type="correction",
                tags=["learning", "correction", "high-priority"],
                confidence=0.98,
            )
            record_id = record.id
        except Exception:
            persisted = False

        _append_learning_signal(
            session_state.metadata,
            {
                "type": "user_correction",
                "content": correction_text,
                "source": "direct_user_instruction",
            },
        )

        persistence_label = "saved" if persisted else "session-only"
        visible_text = (
            "Understood. I will treat that correction as high-priority tuning input and apply it immediately, "
            "unless protected rules are involved."
        )
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_intent_context_receipt(
                intent_class="user_correction",
                record_id=record_id,
                source="direct_user_instruction",
                persistence=persistence_label,
                status="applied",
            ),
            operator_receipts=[],
            memory_receipts=[f"Memory: {record_id}"] if persisted else [],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "intent_router",
                "brain_answer_source": "user_correction",
                "intent_class": intent_class,
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
            },
            warnings=[],
            action_history_refs=action_history_refs,
        )
        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=visible_text,
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
        updated_state.metadata["answer_provenance"] = assistant_payload["policy_provenance"]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    if intent_class == "communication_preference":
        preference_text = _extract_preference_text(payload.raw_text)
        persisted = True
        record_id = "MEMORY-UNAVAILABLE"
        try:
            record = persistent_memory_manager.create_active_memory(
                content=f"Communication preference: {preference_text}",
                source="user_explicit",
                memory_type="user_preference",
                tags=["learning", "communication", "preference"],
                confidence=0.96,
            )
            record_id = record.id
        except Exception:
            persisted = False

        _append_learning_signal(
            session_state.metadata,
            {
                "type": "communication_preference",
                "content": preference_text,
                "source": "direct_user_instruction",
            },
        )

        persistence_label = "saved" if persisted else "session-only"
        visible_text = (
            "Understood. I recorded that as a communication preference and will use it as working behavior going forward."
        )
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_intent_context_receipt(
                intent_class="communication_preference",
                record_id=record_id,
                source="direct_user_instruction",
                persistence=persistence_label,
                status="applied",
            ),
            operator_receipts=[],
            memory_receipts=[f"Memory: {record_id}"] if persisted else [],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "intent_router",
                "brain_answer_source": "communication_preference",
                "intent_class": intent_class,
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
            },
            warnings=[],
            action_history_refs=action_history_refs,
        )
        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=visible_text,
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
        updated_state.metadata["answer_provenance"] = assistant_payload["policy_provenance"]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    if intent_class == "workflow_habit_learning":
        workflow_text = _extract_workflow_habit_text(payload.raw_text)
        persisted = True
        record_id = "MEMORY-UNAVAILABLE"
        try:
            record = persistent_memory_manager.create_active_memory(
                content=f"Workflow/habit learning signal: {workflow_text}",
                source="user_explicit",
                memory_type="workflow_note",
                tags=["learning", "workflow", "habits"],
                confidence=0.96,
            )
            record_id = record.id
        except Exception:
            persisted = False

        _append_learning_signal(
            session_state.metadata,
            {
                "type": "workflow_habit_learning",
                "content": workflow_text,
                "source": "direct_user_instruction",
            },
        )

        persistence_label = "saved" if persisted else "session-only"
        visible_text = (
            "Understood. I recorded that as workflow/habit learning and will adapt to it as current working behavior."
        )
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_intent_context_receipt(
                intent_class="workflow_habit_learning",
                record_id=record_id,
                source="direct_user_instruction",
                persistence=persistence_label,
                status="applied",
            ),
            operator_receipts=[],
            memory_receipts=[f"Memory: {record_id}"] if persisted else [],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "intent_router",
                "brain_answer_source": "workflow_habit_learning",
                "intent_class": intent_class,
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
            },
            warnings=[],
            action_history_refs=action_history_refs,
        )
        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=visible_text,
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
        updated_state.metadata["answer_provenance"] = assistant_payload["policy_provenance"]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    active_focus_instruction = _extract_active_focus_instruction(payload.raw_text)
    if active_focus_instruction is not None:
        if _focus_violates_protected_rules(active_focus_instruction):
            visible_text = (
                "I cannot set that Active Focus because it conflicts with protected system rules "
                "(safety, destructive behavior, or bypassing approval boundaries). "
                "Please give a safe working focus and I will apply it immediately."
            )
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt={
                    "compact": "Context receipt: Active Focus denied by protected rules.",
                    "context_receipts": [
                        {
                            "layer": "active_focus",
                            "record_id": "FOCUS-DENIED",
                            "source": "direct_user_instruction",
                            "persistence": "none",
                            "status": "denied",
                        }
                    ],
                    "record_ids": ["FOCUS-DENIED"],
                },
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "active_focus_intent",
                    "brain_answer_source": "active_focus_denied",
                    "intent_class": intent_class,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
                warnings=[],
                action_history_refs=action_history_refs,
            )
            updated_state = await memory_manager.add_message(
                session_id=session_id,
                role="assistant",
                raw_text=visible_text,
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
            updated_state.metadata["answer_provenance"] = assistant_payload["policy_provenance"]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

        focus_id = _focus_label_for_text(active_focus_instruction)
        focus_summary = active_focus_instruction.strip()
        focus_payload = {
            "id": focus_id,
            "summary": focus_summary,
            "source": "direct_user_instruction",
        }
        persisted = await _persist_session_focus_fact(
            session_id=session_id,
            focus_payload=focus_payload,
        )
        focus_payload["persistence"] = "saved" if persisted else "session-only"
        session_state.metadata["active_focus"] = focus_payload

        visible_text = (
            "Understood. I'm updating my Active Focus.\n\n"
            "New Active Focus:\n"
            f"{focus_id} - {focus_summary}\n\n"
            "I will treat this as the current priority until you change it."
        )

        context_receipt = {
            "compact": (
                f"Context receipt: Active Focus {focus_id} "
                f"(source=direct_user_instruction; persistence={focus_payload['persistence']})."
            ),
            "context_receipts": [
                {
                    "layer": "active_focus",
                    "record_id": focus_id,
                    "source": "direct_user_instruction",
                    "persistence": focus_payload["persistence"],
                    "status": "active",
                }
            ],
            "record_ids": [focus_id],
        }

        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=context_receipt,
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "active_focus_intent",
                "brain_answer_source": "active_focus_update",
                "intent_class": intent_class,
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
            },
            warnings=[],
            action_history_refs=action_history_refs,
        )

        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=visible_text,
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
        updated_state.metadata["answer_provenance"] = assistant_payload["policy_provenance"]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        updated_state.metadata["active_focus"] = focus_payload
        _append_learning_signal(
            updated_state.metadata,
            {
                "type": "active_focus_update",
                "content": focus_summary,
                "source": "direct_user_instruction",
            },
        )
        await memory_manager.update_session(updated_state)
        return updated_state

    focus_prompt = _active_focus_system_prompt(session_state.metadata)
    if focus_prompt:
        inference_state.messages.insert(
            0,
            ConversationMessage(role="system", content=focus_prompt),
        )

    operator_action = operator_manager.try_handle_chat(
        payload.raw_text,
        session_metadata=session_state.metadata,
    )
    if operator_action is not None:
        visible_text = sanitize_visible_answer_text(operator_action.answer.strip())
        assistant_output = visible_text
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
        visible_text = sanitize_visible_answer_text(memory_action.answer.strip())
        assistant_output = visible_text

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
        visible_text = sanitize_visible_answer_text(brain_answer.strip())
        assistant_output = visible_text

        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "answer_contract",
            "brain_answer_source": "brain_records",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        effective_context_receipt = brain_context.receipt
        if _is_focus_status_question(payload.raw_text):
            override_receipt = _session_focus_context_receipt(session_state.metadata)
            if override_receipt is not None:
                effective_context_receipt = override_receipt
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=effective_context_receipt,
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
        updated_state.metadata["context_receipt"] = effective_context_receipt
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

    visible_text = sanitize_visible_answer_text(raw_response.strip())
    assistant_output = visible_text

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
