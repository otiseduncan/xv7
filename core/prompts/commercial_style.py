"""Commercial-quality response baseline prompt for xv7.

This module is intentionally small and deterministic. It does not add a new
agent loop or second model call; it only supplies the baseline behavior contract
that the runtime model sees before ordinary chat inference.
"""

from __future__ import annotations

from typing import Any


_COMMERCIAL_RESPONSE_BASELINE = """
--- COMMERCIAL RESPONSE BASELINE ---
Identity: You are Xoduz, also called X, the XV7 assistant designed by Syfernetics.
Goal: respond with the quality and reliability expected from a commercial assistant.

Behavior rules:
- Answer the user's actual request first. Do not dodge into generic status text.
- Be concise but complete: give the useful answer, the key reason, and the next concrete action when helpful.
- For complex work, reason internally and present a brief plan, findings, decision, and result. Do not expose hidden chain-of-thought.
- Be honest about uncertainty, missing access, failed commands, or unverified claims.
- Use runtime clock/context when provided. Never invent a current date, test result, repo state, or tool result.
- Treat the user's corrections and preferences as working instructions unless they conflict with safety or protected mutation boundaries.
- Ask a clarifying question only when the answer would otherwise be materially wrong; otherwise make the best safe assumption and proceed.
- For code/repo tasks, prefer evidence: exact file, exact failure, exact test/command, exact patch/result.
- Keep tone direct, grounded, capable, and conversational. No filler apologies, no theatrical hype.
-------------------------------
""".strip()


def _compact_mapping(
    mapping: dict[str, Any] | None, *, max_items: int = 8
) -> list[str]:
    if not isinstance(mapping, dict):
        return []
    lines: list[str] = []
    for key, value in list(mapping.items())[:max_items]:
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text and value_text:
            lines.append(f"- {key_text}: {value_text[:500]}")
    return lines


def _compact_rules(rules: list[Any] | None, *, max_items: int = 8) -> list[str]:
    if not isinstance(rules, list):
        return []
    lines: list[str] = []
    for item in rules[:max_items]:
        text = str(item).strip()
        if text:
            lines.append(f"- {text[:500]}")
    return lines


def build_commercial_system_prompt(
    *,
    active_focus: str | None = None,
    learned_rules: list[Any] | None = None,
    session_facts: dict[str, Any] | None = None,
) -> str:
    """Build the runtime model's commercial-quality behavior contract.

    The prompt is deliberately separate from memory retrieval and protected
    operator policy. It shapes ordinary model answers without bypassing existing
    safety guards, answer contracts, artifact routing, or operator mode.
    """

    sections = [_COMMERCIAL_RESPONSE_BASELINE]

    focus = str(active_focus or "").strip()
    if focus:
        sections.append(
            "--- ACTIVE FOCUS ---\n"
            f"Current working focus: {focus[:1200]}\n"
            "Use it to prioritize the answer, but do not ignore the user's immediate request."
        )

    rule_lines = _compact_rules(learned_rules)
    if rule_lines:
        sections.append(
            "--- LEARNED USER RULES ---\n"
            + "\n".join(rule_lines)
            + "\nApply these unless they conflict with safety or the current explicit request."
        )

    fact_lines = _compact_mapping(session_facts)
    if fact_lines:
        sections.append(
            "--- SESSION FACTS ---\n"
            + "\n".join(fact_lines)
            + "\nUse only when relevant; do not let stale facts override the live user request."
        )

    return "\n\n".join(sections)
