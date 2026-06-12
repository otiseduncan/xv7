from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal
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
from core.brain.schema import BrainLayer, BrainRecord
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


class BrainRecordUpdateRequest(BaseModel):
    """Payload for runtime brain record edits (stored as runtime overrides)."""

    model_config = ConfigDict(extra="forbid")

    layer: BrainLayer | None = None
    title: str | None = Field(default=None, min_length=1)
    body: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    status: (
        Literal[
            "active",
            "pending",
            "pending_review",
            "disabled",
            "archived",
        ]
        | None
    ) = None
    relevance_state: (
        Literal[
            "current",
            "historical",
            "superseded",
            "expired",
            "needs_review",
        ]
        | None
    ) = None
    superseded_by: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    applies_when: str | None = None
    review_reason: str | None = None
    last_reviewed_at: str | None = None


class BrainRecordRelevanceUpdateRequest(BaseModel):
    """Payload for setting brain record relevance lifecycle state."""

    model_config = ConfigDict(extra="forbid")

    relevance_state: Literal[
        "current",
        "historical",
        "superseded",
        "expired",
        "needs_review",
    ]
    superseded_by: str | None = None
    review_reason: str | None = None
    applies_when: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


class BrainRecordApplyRecommendationRequest(BaseModel):
    """Explicit approval payload for a staged hygiene recommendation."""

    model_config = ConfigDict(extra="forbid")

    recommendation_type: Literal[
        "mark_historical_via_runtime_override",
        "split_record",
    ]
    approve: bool = True
    operational_title: str | None = None
    operational_summary: str | None = None
    operational_body: str | None = None
    tags: list[str] | None = None
    layer: BrainLayer | None = None


