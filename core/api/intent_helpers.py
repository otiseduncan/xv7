from __future__ import annotations

from typing import Any, Callable, Pattern


def classify_speech_act(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
    status_question_pattern: Pattern[str],
    correction_prefixes: tuple[str, ...],
    hallucination_guard_markers: tuple[str, ...],
    answer_style_markers: tuple[str, ...],
    diagnostic_rule_markers: tuple[str, ...],
    workflow_habit_markers: tuple[str, ...],
    communication_preference_markers: tuple[str, ...],
    protected_mutation_pattern: Pattern[str],
    implementation_task_pattern: Pattern[str],
    extract_active_focus_instruction: Callable[[str], str | None],
    is_protected_implementation_task: Callable[[str], bool],
) -> str:
    normalized = normalize_intent_text(question)
    is_question = status_question_pattern.match(normalized) or normalized.endswith("?")
    is_repo_build_task = (
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
    ) and (
        "we are in" in normalized
        or "x:\\" in normalized
        or "pytest" in normalized
        or "git" in normalized
    )

    if extract_active_focus_instruction(question) is not None:
        return "active_focus_update"

    if is_repo_build_task:
        return "implementation_task"

    if any(normalized.startswith(prefix) for prefix in correction_prefixes):
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

    if any(marker in normalized for marker in hallucination_guard_markers):
        return "hallucination_guard"

    if any(marker in normalized for marker in answer_style_markers):
        return "answer_style_preference"

    if any(marker in normalized for marker in diagnostic_rule_markers):
        return "diagnostic_rule"

    if any(marker in normalized for marker in workflow_habit_markers):
        return "workflow_habit_learning"

    if any(marker in normalized for marker in communication_preference_markers):
        return "communication_preference"

    if protected_mutation_pattern.search(normalized):
        return "protected_mutation_request"

    if is_question:
        return "status_question"

    if implementation_task_pattern.search(
        normalized
    ) and is_protected_implementation_task(normalized):
        return "implementation_task"

    return "normal_question"


def build_task_guard_answer() -> str:
    return (
        "This is a build task targeting a protected location or protected mutation boundary. "
        "Use Operator Mode for repo writes, writes outside the approved sandbox, destructive actions, commit/push, or other protected mutations. "
        "No files were changed. No tests were run. No commit or push occurred."
    )


def is_protected_implementation_task(normalized_question: str) -> bool:
    if not normalized_question:
        return False

    protected_markers = (
        " repo",
        " repository",
        " codebase",
        " workspace",
        " worktree",
        " file",
        " files",
        " folder",
        " directory",
        " x:\\",
        " git",
        " commit",
        " push",
        " branch",
        " pull request",
        " pr",
        " pytest",
        " npm",
        " test suite",
        " tests",
        " docker",
        " container",
        " sandbox",
        " implement patch",
        " apply patch",
    )
    padded = f" {normalized_question} "
    return any(marker in padded for marker in protected_markers)


def is_build_follow_up_prompt(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> bool:
    normalized = normalize_intent_text(question)
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


def active_focus_system_prompt(session_metadata: dict[str, Any]) -> str:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return ""

    label = str(focus.get("id", "FOCUS-USER")).strip() or "FOCUS-USER"
    summary = str(focus.get("summary", "")).strip()
    if not summary:
        return ""

    return (
        "--- ACTIVE FOCUS (DIRECT USER INSTRUCTION) ---\n"
        f"{label} â€” {summary}\n"
        "Treat this as the current working priority until the user changes it.\n"
        "Do not confuse roadmap phase with active user focus.\n"
        "----------------------------------------------\n"
    )


def is_focus_guided_follow_up(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> bool:
    normalized = normalize_intent_text(question)
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


def is_local_scan_or_operator_prompt(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> bool:
    normalized = normalize_intent_text(question)
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


def active_focus_guided_plan_answer() -> str:
    return (
        "Next steps for better communication with Otis, under the current Active Focus:\n"
        "1. Track Otis corrections turn-by-turn and convert them into durable behavior updates.\n"
        "2. Save communication preferences (style, depth, tone, constraints) and apply them on every response.\n"
        "3. Learn workflow habits from repeated patterns and reflect them in execution order.\n"
        "4. Ask one clarifying question whenever an instruction is ambiguous before taking action.\n"
        "5. Use compact receipts to show what was applied, what source was used, and what changed.\n"
        "6. Verify persistence by checking behavior after new session, reload, and container restart.\n"
        "7. Reduce hallucinations by requiring explicit source/proof on repo and runtime status claims.\n\n"
        "Clarifying question (only if needed now): which lane should I tune first for you â€” correction handling, preference persistence, or workflow habit learning?"
    )
