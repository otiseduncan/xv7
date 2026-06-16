from __future__ import annotations

import re
from typing import Callable, Pattern


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
    "update your active focus: ",
    "update your active focus to ",
    "update active focus: ",
    "update active focus to ",
    "set your focus to ",
    "set active focus to ",
    "set the active focus to ",
    "change your focus to ",
    "change my focus to ",
    "make your focus ",
    "make the active focus ",
    "your active focus is ",
    "our focus right now is ",
    "from now on your focus is ",
    "your priority is ",
    "we need your focus to be ",
)

ACTIVE_FOCUS_PROTECTED_PATTERN = re.compile(
    r"\b("
    r"delete|remove|destroy|format|wipe|erase|"
    r"bypass safety|disable safety|ignore safety|"
    r"exfiltrate|steal|credential theft|malware|ransomware|"
    r"without confirmation|without approval|without receipts"
    r")\b",
    flags=re.IGNORECASE,
)


def _cleanup_focus_text(raw_text: str) -> str:
    cleaned = raw_text.strip(" .!?,:")
    cleaned = re.sub(r"^focus\s+(?:on|or)\s+", "", cleaned)
    cleaned = re.sub(r"^active\s+closest\s+to\s+focus\s+(?:on|or)\s+", "", cleaned)
    cleaned = re.sub(r"^active\s+focus\s+(?:on|or)\s+", "", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned


def extract_active_focus_instruction(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
    prefixes: tuple[str, ...] = ACTIVE_FOCUS_UPDATE_PREFIXES,
) -> str | None:
    stripped = question.strip()
    normalized = normalize_intent_text(stripped)

    if normalized.startswith("please "):
        normalized = normalized[len("please ") :]

    for prefix in prefixes:
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
        r"^make\s+the\s+active\s+focus\s+(.+)$",
        r"^our\s+focus\s+right\s+now\s+is\s+(.+)$",
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


def is_active_focus_candidate(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
    is_status_question: Callable[[str], bool],
) -> bool:
    normalized = normalize_intent_text(question)
    if is_status_question(normalized) or normalized.endswith("?"):
        return False
    return bool(
        re.search(
            r"\b(change\s+(?:your|my)?\s*active\s*focus|"
            r"change\s+(?:your|my)?\s*active\s*closest\s*to\s*focus|"
            r"set\s+(?:your|the)?\s*active\s*focus|"
            r"update\s+(?:your|the)?\s*active\s*focus|"
            r"make\s+the\s+active\s+focus|"
            r"our\s+focus\s+right\s+now\s+is|"
            r"from\s+now\s+on\s+(?:your\s+)?focus\s+is|"
            r"your\s+priority\s+is|"
            r"we\s+need\s+your\s+focus\s+to\s+be|"
            r"active\s+closest\s+to\s+focus\s+(?:on|or)|"
            r"focus\s+(?:on|or)\s+)\b",
            normalized,
        )
    )


def is_unclear_focus_instruction(focus_text: str) -> bool:
    cleaned = " ".join(focus_text.strip().split())
    if len(cleaned) < 10:
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
    tokens = [token for token in cleaned.split(" ") if token]
    return all(token in vague_only for token in tokens)


def focus_violates_protected_rules(
    focus_text: str,
    *,
    protected_pattern: Pattern[str] = ACTIVE_FOCUS_PROTECTED_PATTERN,
) -> bool:
    return bool(protected_pattern.search(focus_text))


def is_focus_status_question(question: str) -> bool:
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