class BrainRecordSplitRequest(BaseModel):
    """Payload for explicit split of mixed records into historical + current operational."""

    model_config = ConfigDict(extra="forbid")

    operational_title: str | None = None
    operational_summary: str | None = None
    operational_body: str | None = None
    tags: list[str] | None = None
    layer: BrainLayer | None = None
    review_reason: str | None = None
    applies_when: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


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
    deduped_memory_receipts: list[str] = []
    seen_memory_receipts: set[str] = set()
    for receipt in memory_receipts or []:
        key = str(receipt).strip()
        if not key or key in seen_memory_receipts:
            continue
        seen_memory_receipts.add(key)
        deduped_memory_receipts.append(key)

    return {
        "visible_text": visible_text,
        "context_receipt": context_receipt or {},
        "operator_receipts": operator_receipts or [],
        "memory_receipts": deduped_memory_receipts,
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


def _summary_from_body(body: str) -> str:
    cleaned = " ".join(body.split()).strip()
    if not cleaned:
        return "(empty)"
    if len(cleaned) <= 160:
        return cleaned
    return cleaned[:157].rstrip() + "..."


def _status_label(status: str) -> str:
    normalized = str(status or "").lower()
    if normalized in {"pending", "pending_review"}:
        return "pending"
    if normalized == "disabled":
        return "disabled"
    if normalized == "archived":
        return "archived"
    return "active"


def _brain_hygiene_classification(record: BrainRecord) -> dict[str, Any]:
    text_blob = " ".join(
        [
            record.title,
            record.summary,
            record.body,
            " ".join(record.tags),
            " ".join(record.evidence),
        ]
    ).lower()
    flags: list[str] = []
    recommendations: list[dict[str, Any]] = []
    reasons: list[str] = []
    effective_relevance = record.relevance_state

    has_phase_ref = bool(re.search(r"\bb\d+(?:\.\d+)?\b", text_blob))
    has_milestone_done = any(
        token in text_blob
        for token in (
            "completed",
            "passed",
            "verified",
            "proven",
            "milestone",
            "done",
            "shipped",
            "phase",
        )
    )
    has_operational_rule = any(
        token in text_blob
        for token in (
            "from now on",
            "current",
            "in progress",
            "must",
            "always",
            "operator mode",
            "working priority",
            "active focus",
            "should",
            "bridge",
        )
    )

    if has_phase_ref:
        flags.append("old_phase_reference")
        reasons.append("Contains legacy B-phase references.")
    if has_milestone_done:
        flags.append("completed_milestone")
        reasons.append("Contains completed/passed milestone language.")
    if has_phase_ref and has_milestone_done:
        flags.append("historical_candidate")
        if record.relevance_state == "current":
            effective_relevance = "historical"
            recommendations.append(
                {
                    "type": "mark_historical_via_runtime_override",
                    "record_id": record.record_id,
                    "approval_required": True,
                    "reason": "Contains old completed milestones without current-only scoping.",
                    "payload": {
                        "relevance_state": "historical",
                        "review_reason": "Contains completed or passed phase milestone references.",
                    },
                }
            )

    if has_phase_ref and has_milestone_done and has_operational_rule:
        flags.append("mixed_historical_and_operational")
        flags.append("mixed_historical_and_current")
        effective_relevance = "needs_review"
        reasons.append(
            "Contains old completed milestones and current operational bridge rule content."
        )
        recommendations.append(
            {
                "type": "split_record",
                "record_id": record.record_id,
                "approval_required": True,
                "reason": "Split historical milestones from current operational behavior.",
                "steps": [
                    "Mark existing record as historical or superseded via runtime override",
                    "Create a smaller current operational rule record via runtime override",
                ],
            }
        )

    if record.valid_until:
        try:
            until = datetime.fromisoformat(record.valid_until.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if until < now and record.relevance_state in {"current", "needs_review"}:
                flags.append("expired_window")
                effective_relevance = "expired"
        except Exception:
            pass

    return {
        "effective_relevance_state": effective_relevance,
        "flags": flags,
        "recommended_actions": recommendations,
        "reason": " ".join(dict.fromkeys(reasons)),
    }


def _serialize_brain_record(
    *,
    record: BrainRecord,
    source: str,
    path: Path,
) -> dict[str, Any]:
    hygiene = _brain_hygiene_classification(record)
    return {
        "record_id": record.record_id,
        "layer": record.layer.value,
        "title": record.title,
        "summary": record.summary,
        "body": record.body,
        "status": record.status,
        "status_label": _status_label(record.status),
        "relevance_state": record.relevance_state,
        "effective_relevance_state": hygiene["effective_relevance_state"],
        "superseded_by": record.superseded_by,
        "valid_from": record.valid_from,
        "valid_until": record.valid_until,
        "applies_when": record.applies_when,
        "review_reason": record.review_reason,
        "last_reviewed_at": record.last_reviewed_at,
        "priority": record.priority,
        "tags": list(record.tags),
        "source": source,
        "writable": source == "runtime_override",
        "source_label": "runtime_override" if source == "runtime_override" else "seed",
        "hygiene_flags": hygiene["flags"],
        "hygiene_recommendations": hygiene["recommended_actions"],
        "hygiene_reason": hygiene.get("reason", ""),
        "updated_at": brain_context_manager.loader.record_updated_at(path),
        "raw_record": record.model_dump(mode="json"),
    }


def _layer_token(layer: BrainLayer) -> str:
    return {
        BrainLayer.MEMORY: "MEMORY",
        BrainLayer.KNOWLEDGE: "KNOWLEDGE",
        BrainLayer.VERIFIED_STATUS: "VERIFIED",
        BrainLayer.ACTIVE_FOCUS: "FOCUS",
        BrainLayer.SYSTEM_PROMPT: "SYSTEM",
    }[layer]


def _next_record_id_for_layer(layer: BrainLayer) -> str:
    token = _layer_token(layer)
    records = brain_context_manager.loader.load_records()
    max_index = 0
    for record in records:
        match = re.match(rf"^XV7-{token}-(\d{{4}})$", record.record_id)
        if match is None:
            continue
        max_index = max(max_index, int(match.group(1)))
    return f"XV7-{token}-{max_index + 1:04d}"


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


ACTIVE_FOCUS_UPDATE_PREFIXES = (
    "focus on ",
    "focus or ",
    "active closest to focus on ",
    "active closest to focus or ",
    "from now on focus on ",
    "from now on focus or ",
    "change your active focus to ",
    "change your active closest to focus to ",
    "change active focus to ",
    "set your focus to ",
    "set active focus to ",
    "change your focus to ",
    "change my focus to ",
    "make your focus ",
    "your active focus is ",
    "from now on your focus is ",
    "your priority is ",
    "we need your focus to be ",
)

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
    "no, that is wrong",
    "no that is wrong",
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
    "don't say it that way",
    "dont say it that way",
    "remember i prefer",
    "prefer",
    "keep answers",
    "don't over-explain",
    "do not over-explain",
    "be direct",
)

WORKFLOW_HABIT_MARKERS = (
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

    def _cleanup_focus_text(raw_text: str) -> str:
        cleaned = raw_text.strip(" .!?,:")
        cleaned = re.sub(r"^focus\s+(?:on|or)\s+", "", cleaned)
        cleaned = re.sub(r"^active\s+closest\s+to\s+focus\s+(?:on|or)\s+", "", cleaned)
        cleaned = re.sub(r"^active\s+focus\s+(?:on|or)\s+", "", cleaned)
        cleaned = " ".join(cleaned.split())
        return cleaned

    for prefix in ACTIVE_FOCUS_UPDATE_PREFIXES:
        if normalized.startswith(prefix):
            focus_text = _cleanup_focus_text(normalized[len(prefix) :])
            if len(focus_text) >= 3:
                return focus_text

    from_now_on_match = re.match(r"^from now on\s*,?\s*focus on\s+(.+)$", normalized)
    if from_now_on_match:
        focus_text = _cleanup_focus_text(from_now_on_match.group(1))
        if len(focus_text) >= 3:
            return focus_text

    voice_variants = (
        r"^change\s+(?:your|my)?\s*active\s*focus\s*[\.:,]?\s*focus\s+(?:on|or)\s+(.+)$",
        r"^change\s+(?:your|my)?\s*active\s*closest\s*to\s*focus\s*[\.:,]?\s*focus\s+(?:on|or)\s+(.+)$",
        r"^change\s+(?:your|my)?\s*active\s*closest\s*to\s*focus\s*[\.:,]?\s+(.+)$",
        r"^change\s+(?:your|my)?\s*active\s*focus\s*[\.:,]?\s+(.+)$",
        r"^from\s+now\s+on\s*,?\s*(?:your\s+)?focus\s+is\s+(.+)$",
        r"^your\s+priority\s+is\s+(.+)$",
        r"^we\s+need\s+your\s+focus\s+to\s+be\s+(.+)$",
        r"^active\s+closest\s+to\s+focus\s+(?:on|or)\s+(.+)$",
    )
    for pattern in voice_variants:
        matched = re.match(pattern, normalized)
        if matched:
            focus_text = _cleanup_focus_text(matched.group(1))
            if len(focus_text) >= 3:
                return focus_text

    return None


def _is_active_focus_candidate(question: str) -> bool:
    normalized = _normalize_intent_text(question)
    if STATUS_QUESTION_PATTERN.match(normalized) or normalized.endswith("?"):
        return False
    return bool(
        re.search(
            r"\b(change\s+(?:your|my)?\s*active\s*focus|"
            r"change\s+(?:your|my)?\s*active\s*closest\s*to\s*focus|"
            r"set\s+(?:your|the)?\s*active\s*focus|"
            r"from\s+now\s+on\s+(?:your\s+)?focus\s+is|"
            r"your\s+priority\s+is|"
            r"we\s+need\s+your\s+focus\s+to\s+be|"
            r"active\s+closest\s+to\s+focus\s+(?:on|or)|"
            r"focus\s+(?:on|or)\s+)\b",
            normalized,
        )
    )


def _is_unclear_focus_instruction(focus_text: str) -> bool:
    cleaned = " ".join(focus_text.strip().split())
    if len(cleaned) < 10:
        return True

    tokens = [token for token in cleaned.split(" ") if token]
    if len(tokens) < 3:
        return True

    vague_only = {
        "this",
        "that",
        "it",
        "more",
        "better",
        "same",
        "normal",
    }
    return all(token in vague_only for token in tokens)


def _extract_after_prefixes(normalized: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip(" .!?")
    return normalized.strip(" .!?")


def _classify_speech_act(question: str) -> str:
    normalized = _normalize_intent_text(question)
    is_question = STATUS_QUESTION_PATTERN.match(normalized) or normalized.endswith("?")
    is_repo_build_task = (
        (
            "build this feature" in normalized
            or "code 9" in normalized
            or "code builder" in normalized
            or "code builder smoke test" in normalized
            or "add tests" in normalized
            or "add or update tests" in normalized
            or "run pytest" in normalized
            or "pytest" in normalized
            or "code builder smoke test" in normalized
            or "git commit" in normalized
            or "git push" in normalized
            or "implement patch" in normalized
        )
        and (
            "we are in" in normalized
            or "x:\\" in normalized
            or "pytest" in normalized
            or "git" in normalized
        )
    )

    if _extract_active_focus_instruction(question) is not None:
        return "active_focus_update"

    if is_repo_build_task:
        return "implementation_task"

    if any(normalized.startswith(prefix) for prefix in CORRECTION_PREFIXES):
        return "user_correction"

    if "you are not responsible for building yourself" in normalized:
        return "user_correction"

    if is_question and not any(
        marker in normalized
        for marker in (
            "when i ask about",
            "from now on",
            "i want you to",
            "remember i prefer",
            "check proof first",
            "do not guess",
            "don't guess",
        )
    ):
        return "status_question"

    if any(marker in normalized for marker in HALLUCINATION_GUARD_MARKERS):
        return "hallucination_guard"

    if any(marker in normalized for marker in ANSWER_STYLE_MARKERS):
        return "answer_style_preference"

    if any(marker in normalized for marker in DIAGNOSTIC_RULE_MARKERS):
        return "diagnostic_rule"

    if any(marker in normalized for marker in WORKFLOW_HABIT_MARKERS):
        return "workflow_habit_learning"

    if any(marker in normalized for marker in COMMUNICATION_PREFERENCE_MARKERS):
        return "communication_preference"

    if PROTECTED_MUTATION_PATTERN.search(normalized):
        return "protected_mutation_request"

    if is_question:
        return "status_question"

    if IMPLEMENTATION_TASK_PATTERN.search(normalized):
        return "implementation_task"

    return "normal_question"


def _build_task_guard_answer() -> str:
    return (
        "This is a build task. Xoduz cannot execute natural-language build tasks directly yet. "
        "Use VS Code/Copilot or provide a valid patch payload through /apply-patch. "
        "Repo mutations require Operator Mode with staged slash command confirmation. "
        "No files were changed. No tests were run. No commit or push occurred."
    )


def _is_build_follow_up_prompt(question: str) -> bool:
    normalized = _normalize_intent_text(question)
    return normalized in {
        "implement patch",
        "implemente patch",
        "do it",
        "finish it",
        "commit it",
        "push it",
        "run it",
        "make it happen",
    }


def _lacks_verified_operator_success(session_metadata: dict[str, Any]) -> bool:
    last = session_metadata.get("operator_last_action")
    if not isinstance(last, dict):
        return True

    status = str(last.get("status", "")).strip().lower()
    if status in {"failed", "denied", "not_implemented", "cancelled", "pending"}:
        return True
    if status != "success":
        return True

    data = last.get("data")
    if not isinstance(data, dict):
        return True
    return not bool(data)


def _extract_correction_text(question: str) -> str:
    normalized = _normalize_intent_text(question)
    return _extract_after_prefixes(normalized, CORRECTION_PREFIXES)


def _extract_preference_text(question: str) -> str:
    normalized = _normalize_intent_text(question)
    return normalized.strip(" .!?")


def _extract_workflow_habit_text(question: str) -> str:
    normalized = _normalize_intent_text(question)
    return normalized.strip(" .!?")


def _speech_act_to_learning_layer(speech_act: str) -> BrainLayer:
    if speech_act in {
        "workflow_habit_learning",
        "hallucination_guard",
        "diagnostic_rule",
    }:
        return BrainLayer.KNOWLEDGE
    return BrainLayer.MEMORY


def _speech_act_confidence(speech_act: str, text: str) -> float:
    normalized = _normalize_intent_text(text)
    if speech_act in {"hallucination_guard", "diagnostic_rule"}:
        return 0.9
    if speech_act == "workflow_habit_learning":
        return 0.84
    if speech_act == "answer_style_preference":
        return 0.88
    if speech_act == "communication_preference":
        return 0.86
    if speech_act == "user_correction":
        if "instead" in normalized or "not asking" in normalized:
            return 0.87
        return 0.7
    return 0.65


def _needs_learning_clarification(speech_act: str, text: str) -> bool:
    normalized = _normalize_intent_text(text)
    emotional_only = {
        "you screwed up",
        "no",
        "wrong",
        "bad",
    }
    if speech_act == "user_correction" and normalized in emotional_only:
        return True
    if len(normalized) < 24:
        return True
    if not any(
        token in normalized
        for token in (
            "when",
            "if",
            "instead",
            "prefer",
            "don't",
            "do not",
            "always",
            "before",
            "unless",
            "should",
        )
    ):
        return True
    return False


def _is_emotional_unclear_feedback(text: str) -> bool:
    normalized = _normalize_intent_text(text)
    if len(normalized.split()) > 8:
        return False
    return any(
        token in normalized
        for token in (
            "screwed up",
            "wrong",
            "bad",
            "not what i meant",
        )
    )


def _learning_protected_boundary(text: str) -> bool:
    return bool(LEARNING_PROTECTED_PATTERN.search(_normalize_intent_text(text)))


def _learning_rule_tags(speech_act: str, proof_required: bool) -> list[str]:
    tags = ["learning", speech_act.replace("_", "-")]
    if speech_act in {"answer_style_preference", "communication_preference"}:
        tags.append("communication")
    if speech_act in {"workflow_habit_learning", "diagnostic_rule"}:
        tags.append("workflow")
    if speech_act == "hallucination_guard":
        tags.append("proof-guard")
    if proof_required:
        tags.append("proof-required")
    return tags


def _learning_rule_title(speech_act: str, lesson_text: str) -> str:
    prefix = {
        "user_correction": "Correction",
        "communication_preference": "Communication Preference",
        "workflow_habit_learning": "Workflow Habit",
        "hallucination_guard": "Hallucination Guard",
        "answer_style_preference": "Answer Style",
        "diagnostic_rule": "Diagnostic Rule",
    }.get(speech_act, "Learned Rule")
    clipped = " ".join(lesson_text.split())
    if len(clipped) > 84:
        clipped = clipped[:81].rstrip() + "..."
    return f"{prefix}: {clipped}"


def _append_learning_signal(
    session_metadata: dict[str, Any], signal: dict[str, Any]
) -> None:
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


def _learning_context_receipt(
    *,
    learning_layer: BrainLayer,
    learned_record_id: str,
    proof_required: bool,
) -> dict[str, Any]:
    compact_parts = [
        f"Memory: {learned_record_id}"
        if learning_layer == BrainLayer.MEMORY
        else "Memory: -",
        f"Knowledge: {learned_record_id}"
        if learning_layer == BrainLayer.KNOWLEDGE
        else "Knowledge: -",
        "Focus: -",
        "Proof: required" if proof_required else "Proof: none",
    ]
    return {
        "compact": "; ".join(compact_parts),
        "context_receipts": [
            {
                "layer": learning_layer.value,
                "record_id": learned_record_id,
                "status": "active",
                "source": "direct_user_instruction",
            }
        ],
        "record_ids": [learned_record_id],
    }


def _active_learned_rules(records: list[BrainRecord]) -> list[BrainRecord]:
    out: list[BrainRecord] = []
    for record in records:
        if record.status != "active":
            continue
        tags = {str(tag).lower() for tag in record.tags}
        if "learned-rule" in tags or "otis-learning" in tags:
            out.append(record)
    return out


def _learned_rules_prompt(records: list[BrainRecord]) -> str:
    active = _active_learned_rules(records)
    if not active:
        return ""

    lines = [
        "--- LEARNED USER RULES (DURABLE) ---",
        "Apply these learned behavior rules unless they conflict with safety boundaries:",
    ]
    for record in active[:10]:
        lines.append(f"- {record.record_id}: {record.summary}")
    lines.append("-------------------------------------")
    return "\n".join(lines)


def _applies_learned_rule(
    question: str,
    records: list[BrainRecord],
) -> tuple[str | None, BrainRecord | None]:
    normalized = _normalize_intent_text(question)
    ci_or_github_status_prompt = bool(
        re.search(
            r"\b(github\s+actions?|ci\s+status|build\s+status|checks?\s+status|did\s+ci|is\s+ci)\b",
            normalized,
        )
    )

    # Never replace explicit operator-history/status introspection prompts.
    if re.search(
        r"\b(operator\s+actions?|what\s+did\s+you\s+just\s+check|last\s+operator\s+receipt)\b",
        normalized,
    ):
        return None, None

    for record in _active_learned_rules(records):
        tags = {str(tag).lower() for tag in record.tags}
        if (
            "proof-required" in tags or "proof-guard" in tags
        ) and ci_or_github_status_prompt:
            return (
                "Understood. Per your learned diagnostic rule, I will require proof before claiming CI/GitHub status. I do not have live proof in this turn.",
                record,
            )
    return None, None


def _focus_violates_protected_rules(focus_text: str) -> bool:
    return bool(ACTIVE_FOCUS_PROTECTED_PATTERN.search(focus_text))


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


def _session_focus_context_receipt(
    session_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return None

    focus_id = str(focus.get("id", "")).strip()
    focus_summary = str(focus.get("summary", "")).strip()
    source = (
        str(focus.get("source", "direct_user_instruction")).strip()
        or "direct_user_instruction"
    )
    persistence = (
        str(focus.get("persistence", "session-only")).strip() or "session-only"
    )
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
    merged: dict[str, Any] = dict(base_receipt or {})
    focus_receipt = _session_focus_context_receipt(session_metadata)
    if focus_receipt is None:
        return merged

    existing_contexts = list(merged.get("context_receipts", []))
    if not any(
        isinstance(item, dict) and str(item.get("layer", "")).lower() == "active_focus"
        for item in existing_contexts
    ):
        existing_contexts.extend(list(focus_receipt.get("context_receipts", [])))
    merged["context_receipts"] = existing_contexts

    existing_ids = list(merged.get("record_ids", []))
    for record_id in list(focus_receipt.get("record_ids", [])):
        if record_id not in existing_ids:
            existing_ids.append(record_id)
    merged["record_ids"] = existing_ids

    focus_compact = str(focus_receipt.get("compact", "")).strip()
    base_compact = str(merged.get("compact", "")).strip()
    if focus_compact and focus_compact not in base_compact:
        merged["compact"] = (
            f"{base_compact} | {focus_compact}" if base_compact else focus_compact
        )

    return merged


def _is_communication_workflow_focus(session_metadata: dict[str, Any]) -> bool:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return False
    summary = str(focus.get("summary", "")).lower()
    if not summary:
        return False
    return any(
        token in summary
        for token in (
            "communicat",
            "workflow",
            "habit",
            "otis",
            "operator",
        )
    )


def _is_focus_guided_follow_up(question: str) -> bool:
    normalized = _normalize_intent_text(question)
    patterns = (
        "next steps",
        "what now",
        "how do we improve this",
        "what should we pursue",
        "communicate better",
        "fluid communication",
        "increasing fluid communication",
    )
    return any(token in normalized for token in patterns)


def _is_local_scan_or_operator_prompt(question: str) -> bool:
    normalized = _normalize_intent_text(question)
    scan_tokens = (
        "local scan",
        "scan",
        "bridge",
        "hardware",
        "host visibility",
        "operator mode",
        "staging",
        "stage action",
        "cpu",
        "gpu",
        "disk",
        "ports",
        "container",
    )
    return any(token in normalized for token in scan_tokens)


def _active_focus_guided_plan_answer() -> str:
    return (
        "Next steps for better communication with Otis, under the current Active Focus:\n"
        "1. Track Otis corrections turn-by-turn and convert them into durable behavior updates.\n"
        "2. Save communication preferences (style, depth, tone, constraints) and apply them on every response.\n"
        "3. Learn workflow habits from repeated patterns and reflect them in execution order.\n"
        "4. Ask one clarifying question whenever an instruction is ambiguous before taking action.\n"
        "5. Use compact receipts to show what was applied, what source was used, and what changed.\n"
        "6. Verify persistence by checking behavior after new session, reload, and container restart.\n"
        "7. Reduce hallucinations by requiring explicit source/proof on repo and runtime status claims.\n\n"
        "Clarifying question (only if needed now): which lane should I tune first for you — correction handling, preference persistence, or workflow habit learning?"
    )


def _active_focus_guided_context_receipt(focus_id: str) -> dict[str, Any]:
    return {
        "compact": (
            f"Focus: {focus_id}; Memory: learning-signals; "
            "Knowledge: communication-workflow; Model: policy_only; "
            "Proof: active_focus_guided"
        ),
        "context_receipts": [
            {
                "layer": "active_focus",
                "record_id": focus_id,
                "FocusApplied": True,
                "Mode": "communication_workflow_learning",
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


@app.get("/runtime/brain/records")
async def runtime_brain_records(
    layer: BrainLayer | None = None,
    include_archived: bool = True,
    pending_only: bool = False,
    learned_only: bool = False,
    relevance: Literal[
        "current",
        "historical",
        "superseded",
        "expired",
        "needs_review",
    ]
    | None = None,
    history_only: bool = False,
    review_only: bool = False,
) -> dict[str, Any]:
    entries = brain_context_manager.loader.load_records_with_source()
    records: list[dict[str, Any]] = []

    for record, source, path in entries:
        if layer is not None and record.layer != layer:
            continue
        if pending_only and record.status not in {"pending", "pending_review"}:
            continue
        if not include_archived and record.status not in {
            "active",
            "pending",
            "pending_review",
        }:
            continue
        if learned_only:
            tags = {str(tag).lower() for tag in record.tags}
            if "learned-rule" not in tags and "otis-learning" not in tags:
                continue
        serialized = _serialize_brain_record(record=record, source=source, path=path)
        effective_relevance = serialized.get(
            "effective_relevance_state", record.relevance_state
        )
        stored_relevance = str(
            serialized.get("relevance_state", record.relevance_state)
        )
        status_label = serialized.get("status_label", _status_label(record.status))

        if relevance is not None and effective_relevance != relevance:
            continue
        if history_only and not (
            stored_relevance in {"historical", "superseded", "expired"}
            or effective_relevance in {"historical", "superseded", "expired"}
        ):
            continue
        if review_only and not (
            status_label == "pending"
            or stored_relevance == "needs_review"
            or effective_relevance == "needs_review"
            or bool(serialized.get("hygiene_recommendations"))
            or any(
                str(flag).lower()
                in {
                    "old_phase_reference",
                    "completed_milestone",
                    "mixed_historical_and_operational",
                    "mixed_historical_and_current",
                }
                for flag in (serialized.get("hygiene_flags") or [])
            )
        ):
            continue

        records.append(serialized)

    return {
        "count": len(records),
        "records": records,
    }


@app.put(
    "/runtime/brain/records/{record_id}",
    dependencies=[Depends(require_api_key)],
)
async def update_runtime_brain_record(
    record_id: str,
    payload: BrainRecordUpdateRequest,
) -> dict[str, Any]:
    found = brain_context_manager.loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")

    record, _, _ = found
    updates: dict[str, Any] = {}

    if payload.layer is not None:
        updates["layer"] = payload.layer
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.body is not None:
        cleaned_body = payload.body.strip()
        updates["body"] = cleaned_body
        updates["summary"] = _summary_from_body(cleaned_body)
    if payload.tags is not None:
        updates["tags"] = [
            tag
            for tag in {
                str(tag).strip()
                for tag in payload.tags
                if isinstance(tag, str) and tag.strip()
            }
        ]
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.relevance_state is not None:
        updates["relevance_state"] = payload.relevance_state
    if payload.superseded_by is not None:
        updates["superseded_by"] = payload.superseded_by.strip() or None
    if payload.valid_from is not None:
        updates["valid_from"] = payload.valid_from.strip() or None
    if payload.valid_until is not None:
        updates["valid_until"] = payload.valid_until.strip() or None
    if payload.applies_when is not None:
        updates["applies_when"] = payload.applies_when.strip() or None
    if payload.review_reason is not None:
        updates["review_reason"] = payload.review_reason.strip() or None
    if payload.last_reviewed_at is not None:
        updates["last_reviewed_at"] = payload.last_reviewed_at.strip() or None

    updated = record.model_copy(update=updates)
    brain_context_manager.loader.save_runtime_override(updated)
    refreshed = brain_context_manager.loader.get_record_with_source(record_id)
    if refreshed is None:
        raise RuntimeError(f"Updated record not found after save: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/deactivate",
    dependencies=[Depends(require_api_key)],
)
async def deactivate_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = brain_context_manager.loader.archive_record(record_id)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Deactivated record not found after save: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/set-active",
    dependencies=[Depends(require_api_key)],
)
async def set_active_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = brain_context_manager.loader.set_record_active(record_id)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Activated record not found after save: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/approve",
    dependencies=[Depends(require_api_key)],
)
async def approve_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = brain_context_manager.loader.approve_record(record_id)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Approved record not found after save: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/reject",
    dependencies=[Depends(require_api_key)],
)
async def reject_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = brain_context_manager.loader.reject_record(record_id)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Rejected record not found after save: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/mark-current",
    dependencies=[Depends(require_api_key)],
)
async def mark_current_runtime_brain_record(record_id: str) -> dict[str, Any]:
    found = brain_context_manager.loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found
    updated = record.model_copy(
        update={
            "status": "active",
            "relevance_state": "current",
            "superseded_by": None,
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    brain_context_manager.loader.save_runtime_override(updated)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Record not found after update: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/mark-historical",
    dependencies=[Depends(require_api_key)],
)
async def mark_historical_runtime_brain_record(record_id: str) -> dict[str, Any]:
    found = brain_context_manager.loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found
    updated = record.model_copy(
        update={
            "relevance_state": "historical",
            "review_reason": record.review_reason or "Marked historical by operator.",
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    brain_context_manager.loader.save_runtime_override(updated)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Record not found after update: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/mark-superseded",
    dependencies=[Depends(require_api_key)],
)
async def mark_superseded_runtime_brain_record(
    record_id: str,
    payload: BrainRecordRelevanceUpdateRequest,
) -> dict[str, Any]:
    if payload.relevance_state != "superseded":
        raise ValueError("mark-superseded requires relevance_state='superseded'.")

    found = brain_context_manager.loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found

    updated = record.model_copy(
        update={
            "relevance_state": "superseded",
            "status": "disabled",
            "superseded_by": payload.superseded_by,
            "review_reason": payload.review_reason or "Superseded by newer record.",
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    brain_context_manager.loader.save_runtime_override(updated)
    refreshed = brain_context_manager.loader.get_record_with_source(updated.record_id)
    if refreshed is None:
        raise RuntimeError(f"Record not found after update: {record_id}")
    saved_record, source, path = refreshed
    return _serialize_brain_record(record=saved_record, source=source, path=path)


@app.post(
    "/runtime/brain/records/{record_id}/apply-recommendation",
    dependencies=[Depends(require_api_key)],
)
async def apply_runtime_brain_record_recommendation(
    record_id: str,
    payload: BrainRecordApplyRecommendationRequest,
) -> dict[str, Any]:
    found = brain_context_manager.loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found

    if not payload.approve:
        return {
            "record_id": record_id,
            "applied": False,
            "recommendation_type": payload.recommendation_type,
            "status": "rejected",
        }

    if payload.recommendation_type == "mark_historical_via_runtime_override":
        updated = record.model_copy(
            update={
                "relevance_state": "historical",
                "review_reason": "Approved hygiene recommendation: historical.",
                "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        brain_context_manager.loader.save_runtime_override(updated)
        refreshed = brain_context_manager.loader.get_record_with_source(record_id)
        if refreshed is None:
            raise RuntimeError(f"Record not found after update: {record_id}")
        saved_record, source, path = refreshed
        return {
            "record": _serialize_brain_record(
                record=saved_record,
                source=source,
                path=path,
            ),
            "applied": True,
            "recommendation_type": payload.recommendation_type,
            "status": "applied",
        }

    if payload.recommendation_type == "split_record":
        historical, created = _split_record_to_current_operational(
            record=record,
            operational_title=payload.operational_title,
            operational_summary=payload.operational_summary,
            operational_body=payload.operational_body,
            tags=payload.tags,
            layer=payload.layer,
            review_reason="Approved hygiene recommendation: split applied.",
            applies_when=None,
            valid_from=None,
            valid_until=None,
        )
        historical_refreshed = brain_context_manager.loader.get_record_with_source(
            historical.record_id
        )
        created_refreshed = brain_context_manager.loader.get_record_with_source(
            created.record_id
        )
        if historical_refreshed is None or created_refreshed is None:
            raise RuntimeError(f"Split records not found after update: {record_id}")
        historical_record, historical_source, historical_path = historical_refreshed
        created_record, created_source, created_path = created_refreshed
        return {
            "record": _serialize_brain_record(
                record=historical_record,
                source=historical_source,
                path=historical_path,
            ),
            "created_record": _serialize_brain_record(
                record=created_record,
                source=created_source,
                path=created_path,
            ),
            "applied": True,
            "recommendation_type": payload.recommendation_type,
            "status": "applied",
        }

    raise ValueError(f"Unsupported recommendation type: {payload.recommendation_type}")


@app.post(
    "/runtime/brain/records/{record_id}/split",
    dependencies=[Depends(require_api_key)],
)
async def split_runtime_brain_record(
    record_id: str,
    payload: BrainRecordSplitRequest,
) -> dict[str, Any]:
    found = brain_context_manager.loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found

    historical, created = _split_record_to_current_operational(
        record=record,
        operational_title=payload.operational_title,
        operational_summary=payload.operational_summary,
        operational_body=payload.operational_body,
        tags=payload.tags,
        layer=payload.layer,
        review_reason=payload.review_reason,
        applies_when=payload.applies_when,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )

    historical_refreshed = brain_context_manager.loader.get_record_with_source(
        historical.record_id
    )
    created_refreshed = brain_context_manager.loader.get_record_with_source(
        created.record_id
    )
    if historical_refreshed is None or created_refreshed is None:
        raise RuntimeError(f"Split records not found after update: {record_id}")

    historical_record, historical_source, historical_path = historical_refreshed
    created_record, created_source, created_path = created_refreshed

    return {
        "applied": True,
        "source_record": _serialize_brain_record(
            record=historical_record,
            source=historical_source,
            path=historical_path,
        ),
        "created_record": _serialize_brain_record(
            record=created_record,
            source=created_source,
            path=created_path,
        ),
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
    session_state.metadata["operator_last_action"] = stage_result["result"].model_dump(
        mode="json"
    )
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
        should_clear = "typed confirmation did not match" not in err

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
        raise ValueError(
            "No matching pending operator action found for cancel request."
        )

    cancellation = operator_manager.cancel_pending_action(pending)
    operator_manager.clear_pending_action(session_state.metadata)

    structured_receipt = cancellation["result"].structured_receipt()
    history = append_history(session_state.metadata, structured_receipt)
    session_state.metadata["operator_last_action"] = cancellation["result"].model_dump(
        mode="json"
    )
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
    resolved_focus = _resolve_effective_active_focus(session_state.metadata)
    if isinstance(resolved_focus, dict):
        session_state.metadata["active_focus"] = resolved_focus
        inference_state.metadata["active_focus"] = resolved_focus
    intent_class = _classify_speech_act(payload.raw_text)

    current_history = get_history(session_state.metadata)
    action_history_refs = [
        str(item.get("action_id", ""))
        for item in current_history[-5:]
        if isinstance(item, dict) and str(item.get("action_id", ""))
    ]

    if intent_class in {
        "user_correction",
        "communication_preference",
        "workflow_habit_learning",
        "hallucination_guard",
        "answer_style_preference",
        "diagnostic_rule",
    }:
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
        proof_required = intent_class in {"hallucination_guard", "diagnostic_rule"}
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

    if intent_class == "implementation_task":
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
            context_receipt=_merge_focus_context_receipt({}, session_state.metadata),
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
        updated_state.metadata["operator_last_action"] = (
            operator_action.result.model_dump(mode="json")
        )
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

    if _is_build_follow_up_prompt(payload.raw_text) and _lacks_verified_operator_success(
        session_state.metadata
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

    brain_context = brain_context_manager.build_context_for_question(payload.raw_text)
    inference_state.messages.insert(
        0,
        ConversationMessage(role="system", content=brain_context.prompt),
    )
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
