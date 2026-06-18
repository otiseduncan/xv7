from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import UUID
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from core.api.active_focus import (
    ACTIVE_FOCUS_PROTECTED_PATTERN as _ACTIVE_FOCUS_PROTECTED_PATTERN,
    ACTIVE_FOCUS_UPDATE_PREFIXES as _ACTIVE_FOCUS_UPDATE_PREFIXES,
    extract_active_focus_instruction as _extract_active_focus_instruction_from_api,
    focus_violates_protected_rules as _focus_violates_protected_rules_from_api,
    is_active_focus_candidate as _is_active_focus_candidate_from_api,
    is_focus_status_question as _is_focus_status_question_from_api,
    is_unclear_focus_instruction as _is_unclear_focus_instruction_from_api,
)
from core.api.brain_record_ids import (
    next_record_id_for_layer as _next_record_id_for_layer_from_records,
)
from core.api.brain_records import (
    serialize_brain_record as _serialize_brain_record_payload,
    summary_from_body as _summary_from_body,
)
from core.api.facts_prompt import build_facts_system_prompt
from core.api.learned_rules import (
    active_learned_rules as _active_learned_rules_from_api,
    append_learning_signal as _append_learning_signal_from_api,
    applies_learned_rule as _applies_learned_rule_from_api,
    extract_after_prefixes as _extract_after_prefixes_from_api,
    extract_correction_text as _extract_correction_text_from_api,
    extract_preference_text as _extract_preference_text_from_api,
    extract_workflow_habit_text as _extract_workflow_habit_text_from_api,
    is_emotional_unclear_feedback as _is_emotional_unclear_feedback_from_api,
    learned_rules_prompt as _learned_rules_prompt_from_api,
    learning_protected_boundary as _learning_protected_boundary_from_api,
    learning_rule_tags as _learning_rule_tags_from_api,
    learning_rule_title as _learning_rule_title_from_api,
    needs_learning_clarification as _needs_learning_clarification_from_api,
    speech_act_confidence as _speech_act_confidence_from_api,
    speech_act_to_learning_layer as _speech_act_to_learning_layer_from_api,
)
from core.api.intent_helpers import (
    active_focus_guided_plan_answer as _active_focus_guided_plan_answer_from_api,
    active_focus_system_prompt as _active_focus_system_prompt_from_api,
    build_task_guard_answer as _build_task_guard_answer_from_api,
    classify_speech_act as _classify_speech_act_from_api,
    is_build_follow_up_prompt as _is_build_follow_up_prompt_from_api,
    is_focus_guided_follow_up as _is_focus_guided_follow_up_from_api,
    is_local_scan_or_operator_prompt as _is_local_scan_or_operator_prompt_from_api,
    is_protected_implementation_task as _is_protected_implementation_task_from_api,
)
from core.api.context_receipts import (
    active_focus_guided_context_receipt as _active_focus_guided_context_receipt_from_api,
    intent_context_receipt as _intent_context_receipt_from_api,
    learning_context_receipt as _learning_context_receipt_from_api,
    merge_focus_context_receipt as _merge_focus_context_receipt_from_api,
    session_focus_context_receipt as _session_focus_context_receipt_from_api,
)
from core.api.repo_paths import resolve_operator_repo_root
from core.api.response_payloads import (
    auto_memory_prompt_from_metadata as _auto_memory_prompt_from_metadata,
    build_assistant_payload,
    sanitize_visible_answer_text,
)
from core.api.runtime_helpers import (
    format_runtime_date as _format_runtime_date_from_api,
    format_runtime_time as _format_runtime_time_from_api,
    is_runtime_clock_question as _is_runtime_clock_question_from_api,
    runtime_clock_answer as _runtime_clock_answer_from_api,
    runtime_clock_now as _runtime_clock_now_from_api,
    runtime_clock_system_prompt as _runtime_clock_system_prompt_from_api,
    runtime_clock_timezone as _runtime_clock_timezone_from_api,
)
from core.api.schemas import (
    AddMessageRequest,
    CreateSessionRequest,
    UpdateFactsRequest,
)
from core.api.session_metadata import (
    is_communication_workflow_focus as _is_communication_workflow_focus_from_api,
    lacks_verified_operator_success as _lacks_verified_operator_success_from_api,
)
from core.api.session_facts import (
    ensure_session_facts_table as _ensure_session_facts_table_from_api,
    get_session_facts as _get_session_facts_from_api,
    persist_session_focus_fact as _persist_session_focus_fact_from_api,
    upsert_session_facts as _upsert_session_facts_from_api,
)
from core.api.brain_record_routes import (
    configure_brain_record_routes,
    router as brain_record_router,
)
from core.api.health_routes import router as health_router
from core.api.operator_routes import (
    configure_operator_routes,
    router as operator_router,
)
from core.api.runtime_routes import (
    configure_runtime_routes,
    router as runtime_router,
)
from core.api.session_message_routes import configure_session_message_routes

from core.agents.base_agent import BaseAgent
from core.brain.manager import BrainContextManager
from core.brain.schema import BrainLayer, BrainRecord
from core.memory.auto_pilot import MemoryAutoPilotService, MemoryDecisionState
from core.memory.manager import PersistentMemoryManager
from core.operator.history import append_history, get_history
from core.operator.manager import OperatorExecution, OperatorManager
from core.prompts.commercial_style import build_commercial_system_prompt
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
from core.services.brain_record_service import (
    build_runtime_brain_record_updates as _build_runtime_brain_record_updates_from_service,
    list_runtime_brain_records as _list_runtime_brain_records_from_service,
    mark_record_current as _mark_record_current_from_service,
    mark_record_historical as _mark_record_historical_from_service,
    mark_record_superseded as _mark_record_superseded_from_service,
    serialize_refreshed_record_or_raise as _serialize_refreshed_record_or_raise_from_service,
)
from core.services.operator_action_service import (
    build_operator_history_update as _build_operator_history_update_from_service,
    operator_action_response as _operator_action_response_from_service,
    should_clear_pending_after_confirm as _should_clear_pending_after_confirm_from_service,
    stage_operator_response as _stage_operator_response_from_service,
)
from core.services.runtime_status_service import (
    active_model_payload as _active_model_payload_from_service,
    ensure_required_models_available as _ensure_required_models_available_from_service,
    runtime_communication_proof_status_payload as _runtime_communication_proof_status_payload_from_service,
)


def _resolve_operator_repo_root(
    *,
    env_value: str | None = None,
    fallback: Path | None = None,
    current_os_name: str | None = None,
) -> Path:
    return resolve_operator_repo_root(
        env_value=env_value,
        fallback=fallback,
        current_os_name=current_os_name,
    )


memory_path = Path(os.getenv("MEMORY_DB_PATH", "data/memory"))
if memory_path.suffix == ".db":
    facts_db_path = memory_path
else:
    facts_db_path = memory_path / "session_facts.db"
facts_db_path.parent.mkdir(parents=True, exist_ok=True)


def _serialize_brain_record(
    *,
    record: BrainRecord,
    source: str,
    path: Path,
) -> dict[str, Any]:
    return _serialize_brain_record_payload(
        record=record,
        source=source,
        path=path,
        updated_at=brain_context_manager.loader.record_updated_at(path),
    )


def _next_record_id_for_layer(layer: BrainLayer) -> str:
    return _next_record_id_for_layer_from_records(
        layer,
        brain_context_manager.loader.load_records(),
    )


