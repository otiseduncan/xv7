from __future__ import annotations

import re
from typing import Any, Callable

from core.brain.schema import BrainLayer, BrainRecord


def extract_after_prefixes(normalized: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip(" .!?")
    return normalized.strip(" .!?")


def extract_correction_text(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
    correction_prefixes: tuple[str, ...],
) -> str:
    normalized = normalize_intent_text(question)
    return extract_after_prefixes(normalized, correction_prefixes)


def extract_preference_text(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> str:
    normalized = normalize_intent_text(question)
    return normalized.strip(" .!?")


def extract_workflow_habit_text(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> str:
    normalized = normalize_intent_text(question)
    return normalized.strip(" .!?")


def speech_act_to_learning_layer(speech_act: str) -> BrainLayer:
    if speech_act in {
        "workflow_habit_learning",
        "hallucination_guard",
        "diagnostic_rule",
    }:
        return BrainLayer.KNOWLEDGE
    return BrainLayer.MEMORY


def speech_act_confidence(
    speech_act: str,
    text: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> float:
    normalized = normalize_intent_text(text)
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


def needs_learning_clarification(
    speech_act: str,
    text: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> bool:
    normalized = normalize_intent_text(text)
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
            "treat",
            "preview",
            "write",
            "export",
            "generate",
            "going forward",
        )
    ):
        return True
    return False


def is_emotional_unclear_feedback(
    text: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> bool:
    normalized = normalize_intent_text(text)
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


def learning_protected_boundary(
    text: str,
    *,
    normalize_intent_text: Callable[[str], str],
    learning_protected_pattern: re.Pattern[str],
) -> bool:
    return bool(learning_protected_pattern.search(normalize_intent_text(text)))


def learning_rule_tags(speech_act: str, proof_required: bool) -> list[str]:
    tags = ["learning", "learned-rule", speech_act.replace("_", "-")]
    if speech_act in {"answer_style_preference", "communication_preference"}:
        tags.append("communication")
    if speech_act in {"workflow_habit_learning", "diagnostic_rule"}:
        tags.append("workflow")
    if speech_act == "hallucination_guard":
        tags.append("proof-guard")
    if proof_required:
        tags.append("proof-required")
    return tags


def learning_rule_title(speech_act: str, lesson_text: str) -> str:
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


def append_learning_signal(
    session_metadata: dict[str, Any], signal: dict[str, Any]
) -> None:
    current = session_metadata.get("learning_signals")
    if not isinstance(current, list):
        current = []
    current.append(signal)
    session_metadata["learning_signals"] = current[-50:]


def active_learned_rules(records: list[BrainRecord]) -> list[BrainRecord]:
    out: list[BrainRecord] = []
    for record in records:
        if record.status != "active":
            continue
        tags = {str(tag).lower() for tag in record.tags}
        if "learned-rule" in tags or "otis-learning" in tags:
            out.append(record)
    return out


def learned_rules_prompt(records: list[BrainRecord]) -> str:
    active = active_learned_rules(records)
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


def applies_learned_rule(
    question: str,
    records: list[BrainRecord],
    *,
    normalize_intent_text: Callable[[str], str],
) -> tuple[str | None, BrainRecord | None]:
    normalized = normalize_intent_text(question)
    ci_or_github_status_prompt = bool(
        re.search(
            r"\b(github\s+actions?|ci\s+status|build\s+status|checks?\s+status|did\s+ci|is\s+ci)\b",
            normalized,
        )
    )

    if re.search(
        r"\b(operator\s+actions?|what\s+did\s+you\s+just\s+check|last\s+operator\s+receipt)\b",
        normalized,
    ):
        return None, None

    for record in active_learned_rules(records):
        tags = {str(tag).lower() for tag in record.tags}
        if (
            "proof-required" in tags or "proof-guard" in tags
        ) and ci_or_github_status_prompt:
            return (
                "Understood. Per your learned diagnostic rule, I will require proof before claiming CI/GitHub status. I do not have live proof in this turn.",
                record,
            )
    return None, None
