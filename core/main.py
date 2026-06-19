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
from core.kernel import (
    KernelModeResolver,
    KernelRuntimeDependencies,
    XoduzApplicationKernel,
)
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


def _build_xoduz_kernel() -> XoduzApplicationKernel:
    kernel_resolution_dependencies = KernelRuntimeDependencies(
        answer_contract=brain_context_manager.answer_contract,
        operator_manager=operator_manager,
        persistent_memory_manager=persistent_memory_manager,
        memory_auto_pilot=memory_auto_pilot,
        classify_speech_act=_classify_speech_act,
        extract_active_focus_instruction=_extract_active_focus_instruction,
        active_focus_candidate_checker=_is_active_focus_candidate,
        is_runtime_clock_question=_is_runtime_clock_question,
        normalize_text=_normalize_intent_text,
    )
    return XoduzApplicationKernel(
        mode_resolver=KernelModeResolver(),
        resolution_dependencies=kernel_resolution_dependencies,
        execute_resolved=lambda session_id, payload, resolved_mode, kernel_plan: _legacy_add_session_message(
            session_id,
            payload,
            resolved_mode=resolved_mode,
            kernel_plan=kernel_plan,
        ),
        load_session=memory_manager.get_session,
        normalize_message=_normalize_intent_text,
    )

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
    return await _build_xoduz_kernel().handle_request(session_id, payload)


async def _legacy_add_session_message(
    session_id: UUID,
    payload: AddMessageRequest,
    *,
    resolved_mode: str | None = None,
    kernel_plan: dict[str, Any] | None = None,
) -> SessionState:
    from core.api.session_message_handler import (
        bind_main_dependencies as _bind_session_message_handler_dependencies,
        legacy_add_session_message as _legacy_add_session_message_impl,
    )
    import sys

    _bind_session_message_handler_dependencies(sys.modules[__name__])
    return await _legacy_add_session_message_impl(
        session_id,
        payload,
        resolved_mode=resolved_mode,
        kernel_plan=kernel_plan,
    )