def _split_record_to_current_operational(
    *,
    record: BrainRecord,
    operational_title: str | None,
    operational_summary: str | None,
    operational_body: str | None,
    tags: list[str] | None,
    layer: BrainLayer | None,
    review_reason: str | None,
    applies_when: str | None,
    valid_from: str | None,
    valid_until: str | None,
) -> tuple[BrainRecord, BrainRecord]:
    target_layer = layer or record.layer
    new_record_id = _next_record_id_for_layer(target_layer)

    body = (operational_body or record.body or "").strip()
    if not body:
        body = record.summary.strip()

    title = (operational_title or "").strip()
    if not title:
        title = f"Operational: {record.title}"

    summary = (operational_summary or "").strip() or _summary_from_body(body)

    raw_tags = tags if tags is not None else list(record.tags)
    normalized_tags: list[str] = []
    for tag in raw_tags:
        cleaned = str(tag).strip().lower().replace(" ", "-")
        if cleaned and cleaned not in normalized_tags:
            normalized_tags.append(cleaned)
    for required in ("runtime", "split-derived", "current-operational"):
        if required not in normalized_tags:
            normalized_tags.append(required)
    for remove_tag in ("historical", "superseded", "deactivated"):
        if remove_tag in normalized_tags:
            normalized_tags.remove(remove_tag)

    created = BrainRecord.model_validate(
        {
            "record_id": new_record_id,
            "layer": target_layer.value,
            "title": title,
            "summary": summary,
            "body": body,
            "status": "active",
            "relevance_state": "current",
            "priority": max(record.priority, 200),
            "tags": normalized_tags,
            "facts": list(record.facts),
            "evidence": [
                *list(record.evidence),
                f"split_from={record.record_id}",
            ],
            "applies_when": applies_when,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }
    )

    historical = record.model_copy(
        update={
            "relevance_state": "historical",
            "superseded_by": created.record_id,
            "review_reason": review_reason
            or "Split into historical context plus current operational rule.",
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    brain_context_manager.loader.save_runtime_override(historical)
    brain_context_manager.loader.save_runtime_override(created)
    return historical, created


ACTIVE_FOCUS_UPDATE_PREFIXES = _ACTIVE_FOCUS_UPDATE_PREFIXES

INTENT_CLASSES = {
    "active_focus_update",
    "user_correction",
    "communication_preference",
    "workflow_habit_learning",
    "hallucination_guard",
    "answer_style_preference",
    "diagnostic_rule",
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
    r"delete the memory database|delete memory database|"
    r"bypass safety|disable safety|ignore confirmations|"
    r"expose secrets|leak secrets|"
    r"rewrite system identity|change your identity"
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
    "correction:",
    "no, that is wrong",
    "no that is wrong",
    "no, that is not what i meant",
    "no that is not what i meant",
    "no, that's not what i meant",
    "that's not what i meant",
    "you screwed up",
    "that is wrong",
    "you're wrong",
    "you are wrong",
    "incorrect",
)

COMMUNICATION_PREFERENCE_MARKERS = (
    "i don't want",
    "i do not want",
    "i want you to",
    "going forward",
    "don't say it that way",
    "dont say it that way",
    "remember i prefer",
    "prefer",
    "preview first",
    "write files only",
    "keep answers",
    "don't over-explain",
    "do not over-explain",
    "be direct",
)

WORKFLOW_HABIT_MARKERS = (
    "remember this workflow correction",
    "we always",
    "my habits",
    "my workflow",
    "my workflows",
    "how i work",
    "how i build",
    "how i make decisions",
    "the way i work",
)

HALLUCINATION_GUARD_MARKERS = (
    "before guessing",
    "don't guess",
    "do not guess",
    "verify",
    "proof first",
    "check proof first",
)

ANSWER_STYLE_MARKERS = (
    "direct answers",
    "keep it direct",
    "be concise",
    "short answers",
    "unless i ask",
    "don't dump",
    "do not dump",
)

DIAGNOSTIC_RULE_MARKERS = (
    "when i ask about",
    "github status",
    "repo status",
    "actions",
    "ci status",
    "rebuild before",
    "live testing",
)

LEARNING_PROTECTED_PATTERN = re.compile(
    r"\b("
    r"bypass safety|disable safety|ignore confirmations|"
    r"authorize destructive actions|expose secrets|leak secrets|"
    r"rewrite system identity|change your identity|"
    r"pretend ci is green|claim verified without proof"
    r")\b",
    flags=re.IGNORECASE,
)


def _normalize_intent_text(text: str) -> str:
    lowered = text.lower().strip().replace("â€™", "'")
    lowered = re.sub(r"[\s,]+", " ", lowered)
    return lowered


ACTIVE_FOCUS_PROTECTED_PATTERN = _ACTIVE_FOCUS_PROTECTED_PATTERN


def _extract_active_focus_instruction(question: str) -> str | None:
    return _extract_active_focus_instruction_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
        prefixes=ACTIVE_FOCUS_UPDATE_PREFIXES,
    )


def _is_active_focus_candidate(question: str) -> bool:
    return _is_active_focus_candidate_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
        is_status_question=lambda normalized: bool(
            STATUS_QUESTION_PATTERN.match(normalized)
        ),
    )


def _is_unclear_focus_instruction(focus_text: str) -> bool:
    return _is_unclear_focus_instruction_from_api(focus_text)


def _extract_after_prefixes(normalized: str, prefixes: tuple[str, ...]) -> str:
    return _extract_after_prefixes_from_api(normalized, prefixes)


def _classify_speech_act(question: str) -> str:
    return _classify_speech_act_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
        status_question_pattern=STATUS_QUESTION_PATTERN,
        correction_prefixes=CORRECTION_PREFIXES,
        hallucination_guard_markers=HALLUCINATION_GUARD_MARKERS,
        answer_style_markers=ANSWER_STYLE_MARKERS,
        diagnostic_rule_markers=DIAGNOSTIC_RULE_MARKERS,
        workflow_habit_markers=WORKFLOW_HABIT_MARKERS,
        communication_preference_markers=COMMUNICATION_PREFERENCE_MARKERS,
        protected_mutation_pattern=PROTECTED_MUTATION_PATTERN,
        implementation_task_pattern=IMPLEMENTATION_TASK_PATTERN,
        extract_active_focus_instruction=_extract_active_focus_instruction,
        is_protected_implementation_task=_is_protected_implementation_task,
    )


def _build_task_guard_answer() -> str:
    return _build_task_guard_answer_from_api()


def _is_protected_implementation_task(normalized_question: str) -> bool:
    return _is_protected_implementation_task_from_api(normalized_question)


def _runtime_clock_timezone() -> ZoneInfo | timezone:
    return _runtime_clock_timezone_from_api()


def _runtime_clock_now() -> datetime:
    return _runtime_clock_now_from_api()


def _format_runtime_date(now: datetime) -> str:
    return _format_runtime_date_from_api(now)


def _format_runtime_time(now: datetime) -> str:
    return _format_runtime_time_from_api(now)


def _runtime_clock_system_prompt() -> str:
    return _runtime_clock_system_prompt_from_api()


def _is_runtime_clock_question(question: str) -> bool:
    return _is_runtime_clock_question_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
    )


def _runtime_clock_answer() -> tuple[str, dict[str, Any]]:
    return _runtime_clock_answer_from_api()


def _is_build_follow_up_prompt(question: str) -> bool:
    return _is_build_follow_up_prompt_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
    )


def _lacks_verified_operator_success(session_metadata: dict[str, Any]) -> bool:
    return _lacks_verified_operator_success_from_api(session_metadata)


def _extract_correction_text(question: str) -> str:
    return _extract_correction_text_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
        correction_prefixes=CORRECTION_PREFIXES,
    )


def _extract_preference_text(question: str) -> str:
    return _extract_preference_text_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
    )


def _extract_workflow_habit_text(question: str) -> str:
    return _extract_workflow_habit_text_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
    )


def _speech_act_to_learning_layer(speech_act: str) -> BrainLayer:
    return _speech_act_to_learning_layer_from_api(speech_act)


def _speech_act_confidence(speech_act: str, text: str) -> float:
    return _speech_act_confidence_from_api(
        speech_act,
        text,
        normalize_intent_text=_normalize_intent_text,
    )


def _needs_learning_clarification(speech_act: str, text: str) -> bool:
    return _needs_learning_clarification_from_api(
        speech_act,
        text,
        normalize_intent_text=_normalize_intent_text,
    )


def _is_emotional_unclear_feedback(text: str) -> bool:
    return _is_emotional_unclear_feedback_from_api(
        text,
        normalize_intent_text=_normalize_intent_text,
    )


def _learning_protected_boundary(text: str) -> bool:
    return _learning_protected_boundary_from_api(
        text,
        normalize_intent_text=_normalize_intent_text,
        learning_protected_pattern=LEARNING_PROTECTED_PATTERN,
    )


def _learning_rule_tags(speech_act: str, proof_required: bool) -> list[str]:
    return _learning_rule_tags_from_api(speech_act, proof_required)


def _learning_rule_title(speech_act: str, lesson_text: str) -> str:
    return _learning_rule_title_from_api(speech_act, lesson_text)


def _append_learning_signal(
    session_metadata: dict[str, Any], signal: dict[str, Any]
) -> None:
    _append_learning_signal_from_api(session_metadata, signal)


def _intent_context_receipt(
    *,
    intent_class: str,
    record_id: str,
    source: str,
    persistence: str,
    status: str,
) -> dict[str, Any]:
    return _intent_context_receipt_from_api(
        intent_class=intent_class,
        record_id=record_id,
        source=source,
        persistence=persistence,
        status=status,
    )


def _learning_context_receipt(
    *,
    learning_layer: BrainLayer,
    learned_record_id: str,
    proof_required: bool,
) -> dict[str, Any]:
    return _learning_context_receipt_from_api(
        learning_layer=learning_layer,
        learned_record_id=learned_record_id,
        proof_required=proof_required,
    )


def _active_learned_rules(records: list[BrainRecord]) -> list[BrainRecord]:
    return _active_learned_rules_from_api(records)


def _learned_rules_prompt(records: list[BrainRecord]) -> str:
    return _learned_rules_prompt_from_api(records)


def _applies_learned_rule(
    question: str,
    records: list[BrainRecord],
) -> tuple[str | None, BrainRecord | None]:
    return _applies_learned_rule_from_api(
        question,
        records,
        normalize_intent_text=_normalize_intent_text,
    )


def _focus_violates_protected_rules(focus_text: str) -> bool:
    return _focus_violates_protected_rules_from_api(
        focus_text,
        protected_pattern=ACTIVE_FOCUS_PROTECTED_PATTERN,
    )


def _active_focus_system_prompt(session_metadata: dict[str, Any]) -> str:
    return _active_focus_system_prompt_from_api(session_metadata)


async def _persist_session_focus_fact(
    *,
    session_id: UUID,
    focus_payload: dict[str, Any],
) -> bool:
    return await _persist_session_focus_fact_from_api(
        facts_db_path,
        session_id=session_id,
        focus_payload=focus_payload,
    )


def _is_focus_status_question(question: str) -> bool:
    return _is_focus_status_question_from_api(question)


def _session_focus_context_receipt(
    session_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    return _session_focus_context_receipt_from_api(session_metadata)


def _resolve_effective_active_focus(
    session_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    focus = session_metadata.get("active_focus")
    if isinstance(focus, dict):
        focus_id = str(focus.get("id", "")).strip()
        focus_summary = str(focus.get("summary", "")).strip()
        if focus_id and focus_summary:
            return focus

    active_focus_records = brain_context_manager.loader.load_active_records(
        layer=BrainLayer.ACTIVE_FOCUS
    )
    if not active_focus_records:
        return None

    record = active_focus_records[0]
    return {
        "id": record.record_id,
        "title": record.title,
        "summary": record.summary,
        "source": "brain_record_runtime",
        "persistence": "brain_record_saved",
    }


def _merge_focus_context_receipt(
    base_receipt: dict[str, Any] | None,
    session_metadata: dict[str, Any],
) -> dict[str, Any]:
    return _merge_focus_context_receipt_from_api(base_receipt, session_metadata)


def _is_communication_workflow_focus(session_metadata: dict[str, Any]) -> bool:
    return _is_communication_workflow_focus_from_api(session_metadata)


def _is_focus_guided_follow_up(question: str) -> bool:
    return _is_focus_guided_follow_up_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
    )


def _is_local_scan_or_operator_prompt(question: str) -> bool:
    return _is_local_scan_or_operator_prompt_from_api(
        question,
        normalize_intent_text=_normalize_intent_text,
    )


def _active_focus_guided_plan_answer() -> str:
    return _active_focus_guided_plan_answer_from_api()


def _active_focus_guided_context_receipt(focus_id: str) -> dict[str, Any]:
    return _active_focus_guided_context_receipt_from_api(focus_id)


async def ensure_session_facts_table() -> None:
    await _ensure_session_facts_table_from_api(facts_db_path)


async def get_session_facts(session_id: str) -> dict[str, Any]:
    return await _get_session_facts_from_api(facts_db_path, session_id)


async def upsert_session_facts(session_id: str, facts: dict[str, Any]) -> None:
    await _upsert_session_facts_from_api(facts_db_path, session_id, facts)


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
memory_auto_pilot = MemoryAutoPilotService()
_operator_repo_root = resolve_operator_repo_root()
operator_manager = OperatorManager(repo_root=_operator_repo_root)

configure_runtime_routes(
    build_runtime_status=build_runtime_status,
    fetch_ollama_status=fetch_ollama_status,
    fetch_ollama_status_getter=lambda: fetch_ollama_status,
    fetch_runtime_models=fetch_runtime_models,
    fetch_runtime_models_getter=lambda: fetch_runtime_models,
    build_runtime_model_profiles=build_runtime_model_profiles,
    set_runtime_profile_override=set_runtime_profile_override,
    clear_runtime_profile_override=clear_runtime_profile_override,
    ensure_required_models_available=_ensure_required_models_available_from_service,
    active_model_payload=_active_model_payload_from_service,
    build_effective_runtime_models=build_effective_runtime_models,
    brain_context_manager=brain_context_manager,
    runtime_communication_proof_status_payload=_runtime_communication_proof_status_payload_from_service,
)
configure_brain_record_routes(
    brain_context_manager_getter=lambda: brain_context_manager,
    list_runtime_brain_records=_list_runtime_brain_records_from_service,
    serialize_brain_record=_serialize_brain_record,
    build_runtime_brain_record_updates=_build_runtime_brain_record_updates_from_service,
    serialize_refreshed_record_or_raise=_serialize_refreshed_record_or_raise_from_service,
    mark_record_current=_mark_record_current_from_service,
    mark_record_historical=_mark_record_historical_from_service,
    mark_record_superseded=_mark_record_superseded_from_service,
    split_record_to_current_operational=_split_record_to_current_operational,
)
configure_operator_routes(
    memory_manager=memory_manager,
    operator_manager=operator_manager,
    append_history=append_history,
    build_operator_history_update=_build_operator_history_update_from_service,
    should_clear_pending_after_confirm=_should_clear_pending_after_confirm_from_service,
    stage_operator_response=_stage_operator_response_from_service,
    operator_action_response=_operator_action_response_from_service,
)
app.include_router(health_router)
app.include_router(runtime_router)
app.include_router(brain_record_router)
app.include_router(operator_router)
app.include_router(
    configure_session_message_routes(
        add_message_handler_getter=lambda: add_session_message
    )
)


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
    session_state.metadata["operator_mode_enabled"] = bool(payload.operator_mode)
    resolved_focus = _resolve_effective_active_focus(session_state.metadata)
    if isinstance(resolved_focus, dict):
        session_state.metadata["active_focus"] = resolved_focus

    # X Kernel v0 bridge: classify the incoming message on the existing UI path.
    # Metadata-only for now; normal chat behavior continues unchanged.
    try:
        from core.x_kernel.decision import XDecisionKernel

        x_kernel_decision = XDecisionKernel().decide(payload.raw_text)
        session_state.metadata["x_kernel_decision"] = x_kernel_decision.to_dict()
    except Exception as exc:
        session_state.metadata["x_kernel_decision"] = {
            "intent": "kernel_error",
            "risk": "none",
            "route": "answer_only",
            "summary": str(exc),
            "requires_confirmation": False,
            "command": [],
            "package_action": "none",
            "reasons": ["x_kernel_exception"],
        }

    auto_decision = memory_auto_pilot.intake(
        payload.raw_text,
        session_metadata=session_state.metadata,
        active_records=persistent_memory_manager.list_active_memories(),
    )
    for key, value in auto_decision.metadata_updates.items():
        session_state.metadata[key] = value

    normalized_fast_policy_text = _normalize_intent_text(payload.raw_text)
    if normalized_fast_policy_text in {
        "what is your name?",
        "what is your name",
        "whats your name?",
        "whats your name",
        "what's your name?",
        "what's your name",
        "your name?",
        "your name",
        "who is otis duncan?",
        "who is otis duncan",
        "what is xv7?",
        "what is xv7",
        "can you read github repos?",
        "can you read github repos",
    }:
        visible_text = brain_context_manager.answer_from_records(
            payload.raw_text,
            session_metadata=session_state.metadata,
        )
        if visible_text is None:
            visible_text = "My name is Xoduz."
        visible_text = sanitize_visible_answer_text(visible_text.strip())
        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "answer_contract",
            "brain_answer_source": "deterministic_identity",
            "intent_class": "identity_question",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt(
                {}, session_state.metadata
            ),
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=[],
            action_history_refs=[],
        )
        updated_state = await memory_manager.add_message(
            session_id=session_id,
            role="assistant",
            raw_text=visible_text,
            message_metadata=assistant_payload,
        )
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["vector_memory"] = {
            "status": "skipped",
            "reason": "fast_policy_identity",
        }
        updated_state.metadata["context_receipt"] = assistant_payload[
            "context_receipt"
        ]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        updated_state.metadata["model_used"] = "policy_only"
        updated_state.metadata["fallback_used"] = False
        await memory_manager.update_session(updated_state)
        return updated_state

    if auto_decision.state in {
        MemoryDecisionState.save_active,
        MemoryDecisionState.save_pending_review,
        MemoryDecisionState.ask_clarification,
        MemoryDecisionState.reject_protected,
    }:
        if (
            auto_decision.state == MemoryDecisionState.save_active
            and auto_decision.candidate is not None
        ):
            saved_record = persistent_memory_manager.upsert_active_memory(
                content=auto_decision.candidate.content,
                source="user_explicit",
                memory_type=auto_decision.candidate.memory_type,
                tags=auto_decision.candidate.tags,
                confidence=auto_decision.candidate.confidence,
            )
            if auto_decision.visible_text:
                visible_text = auto_decision.visible_text
            else:
                visible_text = "Got it — I’ll keep that preference going forward."
            auto_receipt = persistent_memory_manager.compact_receipt([saved_record])
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt=_merge_focus_context_receipt(
                    {}, session_state.metadata
                ),
                operator_receipts=[],
                memory_receipts=[auto_receipt],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "auto_memory",
                    "brain_answer_source": "auto_memory_saved",
                    "intent_class": auto_decision.signal.value,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
                warnings=[],
                action_history_refs=[],
            )
            assistant_payload.update(
                {
                    "speech_act": auto_decision.signal.value,
                    "learned_record_id": saved_record.id,
                    "learning_layer": saved_record.layer,
                    "learning_status": saved_record.status,
                    "source_user_message": payload.raw_text,
                    "confidence": saved_record.confidence,
                    "requires_confirmation": False,
                    "protected_boundary": False,
                    "source_record_ids": [saved_record.id],
                }
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            updated_state.metadata["auto_memory_last_record_id"] = saved_record.id
            updated_state.metadata["auto_memory_receipt"] = auto_receipt
            await memory_manager.update_session(updated_state)
            return updated_state

        if (
            auto_decision.state == MemoryDecisionState.save_pending_review
            and auto_decision.candidate is not None
        ):
            pending_record = persistent_memory_manager.create_pending_memory(
                content=auto_decision.candidate.content,
                source="user_explicit",
                memory_type=auto_decision.candidate.memory_type,
                tags=auto_decision.candidate.tags,
            )
            visible_text = (
                auto_decision.visible_text
                or "Got it — I’ll keep that as an unverified memory candidate until proof is available."
            )
            auto_receipt = persistent_memory_manager.compact_receipt([pending_record])
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt=_merge_focus_context_receipt(
                    {}, session_state.metadata
                ),
                operator_receipts=[],
                memory_receipts=[auto_receipt],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "auto_memory",
                    "brain_answer_source": "auto_memory_pending_review",
                    "intent_class": auto_decision.signal.value,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
                warnings=[],
                action_history_refs=[],
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            updated_state.metadata["auto_memory_last_record_id"] = pending_record.id
            updated_state.metadata["auto_memory_receipt"] = auto_receipt
            await memory_manager.update_session(updated_state)
            return updated_state

        if auto_decision.state in {
            MemoryDecisionState.ask_clarification,
            MemoryDecisionState.reject_protected,
        }:
            visible_text = (
                auto_decision.visible_text
                or "I need more detail before I can save that."
            )
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt=_merge_focus_context_receipt(
                    {}, session_state.metadata
                ),
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "auto_memory",
                    "brain_answer_source": auto_decision.state.value,
                    "intent_class": auto_decision.signal.value,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
                warnings=[],
                action_history_refs=[],
            )
            assistant_payload.update(
                {
                    "speech_act": auto_decision.signal.value,
                    "learning_status": "pending_clarification",
                    "learning_layer": "memory",
                    "source_user_message": payload.raw_text,
                    "confidence": 0.0,
                    "requires_confirmation": True,
                    "protected_boundary": False,
                    "source_record_ids": [],
                }
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

    inference_state = session_state.model_copy(deep=True)
    inference_state.metadata["active_focus"] = session_state.metadata.get(
        "active_focus", {}
    )
    auto_memory_prompt = _auto_memory_prompt_from_metadata(session_state.metadata)
    if auto_memory_prompt:
        inference_state.messages.insert(
            0,
            ConversationMessage(role="system", content=auto_memory_prompt),
        )
    intent_class = _classify_speech_act(payload.raw_text)
    active_focus_instruction = _extract_active_focus_instruction(payload.raw_text)

    current_history = get_history(session_state.metadata)
    action_history_refs = [
        str(item.get("action_id", ""))
        for item in current_history[-5:]
        if isinstance(item, dict) and str(item.get("action_id", ""))
    ]

    async def _store_operator_response(
        operator_action: OperatorExecution,
    ) -> SessionState:
        visible_text = sanitize_visible_answer_text(operator_action.answer.strip())
        assistant_output = visible_text
        structured_receipt = operator_action.result.structured_receipt()
        operator_result = structured_receipt.get("operator_result", {})
        if not isinstance(operator_result, dict):
            operator_result = {}

        stored_history = get_history(session_state.metadata)
        if operator_action.record_history:
            stored_history = append_history(session_state.metadata, structured_receipt)
        stored_action_history_refs = [
            str(item.get("action_id", ""))
            for item in stored_history[-5:]
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
            context_receipt=_merge_focus_context_receipt({}, session_state.metadata),
            operator_receipts=[structured_receipt],
            operator_result=operator_result,
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=warnings,
            action_history_refs=stored_action_history_refs,
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
        updated_state.metadata["operator_last_action"] = (
            operator_action.result.model_dump(mode="json")
        )
        updated_state.metadata["operator_action_history"] = stored_history
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        if (
            operator_action.result.action_name
            in {"repo_status", "operator_status_report"}
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

    early_operator_text = _normalize_intent_text(payload.raw_text)
    operator_mode_enabled = bool(
        payload.operator_mode
        or session_state.metadata.get("operator_mode_enabled", False)
    )
    latest_applied_patch = (
        brain_context_manager.answer_contract._latest_applied_patch_proposal(
            session_state.messages,
            session_state.metadata,
        )
    )
    is_post_apply_targeted_validation_prompt = (
        brain_context_manager.answer_contract._is_post_apply_targeted_validation_request(
            early_operator_text
        )
        and latest_applied_patch is not None
    )
    is_v1e_operator_prompt = (
        early_operator_text
        in {
            "check the repo",
            "give me repo status",
            "repo status",
            "what is git status",
            "what branch are we on",
            "is the working tree clean",
            "run validation",
            "run the checks",
            "run checks",
            "what's failing",
            "what is failing",
            "fix the first failure",
            "fix first failure",
            "fix it",
        }
        or "preview this patch" in early_operator_text
        or "preview the patch" in early_operator_text
        or "apply this patch" in early_operator_text
        or "apply the patch" in early_operator_text
        or "apply this approved patch" in early_operator_text
        or "apply approved patch" in early_operator_text
    )

    is_first_class_operator_prompt = operator_manager.is_first_class_operator_prompt(
        payload.raw_text
    )

    if is_first_class_operator_prompt and not is_post_apply_targeted_validation_prompt:
        github_operator_action = operator_manager.try_handle_chat(
            payload.raw_text,
            session_metadata=session_state.metadata,
            operator_mode_enabled=operator_mode_enabled,
        )
        if github_operator_action is not None:
            return await _store_operator_response(github_operator_action)

    if is_v1e_operator_prompt and not is_post_apply_targeted_validation_prompt:
        early_operator_action = operator_manager.try_handle_chat(
            payload.raw_text,
            session_metadata=session_state.metadata,
            operator_mode_enabled=operator_mode_enabled,
        )
        if early_operator_action is not None:
            return await _store_operator_response(early_operator_action)

    if _is_runtime_clock_question(payload.raw_text):
        visible_text, clock_context_receipt = _runtime_clock_answer()
        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "runtime_clock",
            "brain_answer_source": "runtime_clock",
            "intent_class": "status_question",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt(
                clock_context_receipt, session_state.metadata
            ),
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance=policy_provenance,
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
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    learned_rule_answer, learned_rule_record = _applies_learned_rule(
        payload.raw_text,
        brain_context_manager.loader.load_records(),
    )
    if learned_rule_answer is not None and learned_rule_record is not None:
        visible_text = sanitize_visible_answer_text(learned_rule_answer.strip())
        record_id = learned_rule_record.record_id
        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "learned_rule",
            "brain_answer_source": "learned_rule_applied",
            "intent_class": "learned_rule_applied",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt(
                _intent_context_receipt(
                    intent_class="learned_rule_applied",
                    record_id=record_id,
                    source="learned_rule",
                    persistence="durable",
                    status="active",
                ),
                session_state.metadata,
            ),
            operator_receipts=[],
            memory_receipts=[f"{learned_rule_record.layer.value}: {record_id}"],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=[],
            action_history_refs=action_history_refs,
        )
        assistant_payload.update(
            {
                "speech_act": "learned_rule_applied",
                "learned_record_id": record_id,
                "source_record_ids": [record_id],
            }
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
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    if intent_class in {
        "user_correction",
        "communication_preference",
        "workflow_habit_learning",
        "hallucination_guard",
        "answer_style_preference",
        "diagnostic_rule",
    } and not brain_context_manager.answer_contract._is_post_apply_intent_request(
        _normalize_intent_text(payload.raw_text)
    ):
        if intent_class == "user_correction":
            lesson_text = _extract_correction_text(payload.raw_text)
        elif intent_class == "workflow_habit_learning":
            lesson_text = _extract_workflow_habit_text(payload.raw_text)
        else:
            lesson_text = _extract_preference_text(payload.raw_text)

        protected_boundary = (
            intent_class == "protected_mutation_request"
            or _learning_protected_boundary(payload.raw_text)
        )
        requires_confirmation = False
        confidence = _speech_act_confidence(intent_class, lesson_text)

        if protected_boundary:
            visible_text = (
                "I cannot auto-learn that rule because it would cross a protected boundary "
                "(safety, destructive authority, secrets, or unverified truth claims)."
            )
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt={
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: protected-boundary",
                    "context_receipts": [],
                    "record_ids": [],
                },
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "intent_router",
                    "brain_answer_source": "learning_protected_boundary",
                    "intent_class": intent_class,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
                warnings=["protected learning boundary"],
                action_history_refs=action_history_refs,
            )
            assistant_payload.update(
                {
                    "speech_act": intent_class,
                    "learned_record_id": None,
                    "learning_layer": None,
                    "learning_status": "rejected",
                    "source_user_message": payload.raw_text,
                    "confidence": confidence,
                    "requires_confirmation": True,
                    "protected_boundary": True,
                }
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

        if _is_emotional_unclear_feedback(lesson_text) or _needs_learning_clarification(
            intent_class, lesson_text
        ):
            requires_confirmation = True
            visible_text = "I understand. Tell me the exact behavior you want changed in one sentence, and I will save that as a learned rule."
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt={
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: pending-clarification",
                    "context_receipts": [],
                    "record_ids": [],
                },
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "intent_router",
                    "brain_answer_source": "learning_clarification_pending",
                    "intent_class": intent_class,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
                warnings=[],
                action_history_refs=action_history_refs,
            )
            assistant_payload.update(
                {
                    "speech_act": intent_class,
                    "learned_record_id": None,
                    "learning_layer": None,
                    "learning_status": "pending_clarification",
                    "source_user_message": payload.raw_text,
                    "confidence": confidence,
                    "requires_confirmation": True,
                    "protected_boundary": False,
                }
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

        learning_layer = _speech_act_to_learning_layer(intent_class)
        lesson_norm = _normalize_intent_text(lesson_text)
        proof_required = intent_class in {"hallucination_guard", "diagnostic_rule"} or (
            (
                "proof" in lesson_norm
                or "do not guess" in lesson_norm
                or "don't guess" in lesson_norm
            )
            and any(token in lesson_norm for token in ("ci", "github", "status"))
        )
        learning_status = "active" if confidence >= 0.8 else "pending_review"
        memory_type = (
            "diagnostic_rule"
            if intent_class == "diagnostic_rule"
            else "hallucination_guard"
            if intent_class == "hallucination_guard"
            else "answer_style"
            if intent_class == "answer_style_preference"
            else "workflow_rule"
            if intent_class == "workflow_habit_learning"
            else "preference"
        )

        learned = brain_context_manager.loader.create_learned_rule_record(
            layer=learning_layer,
            title=_learning_rule_title(intent_class, lesson_text),
            summary=lesson_text,
            body=f"Learned rule from Otis conversation: {lesson_text}",
            tags=_learning_rule_tags(intent_class, proof_required),
            source_user_message=payload.raw_text,
            confidence=confidence,
            memory_type=memory_type,
            status=learning_status,
            proof_required=proof_required,
        )

        _append_learning_signal(
            session_state.metadata,
            {
                "type": intent_class,
                "content": lesson_text,
                "source": "direct_user_instruction",
                "record_id": learned.record_id,
                "status": learning_status,
            },
        )

        learning_label = (
            "communication/workflow rule"
            if learning_layer == BrainLayer.KNOWLEDGE
            else "communication preference"
        )
        visible_text = f"Understood. I saved that as a {learning_label} and will apply it going forward."

        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_learning_context_receipt(
                learning_layer=learning_layer,
                learned_record_id=learned.record_id,
                proof_required=proof_required,
            ),
            operator_receipts=[],
            memory_receipts=[f"{learning_layer.value}: {learned.record_id}"],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "intent_router",
                "brain_answer_source": "learning_rule_saved",
                "intent_class": intent_class,
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
            },
            warnings=[],
            action_history_refs=action_history_refs,
        )
        assistant_payload.update(
            {
                "speech_act": intent_class,
                "learned_record_id": learned.record_id,
                "learning_layer": learning_layer.value,
                "learning_status": learning_status,
                "source_user_message": payload.raw_text,
                "confidence": confidence,
                "requires_confirmation": requires_confirmation,
                "protected_boundary": False,
                "source_record_ids": [learned.record_id],
            }
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    normalized_question = _normalize_intent_text(payload.raw_text)
    latest_applied_patch = (
        brain_context_manager.answer_contract._latest_applied_patch_proposal(
            session_state.messages,
            session_state.metadata,
        )
    )
    is_post_apply_file_check_prompt = (
        brain_context_manager.answer_contract._is_post_apply_verify_request(
            normalized_question
        )
        or brain_context_manager.answer_contract._is_post_apply_preview_request(
            normalized_question
        )
        or brain_context_manager.answer_contract._is_post_apply_targeted_validation_request(
            normalized_question
        )
    )
    is_post_apply_full_test_prompt = (
        brain_context_manager.answer_contract._is_post_apply_full_test_guard_request(
            normalized_question
        )
        and latest_applied_patch is not None
    )
    prioritize_artifact_over_build_guard = (
        brain_context_manager.answer_contract._prioritize_artifact_over_build_guard(
            normalized_question
        )
    )
    is_artifact_patch_lane_prompt = (
        brain_context_manager.answer_contract._is_patch_proposal_request(
            normalized_question
        )
        or brain_context_manager.answer_contract._is_patch_apply_request(
            normalized_question
        )
        or brain_context_manager.answer_contract._is_preview_artifact_request(
            normalized_question
        )
        or brain_context_manager.answer_contract._looks_like_artifact_edit(
            normalized_question
        )
        or brain_context_manager.answer_contract._is_sandbox_build_request(
            normalized_question
        )
        or is_post_apply_file_check_prompt
        or is_post_apply_full_test_prompt
        or prioritize_artifact_over_build_guard
    )

    if is_artifact_patch_lane_prompt and active_focus_instruction is None:
        brain_context = brain_context_manager.build_context_for_question(
            payload.raw_text
        )
        inference_state.messages.insert(
            0,
            ConversationMessage(role="system", content=brain_context.prompt),
        )
        try:
            artifact_response = await brain_context_manager.code_artifact_response(
                payload.raw_text,
                session_messages=[
                    msg.model_dump(mode="json") for msg in session_state.messages
                ],
                session_metadata=session_state.metadata,
            )
        except RuntimeError as artifact_error:
            artifact_error_text = str(artifact_error).lower()
            if (
                "artifact revision failed validation" in artifact_error_text
                or "artifact generation failed validation" in artifact_error_text
            ):
                brain_answer_source = (
                    "artifact_revision_error"
                    if "artifact revision failed validation" in artifact_error_text
                    else "artifact_generation_error"
                )
                visible_text = sanitize_visible_answer_text(str(artifact_error).strip())
                assistant_payload = build_assistant_payload(
                    visible_text=visible_text,
                    context_receipt=_merge_focus_context_receipt(
                        brain_context.receipt, session_state.metadata
                    ),
                    operator_receipts=[],
                    memory_receipts=[],
                    model_use_receipt={},
                    policy_provenance={
                        "answer_source": "brain_policy",
                        "policy_source": "answer_contract",
                        "brain_answer_source": brain_answer_source,
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
                updated_state.metadata["answer_provenance"] = assistant_payload[
                    "policy_provenance"
                ]
                updated_state.metadata["vector_memory"] = vector_memory_receipt
                updated_state.metadata["context_receipt"] = assistant_payload[
                    "context_receipt"
                ]
                updated_state.metadata["last_assistant_payload"] = assistant_payload
                await memory_manager.update_session(updated_state)
                return updated_state
            raise

        if artifact_response is not None:
            visible_text = str(artifact_response.get("visible_text", "")).strip()
            artifact_provenance = artifact_response.get("provenance", {})
            if not isinstance(artifact_provenance, dict):
                artifact_provenance = {}
            brain_answer_source = (
                "commit_proposal_request"
                if "commit_proposal" in (artifact_provenance or {})
                else "code_artifact_request"
            )
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt=artifact_response.get("context_receipt"),
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "answer_contract",
                    "brain_answer_source": brain_answer_source,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                    **artifact_provenance,
                },
                warnings=[],
                action_history_refs=action_history_refs,
                code_artifact=artifact_response.get("code_artifact"),
                code_artifacts=artifact_response.get("code_artifacts"),
                artifact_patch_proposal=artifact_response.get(
                    "artifact_patch_proposal"
                ),
                site_bundle=artifact_response.get("site_bundle"),
                site_bundle_patch_proposals=artifact_response.get(
                    "site_bundle_patch_proposals"
                ),
                commit_proposal=artifact_response.get("commit_proposal"),
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

    if (
        intent_class == "implementation_task"
        and not is_artifact_patch_lane_prompt
        and not prioritize_artifact_over_build_guard
    ):
        visible_text = _build_task_guard_answer()
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt({}, session_state.metadata),
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "operator_guard",
                "brain_answer_source": "implementation_task_guard",
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    active_focus_instruction = _extract_active_focus_instruction(payload.raw_text)
    if (
        _is_active_focus_candidate(payload.raw_text)
        and active_focus_instruction is None
    ):
        visible_text = (
            "I heard an Active Focus change, but the target focus is unclear. "
            "What exact focus should I set right now?"
        )
        session_state.metadata["pending_focus_update"] = {
            "status": "pending_clarification",
            "source": "direct_user_instruction",
            "raw_text": payload.raw_text,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt={
                "compact": "Context receipt: Active Focus pending clarification.",
                "context_receipts": [
                    {
                        "layer": "active_focus",
                        "record_id": "FOCUS-PENDING",
                        "source": "direct_user_instruction",
                        "persistence": "none",
                        "status": "pending",
                    }
                ],
                "record_ids": ["FOCUS-PENDING"],
            },
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "active_focus_intent",
                "brain_answer_source": "active_focus_clarification_pending",
                "intent_class": "active_focus_update",
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
                "protected": False,
                "action": "stage_pending_focus_update",
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    if (
        _is_communication_workflow_focus(session_state.metadata)
        and _is_focus_guided_follow_up(payload.raw_text)
        and not _is_local_scan_or_operator_prompt(payload.raw_text)
    ):
        active_focus_payload = session_state.metadata.get("active_focus", {})
        focus_id = str(
            active_focus_payload.get("id", "XV7-FOCUS-UNKNOWN")
            if isinstance(active_focus_payload, dict)
            else "XV7-FOCUS-UNKNOWN"
        )
        active_focus_text = (
            str(active_focus_payload.get("summary", "")).strip()
            if isinstance(active_focus_payload, dict)
            else ""
        )
        visible_text = _active_focus_guided_plan_answer()
        context_receipt = _active_focus_guided_context_receipt(focus_id)
        source_record_ids = list(context_receipt.get("record_ids", []))
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt(
                context_receipt, session_state.metadata
            ),
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "active_focus_guided",
                "brain_answer_source": "active_focus_guided_plan",
                "intent_class": "active_focus_follow_up",
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
                "active_focus_id": focus_id,
                "focus_applied": True,
                "response_mode": "active_focus_guided",
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        updated_state.metadata["active_focus_id"] = focus_id
        updated_state.metadata["focus_applied"] = True
        updated_state.metadata["focus_mode"] = "communication_workflow_learning"
        updated_state.metadata["active_focus_text"] = active_focus_text
        updated_state.metadata["context_includes_focus"] = True
        updated_state.metadata["response_mode"] = "active_focus_guided"
        updated_state.metadata["model_used"] = "policy_only"
        updated_state.metadata["fallback_used"] = False
        updated_state.metadata["source_record_ids"] = source_record_ids
        await memory_manager.update_session(updated_state)
        return updated_state

    if active_focus_instruction is not None:
        if _is_unclear_focus_instruction(active_focus_instruction):
            visible_text = (
                "I heard an Active Focus change, but it is still too broad. "
                "What exact focus should I set right now?"
            )
            session_state.metadata["pending_focus_update"] = {
                "status": "pending_clarification",
                "source": "direct_user_instruction",
                "raw_text": payload.raw_text,
                "candidate_focus": active_focus_instruction,
            }
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt={
                    "compact": "Context receipt: Active Focus pending clarification.",
                    "context_receipts": [
                        {
                            "layer": "active_focus",
                            "record_id": "FOCUS-PENDING",
                            "source": "direct_user_instruction",
                            "persistence": "none",
                            "status": "pending",
                        }
                    ],
                    "record_ids": ["FOCUS-PENDING"],
                },
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "active_focus_intent",
                    "brain_answer_source": "active_focus_clarification_pending",
                    "intent_class": "active_focus_update",
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                    "protected": False,
                    "action": "stage_pending_focus_update",
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state

        focus_summary = active_focus_instruction.strip()
        focus_record = brain_context_manager.apply_active_focus_instruction(
            focus_summary
        )
        focus_payload: dict[str, Any] = {
            "id": focus_record.record_id,
            "title": focus_record.title,
            "summary": focus_summary,
            "source": "direct_user_instruction",
        }
        persisted = await _persist_session_focus_fact(
            session_id=session_id,
            focus_payload=focus_payload,
        )
        focus_payload["persistence"] = "brain_record_saved"
        focus_payload["session_fact_saved"] = persisted
        session_state.metadata["active_focus"] = focus_payload
        session_state.metadata.pop("pending_focus_update", None)

        visible_text = (
            "I'm updating Active Focus.\n\n"
            "New Active Focus:\n"
            f"{focus_record.record_id} - {focus_summary}\n\n"
            "I will treat this as the current priority until you change it."
        )

        context_receipt = {
            "compact": (
                f"Context receipt: Active Focus {focus_record.record_id} "
                "(intent_class=active_focus_update; action=create_active_focus_record; "
                f"source=direct_user_instruction; persistence={focus_payload['persistence']})."
            ),
            "context_receipts": [
                {
                    "layer": "active_focus",
                    "record_id": focus_record.record_id,
                    "intent_class": "active_focus_update",
                    "action": "create_active_focus_record",
                    "source": "direct_user_instruction",
                    "persistence": focus_payload["persistence"],
                    "status": "active",
                }
            ],
            "record_ids": [focus_record.record_id],
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
                "protected": False,
                "action": "create_active_focus_record",
                "current_focus": {
                    "record_id": focus_record.record_id,
                    "title": focus_record.title,
                    "summary": focus_record.summary,
                },
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
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

    learned_records = brain_context_manager.loader.load_records()
    if "session_metadata_learned_rule_records" not in session_state.metadata:
        session_rule_records: list[BrainRecord] = []
        for previous_message in session_state.messages:
            previous_metadata = getattr(previous_message, "metadata", {})
            if not isinstance(previous_metadata, dict):
                continue

            learned_record_id = str(
                previous_metadata.get("learned_record_id", "")
            ).strip()
            learning_status = str(previous_metadata.get("learning_status", "")).strip()
            speech_act = str(previous_metadata.get("speech_act", "")).strip()
            source_user_message = str(
                previous_metadata.get("source_user_message", "")
            ).strip()

            if (
                not learned_record_id
                or learning_status != "active"
                or not source_user_message
                or speech_act
                not in {
                    "user_correction",
                    "communication_preference",
                    "workflow_habit_learning",
                    "hallucination_guard",
                    "answer_style_preference",
                    "diagnostic_rule",
                }
            ):
                continue

            source_norm = _normalize_intent_text(source_user_message)
            proof_required = speech_act in {
                "hallucination_guard",
                "diagnostic_rule",
            } or (
                (
                    "proof" in source_norm
                    or "do not guess" in source_norm
                    or "don't guess" in source_norm
                )
                and any(token in source_norm for token in ("ci", "github", "status"))
            )

            session_rule_records.append(
                BrainRecord(
                    record_id=learned_record_id,
                    layer=_speech_act_to_learning_layer(speech_act),
                    title=_learning_rule_title(speech_act, source_user_message),
                    summary=source_user_message,
                    body=f"Learned rule from session metadata: {source_user_message}",
                    memory_type=(
                        "diagnostic_rule"
                        if speech_act == "diagnostic_rule"
                        else "hallucination_guard"
                        if speech_act == "hallucination_guard"
                        else "answer_style"
                        if speech_act == "answer_style_preference"
                        else "workflow_rule"
                        if speech_act == "workflow_habit_learning"
                        else "preference"
                    ),
                    status="active",
                    tags=_learning_rule_tags(speech_act, proof_required),
                )
            )

        if session_rule_records:
            learned_records = [*learned_records, *session_rule_records]
        session_state.metadata["session_metadata_learned_rule_records"] = [
            record.record_id for record in session_rule_records
        ]
    learned_prompt = _learned_rules_prompt(learned_records)
    if learned_prompt:
        inference_state.messages.insert(
            0,
            ConversationMessage(role="system", content=learned_prompt),
        )

    learned_answer, learned_record = _applies_learned_rule(
        payload.raw_text,
        learned_records,
    )
    if learned_answer is None:
        normalized_for_learning_fallback = _normalize_intent_text(payload.raw_text)
        is_ci_github_status_prompt = bool(
            re.search(
                r"\b(github\s+actions?|ci\s+status|build\s+status|checks?\s+status|did\s+ci|is\s+ci)\b",
                normalized_for_learning_fallback,
            )
        )
        session_learning_signals = session_state.metadata.get("learning_signals", [])
        if is_ci_github_status_prompt and isinstance(session_learning_signals, list):
            for signal in reversed(session_learning_signals):
                if not isinstance(signal, dict):
                    continue
                signal_type = str(signal.get("type", "")).strip()
                signal_status = str(signal.get("status", "")).strip()
                signal_content = _normalize_intent_text(str(signal.get("content", "")))
                signal_record_id = str(signal.get("record_id", "")).strip()
                if (
                    signal_status == "active"
                    and signal_record_id
                    and signal_type in {"hallucination_guard", "diagnostic_rule"}
                    and (
                        "proof" in signal_content
                        or "do not guess" in signal_content
                        or "don't guess" in signal_content
                    )
                    and any(
                        token in signal_content for token in ("ci", "github", "status")
                    )
                ):
                    learned_answer = (
                        "Understood. Per your learned diagnostic rule, I will require proof before claiming CI/GitHub status. "
                        "I do not have live proof in this turn."
                    )
                    learned_record = BrainRecord(
                        layer=BrainLayer.KNOWLEDGE,
                        record_id=signal_record_id,
                        title="Session learned proof rule",
                        summary=str(signal.get("content", "")),
                        body=str(signal.get("content", "")),
                        tags=["learning", "learned-rule", "proof-required"],
                        status="active",
                    )
                    break

    if learned_answer and learned_record is not None:
        learning_layer = learned_record.layer
        visible_text = sanitize_visible_answer_text(learned_answer)
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt(
                _learning_context_receipt(
                    learning_layer=learning_layer,
                    learned_record_id=learned_record.record_id,
                    proof_required="proof-required"
                    in {str(tag).lower() for tag in learned_record.tags},
                ),
                session_state.metadata,
            ),
            operator_receipts=[],
            memory_receipts=[f"{learning_layer.value}: {learned_record.record_id}"],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "learned_rules",
                "brain_answer_source": "learned_rule_applied",
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
                "learned_record_id": learned_record.record_id,
            },
            warnings=[],
            action_history_refs=action_history_refs,
        )
        assistant_payload.update(
            {
                "speech_act": "learned_rule_applied",
                "learned_record_id": learned_record.record_id,
                "learning_layer": learned_record.layer.value,
                "learning_status": learned_record.status,
                "source_user_message": payload.raw_text,
                "confidence": 1.0,
                "requires_confirmation": False,
                "protected_boundary": False,
                "source_record_ids": [learned_record.record_id],
            }
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    operator_action = operator_manager.try_handle_chat(
        payload.raw_text,
        session_metadata=session_state.metadata,
        operator_mode_enabled=operator_mode_enabled,
    )
    if operator_action is not None:
        visible_text = sanitize_visible_answer_text(operator_action.answer.strip())
        assistant_output = visible_text
        structured_receipt = operator_action.result.structured_receipt()
        operator_result = structured_receipt.get("operator_result", {})
        if not isinstance(operator_result, dict):
            operator_result = {}

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
            context_receipt=_merge_focus_context_receipt({}, session_state.metadata),
            operator_receipts=[structured_receipt],
            operator_result=operator_result,
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
        updated_state.metadata["operator_last_action"] = (
            operator_action.result.model_dump(mode="json")
        )
        updated_state.metadata["operator_action_history"] = current_history
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        if (
            operator_action.result.action_name
            in {"repo_status", "operator_status_report"}
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

    normalized_for_commit_check = _normalize_intent_text(payload.raw_text)
    is_explicit_commit_approval = (
        brain_context_manager.answer_contract._is_commit_approval_request(
            normalized_for_commit_check
        )
    )
    if (
        _is_build_follow_up_prompt(payload.raw_text)
        and _lacks_verified_operator_success(session_state.metadata)
        and not is_explicit_commit_approval
    ):
        visible_text = (
            "I cannot report implementation completion from this turn because the last relevant operator action is not verified as successful. "
            "No files were changed. No tests were run. No commit or push occurred."
        )
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt({}, session_state.metadata),
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "operator_truth_guard",
                "brain_answer_source": "operator_follow_up_guard",
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
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
            context_receipt=_merge_focus_context_receipt({}, session_state.metadata),
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

    learned_rule_answer, learned_rule_record = _applies_learned_rule(
        payload.raw_text,
        learned_records,
    )
    if learned_rule_answer is not None and learned_rule_record is not None:
        visible_text = sanitize_visible_answer_text(learned_rule_answer.strip())
        record_id = learned_rule_record.record_id
        policy_provenance = {
            "answer_source": "brain_policy",
            "policy_source": "learned_rule",
            "brain_answer_source": "learned_rule_applied",
            "intent_class": "learned_rule_applied",
            "request_id": str(uuid4()),
            "session_id": str(session_id),
            "runtime_model_inference_proven": False,
        }
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=_merge_focus_context_receipt(
                _intent_context_receipt(
                    intent_class="learned_rule_applied",
                    record_id=record_id,
                    source="learned_rule",
                    persistence="durable",
                    status="active",
                ),
                session_state.metadata,
            ),
            operator_receipts=[],
            memory_receipts=[f"{learned_rule_record.layer.value}: {record_id}"],
            model_use_receipt={},
            policy_provenance=policy_provenance,
            warnings=[],
            action_history_refs=action_history_refs,
        )
        assistant_payload.update(
            {
                "speech_act": "learned_rule_applied",
                "learned_record_id": record_id,
                "source_record_ids": [record_id],
            }
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
        updated_state.metadata["answer_provenance"] = policy_provenance
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

    brain_context = brain_context_manager.build_context_for_question(payload.raw_text)
    inference_state.messages.insert(
        0,
        ConversationMessage(role="system", content=brain_context.prompt),
    )
    try:
        artifact_response = await brain_context_manager.code_artifact_response(
            payload.raw_text,
            session_messages=[
                msg.model_dump(mode="json") for msg in session_state.messages
            ],
            session_metadata=session_state.metadata,
        )
    except RuntimeError as artifact_error:
        artifact_error_text = str(artifact_error).lower()
        if (
            "artifact revision failed validation" in artifact_error_text
            or "artifact generation failed validation" in artifact_error_text
        ):
            brain_answer_source = (
                "artifact_revision_error"
                if "artifact revision failed validation" in artifact_error_text
                else "artifact_generation_error"
            )
            visible_text = sanitize_visible_answer_text(str(artifact_error).strip())
            assistant_payload = build_assistant_payload(
                visible_text=visible_text,
                context_receipt=_merge_focus_context_receipt(
                    brain_context.receipt, session_state.metadata
                ),
                operator_receipts=[],
                memory_receipts=[],
                model_use_receipt={},
                policy_provenance={
                    "answer_source": "brain_policy",
                    "policy_source": "answer_contract",
                    "brain_answer_source": brain_answer_source,
                    "request_id": str(uuid4()),
                    "session_id": str(session_id),
                    "runtime_model_inference_proven": False,
                },
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
            updated_state.metadata["answer_provenance"] = assistant_payload[
                "policy_provenance"
            ]
            updated_state.metadata["vector_memory"] = vector_memory_receipt
            updated_state.metadata["context_receipt"] = assistant_payload[
                "context_receipt"
            ]
            updated_state.metadata["last_assistant_payload"] = assistant_payload
            await memory_manager.update_session(updated_state)
            return updated_state
        raise

    if artifact_response is not None:
        visible_text = str(artifact_response.get("visible_text", "")).strip()
        artifact_provenance = artifact_response.get("provenance", {})
        if not isinstance(artifact_provenance, dict):
            artifact_provenance = {}
        brain_answer_source = (
            "commit_proposal_request"
            if "commit_proposal" in (artifact_provenance or {})
            else "code_artifact_request"
        )
        assistant_payload = build_assistant_payload(
            visible_text=visible_text,
            context_receipt=artifact_response.get("context_receipt"),
            operator_receipts=[],
            memory_receipts=[],
            model_use_receipt={},
            policy_provenance={
                "answer_source": "brain_policy",
                "policy_source": "answer_contract",
                "brain_answer_source": brain_answer_source,
                "request_id": str(uuid4()),
                "session_id": str(session_id),
                "runtime_model_inference_proven": False,
                **artifact_provenance,
            },
            warnings=[],
            action_history_refs=[
                str(item.get("action_id", ""))
                for item in get_history(session_state.metadata)[-5:]
                if isinstance(item, dict) and str(item.get("action_id", ""))
            ],
            code_artifact=artifact_response.get("code_artifact"),
            code_artifacts=artifact_response.get("code_artifacts"),
            artifact_patch_proposal=artifact_response.get("artifact_patch_proposal"),
            site_bundle=artifact_response.get("site_bundle"),
            site_bundle_patch_proposals=artifact_response.get(
                "site_bundle_patch_proposals"
            ),
            commit_proposal=artifact_response.get("commit_proposal"),
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
        updated_state.metadata["answer_provenance"] = assistant_payload[
            "policy_provenance"
        ]
        updated_state.metadata["vector_memory"] = vector_memory_receipt
        updated_state.metadata["context_receipt"] = assistant_payload["context_receipt"]
        updated_state.metadata["last_assistant_payload"] = assistant_payload
        await memory_manager.update_session(updated_state)
        return updated_state

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
        effective_context_receipt = _merge_focus_context_receipt(
            effective_context_receipt,
            session_state.metadata,
        )
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

    learned_rule_texts = [
        str((getattr(record, "summary", "") or getattr(record, "body", ""))).strip()
        for record in _active_learned_rules(learned_records)
        if str((getattr(record, "summary", "") or getattr(record, "body", ""))).strip()
    ]
    active_focus_summary = ""
    active_focus_payload = session_state.metadata.get("active_focus")
    if isinstance(active_focus_payload, dict):
        active_focus_summary = str(active_focus_payload.get("summary", "")).strip()

    inference_state.messages.insert(
        0,
        ConversationMessage(
            role="system",
            content=build_commercial_system_prompt(
                active_focus=active_focus_summary,
                learned_rules=learned_rule_texts,
                session_facts=facts,
            ),
        ),
    )
    inference_state.messages.insert(
        0,
        ConversationMessage(role="system", content=_runtime_clock_system_prompt()),
    )

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
            context_receipt=_merge_focus_context_receipt(
                brain_context.receipt,
                session_state.metadata,
            ),
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
    updated_state.metadata["context_receipt"] = _merge_focus_context_receipt(
        brain_context.receipt,
        session_state.metadata,
    )
    updated_state.metadata["last_assistant_payload"] = updated_state.messages[
        -1
    ].metadata
    await memory_manager.update_session(updated_state)

    return updated_state
