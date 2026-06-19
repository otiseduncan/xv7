from __future__ import annotations

import os
import html
import re
import difflib
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from core.brain.artifact_fidelity_manager import ArtifactFidelityManager
from core.brain.artifact_response_service import ArtifactResponseService
from core.brain.answer_decision_service import AnswerDecisionService
from core.brain.artifact_utils import (
    content_sha256,
    safe_slug,
    slugify_artifact_name,
    utc_now_iso,
)
from core.brain.code_artifact_builder import CodeArtifactBuilder
from core.brain.git_runner import run_git
from core.brain.intent_router import IntentRouter
from core.brain.repo_safety_policy import RepoSafetyPolicy
from core.brain.sandbox_writer import SandboxWriteManager
from core.brain.schema import BrainLayer, BrainRecord
from core.operator.slash_commands import get_tool_capability_summary
from core.runtime.model_registry import (
    configured_ollama_base_url_candidates,
    resolve_model_for_runtime_role,
)



AnswerContract = None

@classmethod
def _artifact_history(
    cls,
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    if not isinstance(session_messages, list):
        return history

    pending_user_prompt: str | None = None
    next_revision_number = 1
    active_artifact_id: str | None = None
    for message in session_messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).lower()
        if role == "user":
            content = str(
                message.get("content") or message.get("raw_text") or ""
            ).strip()
            if content:
                pending_user_prompt = content
            continue
        if role != "assistant":
            continue

        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            continue
        artifact = cls._extract_artifact_from_metadata(metadata)
        if artifact is None:
            continue

        policy_raw = metadata.get("policy_provenance")
        policy: dict[str, Any] = policy_raw if isinstance(policy_raw, dict) else {}
        artifact_id = str(
            artifact.get("artifact_id")
            or policy.get("artifact_id")
            or active_artifact_id
            or f"{cls._slugify_artifact_name(str(artifact.get('filename') or 'artifact'))}-artifact"
        ).strip()
        revision_number = (
            artifact.get("revision_number")
            or policy.get("revision_number")
            or next_revision_number
        )
        try:
            revision_number = int(revision_number)
        except (TypeError, ValueError):
            revision_number = next_revision_number
        next_revision_number = max(next_revision_number, revision_number + 1)
        active_artifact_id = artifact_id

        history.append(
            {
                "artifact": {
                    **artifact,
                    "artifact_id": artifact_id,
                    "revision_id": str(
                        artifact.get("revision_id")
                        or policy.get("revision_id")
                        or f"{artifact_id}:r{revision_number}"
                    ),
                    "revision_number": revision_number,
                    "source_prompt": str(
                        artifact.get("source_prompt") or pending_user_prompt or ""
                    ).strip(),
                    "generation_provenance": dict(policy),
                },
                "message_id": message.get("id") or message.get("message_id"),
                "created_at": message.get("created_at") or message.get("timestamp"),
                "visible_text": str(message.get("content") or "").strip(),
            }
        )
    return history

@staticmethod
def _extract_target_text(question: str, label: str) -> str | None:
    patterns = [
        rf"{label}\s+to\s+[\"'“”‘’]([^\"'“”‘’]{{1,160}})[\"'“”‘’]",
        rf"{label}\s+to\s+([^.;]{{1,160}})",
        rf"{label}\s+say\s+[\"'“”‘’]([^\"'“”‘’]{{1,160}})[\"'“”‘’]",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;\"'“”‘’")
            if value:
                return value
    return None

@classmethod
def _artifact_refinement_mode(cls, normalized_question: str) -> str | None:
    return IntentRouter.artifact_refinement_mode(normalized_question)
    return "full_revision"

@staticmethod
def _artifact_needs_context_message() -> str:
    return (
        "I do not have an active artifact to refine in this session yet. "
        "Generate or provide an artifact first, then I can revise, undo, or summarize changes to it."
    )

@staticmethod
def _extract_first_tag_text(content: str, tag: str) -> str | None:
    return ArtifactFidelityManager.extract_first_tag_text(content, tag)

@staticmethod
def _replace_first_tag_text(content: str, tag: str, replacement: str) -> str:
    return ArtifactFidelityManager.replace_first_tag_text(content, tag, replacement)

@staticmethod
def _current_capabilities_answer() -> str:
    summary = get_tool_capability_summary()
    read_only_tools = ", ".join(summary.get("implemented_read_only_tools", []))
    operator_tools = ", ".join(summary.get("implemented_operator_tools", []))
    stubbed_tools = ", ".join(
        [
            *summary.get("stubbed_read_only_tools", []),
            *summary.get("stubbed_operator_tools", []),
        ]
    )
    return (
        "Current capabilities (wired now): "
        f"Read-only tools ({len(summary.get('implemented_read_only_tools', []))}): {read_only_tools}. "
        f"Operator/mutation tools ({len(summary.get('implemented_operator_tools', []))}): {operator_tools}. "
        f"Roadmap/stubbed tools ({len(summary.get('stubbed_read_only_tools', [])) + len(summary.get('stubbed_operator_tools', []))}): {stubbed_tools}. "
        "Not wired yet: live internet browsing, email connectors, calendar scheduling, and VS Code control commands. "
        "Filesystem mutation is only available through implemented Operator Mode slash commands with confirmation."
    )

@staticmethod
def _replace_first_button_text(content: str, replacement: str) -> str:
    escaped = html.escape(replacement, quote=False)
    pattern = re.compile(
        r"(<a[^>]*class=\"button[^\"]*\"[^>]*>)(.*?)(</a>)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub(rf"\1{escaped}\3", content, count=1)

@classmethod
def _artifact_change_summary(
    cls,
    current_artifact: dict[str, Any],
    previous_artifact: dict[str, Any] | None,
) -> str:
    if previous_artifact is None:
        return (
            "I do not have an earlier artifact revision to compare in this session."
        )

    current_content = str(current_artifact.get("content") or "")
    previous_content = str(previous_artifact.get("content") or "")
    changes: list[str] = []

    previous_h1 = cls._extract_first_tag_text(previous_content, "h1")
    current_h1 = cls._extract_first_tag_text(current_content, "h1")
    if previous_h1 and current_h1 and previous_h1 != current_h1:
        changes.append(f'Main headline changed to "{current_h1}".')
    if (
        "Brush Script MT" in current_content
        and "Brush Script MT" not in previous_content
    ):
        changes.append("Typography was updated with a script-style font treatment.")
    if any(
        token in current_content.lower() for token in ("#d4af37", "gold")
    ) and not any(
        token in previous_content.lower() for token in ("#d4af37", "gold")
    ):
        changes.append("The palette shifted toward black-and-gold styling.")
    if (
        "premium" in current_content.lower()
        and "premium" not in previous_content.lower()
    ):
        changes.append("The copy and styling now carry a more premium tone.")
    if not changes:
        changes.append(
            "I updated the current artifact while keeping the same overall business identity and structure."
        )
    return " ".join(changes[:3])

@staticmethod
def _extract_requested_headline(question: str) -> str | None:
    return AnswerContract._extract_target_text(
        question, "headline"
    ) or AnswerContract._extract_target_text(question, "main headline")

@staticmethod
def _extract_requested_button_text(question: str) -> str | None:
    return AnswerContract._extract_target_text(
        question, "button text"
    ) or AnswerContract._extract_target_text(question, "cta")

@staticmethod
def _is_business_rename_request(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "rename the business",
            "rename the site",
            "change the business name",
            "change the site name",
        )
    )

@classmethod
def _validate_revision_candidate(
    cls,
    *,
    content: str,
    source_artifact: dict[str, Any],
    requested_question: str,
) -> tuple[bool, str]:
    business_name = ""
    if not cls._is_business_rename_request(requested_question):
        business_name = (
            cls._extract_business_name_from_html(
                str(source_artifact.get("content") or "")
            )
            or ""
        )
    valid, reason = cls._validate_artifact_content(
        content=content,
        language=str(source_artifact.get("language") or "html"),
        business_name=business_name,
        style_hints=cls._extract_style_hints(requested_question),
        requested_question=requested_question,
    )
    if (
        not valid
        and reason == "stale_business_leak_detected"
        and business_name
        and business_name.lower() in content.lower()
    ):
        return True, "passed"
    return valid, reason

@classmethod
def _build_refinement_constraints(
    cls, revision_mode: str, question: str
) -> list[str]:
    constraints: list[str] = []
    lowered = question.lower()
    if revision_mode == "style_only":
        constraints.append(
            "Preserve the existing content and structure as much as possible while changing styling."
        )
    elif revision_mode == "content_only":
        constraints.append(
            "Preserve layout and styling as much as possible while changing only the requested copy/content."
        )
    elif revision_mode == "targeted_revision":
        constraints.append(
            "Preserve everything outside the requested scope as much as possible."
        )
    if "keep the layout" in lowered:
        constraints.append("Keep the layout structure and section order intact.")
    if "keep the content" in lowered:
        constraints.append(
            "Keep the existing wording and section content intact unless the user explicitly asked to rewrite it."
        )
    if any(token in lowered for token in ("script", "cursive", "handwritten")):
        constraints.append(
            "Use a visible script-style font cue such as Brush Script MT, Segoe Script, or cursive in CSS."
        )
    if "easier to read" in lowered:
        constraints.append(
            "Increase readability with stronger contrast, roomier spacing, and slightly larger text sizing."
        )
    if any(
        token in lowered
        for token in ("black", "gold", "white", "purple", "green", "red", "silver")
    ):
        constraints.append(
            "Make the requested colors visibly present in CSS variables or style declarations."
        )
    return constraints

@classmethod
def _typography_style_request(cls, normalized_question: str) -> str | None:
    if cls.TYPOGRAPHY_BLACKLETTER_PATTERN.search(normalized_question):
        return "blackletter/gothic"
    if (
        "gothic" in normalized_question
        and cls.TYPOGRAPHY_BLACKLETTER_DETAIL_PATTERN.search(normalized_question)
    ):
        return "blackletter/gothic"
    if cls.TYPOGRAPHY_SCRIPT_PATTERN.search(normalized_question):
        return "script/cursive"
    return None

@staticmethod
def _add_class_to_tag_openings(
    content: str, tag: str, class_name: str, *, first_only: bool = False
) -> str:
    pattern = re.compile(rf"<{tag}([^>]*)>", flags=re.IGNORECASE)

    def _repl(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        class_match = re.search(
            r"class\s*=\s*([\"'])(.*?)\1", attrs, flags=re.IGNORECASE | re.DOTALL
        )
        if class_match:
            quote = class_match.group(1)
            class_value = class_match.group(2)
            classes = [
                token for token in re.split(r"\s+", class_value.strip()) if token
            ]
            if class_name not in classes:
                classes.append(class_name)
            new_attr = f"class={quote}{' '.join(classes)}{quote}"
            attrs = (
                attrs[: class_match.start()] + new_attr + attrs[class_match.end() :]
            )
        else:
            attrs = f'{attrs} class="{class_name}"'
        return f"<{tag}{attrs}>"

    return pattern.sub(_repl, content, count=1 if first_only else 0)

@classmethod
def _add_class_to_eyebrow_labels(cls, content: str, class_name: str) -> str:
    pattern = re.compile(
        r"<(div|span)([^>]*)>",
        flags=re.IGNORECASE,
    )

    def _repl(match: re.Match[str]) -> str:
        tag = match.group(1)
        attrs = match.group(2) or ""
        class_match = re.search(
            r"class\s*=\s*([\"'])(.*?)\1", attrs, flags=re.IGNORECASE | re.DOTALL
        )
        if not class_match:
            return match.group(0)
        class_value = class_match.group(2)
        classes = [
            token for token in re.split(r"\s+", class_value.strip()) if token
        ]
        if "eyebrow" not in classes:
            return match.group(0)
        if class_name not in classes:
            classes.append(class_name)
        quote = class_match.group(1)
        new_attr = f"class={quote}{' '.join(classes)}{quote}"
        attrs = attrs[: class_match.start()] + new_attr + attrs[class_match.end() :]
        return f"<{tag}{attrs}>"

    return pattern.sub(_repl, content)

@classmethod
def _deterministic_typography_refinement_content(
    cls,
    *,
    source_artifact: dict[str, Any],
    requested_style: str,
) -> tuple[str, dict[str, Any], bool, str]:
    source_content = str(source_artifact.get("content") or "")
    language = str(source_artifact.get("language") or "html").lower()
    if not source_content.strip() or language != "html":
        return (
            source_content,
            {
                "requested_style": requested_style,
                "applied_to": [],
                "deterministic_fallback_used": True,
                "status": "failed",
            },
            False,
            "unsupported_typography_refinement_target",
        )

    if requested_style == "blackletter/gothic":
        class_name = "blackletter-heading"
        style_block = (
            '<style id="xv7-typography-refinement">'
            ".blackletter-heading,"
            "h1.blackletter-heading,"
            "h2.blackletter-heading,"
            ".section-title.blackletter-heading {"
            'font-family: "Old English Text MT", "UnifrakturCook", "UnifrakturMaguntia", "Cloister Black", "Lucida Blackletter", fantasy, Georgia, serif;'
            "font-weight: 900;"
            "letter-spacing: 0.045em;"
            "text-shadow: 0 2px 0 rgba(0,0,0,0.45), 0 0 18px rgba(255,255,255,0.18);"
            "-webkit-text-stroke: 0.35px rgba(0,0,0,0.45);"
            "text-transform: none;"
            "line-height: 1.05;"
            "}"
            "h2.blackletter-heading {"
            "display: inline-block;"
            "padding-bottom: 0.24rem;"
            "border-bottom: 2px solid color-mix(in srgb, currentColor 60%, transparent);"
            "margin-bottom: 0.7rem;"
            "}"
            ".eyebrow.blackletter-heading {"
            "font-size: 0.86rem;"
            "letter-spacing: 0.09em;"
            "text-shadow: 0 1px 0 rgba(0,0,0,0.5), 0 0 10px rgba(255,255,255,0.22);"
            "}"
            "</style>"
        )
    else:
        class_name = "script-heading"
        style_block = (
            '<style id="xv7-typography-refinement">'
            ".script-heading {"
            'font-family: "Brush Script MT", "Segoe Script", "Lucida Handwriting", cursive;'
            "font-weight: 700;"
            "letter-spacing: 0.02em;"
            "text-shadow: 0 1px 0 rgba(0,0,0,0.32), 0 0 10px rgba(255,255,255,0.14);"
            "line-height: 1.1;"
            "}"
            "h2.script-heading {"
            "display: inline-block;"
            "padding-bottom: 0.2rem;"
            "border-bottom: 1px solid color-mix(in srgb, currentColor 52%, transparent);"
            "}"
            ".eyebrow.script-heading {"
            "font-weight: 700;"
            "letter-spacing: 0.08em;"
            "}"
            "</style>"
        )

    revised = source_content
    revised = re.sub(
        r"<style\s+id=[\"']xv7-typography-refinement[\"'][^>]*>.*?</style>",
        "",
        revised,
        flags=re.IGNORECASE | re.DOTALL,
    )
    revised = cls._insert_before_tag(revised, "head", style_block)
    revised = cls._add_class_to_tag_openings(
        revised, "h1", class_name, first_only=True
    )
    revised = cls._add_class_to_tag_openings(revised, "h2", class_name)
    revised = cls._add_class_to_tag_openings(revised, "h3", class_name)
    revised = cls._add_class_to_tag_openings(revised, "h4", class_name)
    revised = cls._add_class_to_eyebrow_labels(revised, class_name)

    metadata = {
        "requested_style": requested_style,
        "applied_to": ["main_heading", "section_titles", "display_labels"],
        "deterministic_fallback_used": True,
        "status": "passed",
    }
    return revised, metadata, True, "passed"

@classmethod
def _build_local_artifact_revision_prompt(
    cls,
    *,
    edit_instruction: str,
    source_artifact: dict[str, Any],
    revision_mode: str = "full_revision",
    strict_retry: bool,
    retry_requirements: list[str] | None = None,
) -> str:
    retry_requirements = retry_requirements or []
    filename = str(source_artifact.get("filename") or "index.html")
    language = str(source_artifact.get("language") or "html")
    existing_content = str(source_artifact.get("content") or "")

    retry_line = "Output only revised source code."
    if strict_retry:
        retry_line = "This is a retry because the first revision failed validation. Missing requirements: satisfy all hard constraints."
        if retry_requirements:
            retry_line += (
                " Missing requirements: " + "; ".join(retry_requirements) + "."
            )

    constraints = cls._build_refinement_constraints(revision_mode, edit_instruction)
    extra_constraints = "\n".join(f"- {item}" for item in constraints)

    return (
        f"Revise an existing {language} code artifact for filename {filename}.\n"
        f"User edit instruction: {edit_instruction.strip()}\n"
        f"Revision mode: {revision_mode}\n"
        "Hard constraints:\n"
        "- Return ONLY the full replacement source code content.\n"
        "- No markdown fences and no explanation.\n"
        "- Keep same filename/language/previewability metadata externally; only revise content.\n"
        "- No file writes, no repo mutation, no apply behavior.\n"
        "- No remote assets, no remote URLs, no external scripts, no external fonts/images.\n"
        "- Preserve the business identity and avoid unrelated business leakage.\n"
        f"{extra_constraints}\n"
        f"{retry_line}\n"
        "Current artifact source to revise:\n"
        "<<<ARTIFACT_START>>>\n"
        f"{existing_content}\n"
        "<<<ARTIFACT_END>>>\n"
    )

@staticmethod
def _html_text_diff_summary(previous_content: str, current_content: str) -> str:
    previous_headline = (
        AnswerContract._extract_business_name_from_html(previous_content)
        or "the previous artifact"
    )
    current_headline = (
        AnswerContract._extract_business_name_from_html(current_content)
        or previous_headline
    )
    changes: list[str] = []

    if previous_headline != current_headline:
        changes.append(
            f'The primary title changed from "{previous_headline}" to "{current_headline}".'
        )
    if previous_content != current_content:
        if (
            "Brush Script MT" in current_content
            and "Brush Script MT" not in previous_content
        ):
            changes.append(
                "Typography was updated with a script-style font treatment."
            )
        if any(
            token in current_content.lower() for token in ("#d4af37", "gold")
        ) and not any(
            token in previous_content.lower() for token in ("#d4af37", "gold")
        ):
            changes.append(
                "The palette was shifted toward black-and-gold premium styling."
            )
        if any(
            token in current_content.lower() for token in ("premium", "luxury")
        ) and not any(
            token in previous_content.lower() for token in ("premium", "luxury")
        ):
            changes.append("The copy added a more premium tone.")
    if not changes:
        changes.append(
            "The current artifact matches the previous saved revision closely, with no major visible differences detected."
        )
    return " ".join(changes)

@staticmethod
def _strip_markdown_fences(content: str) -> str:
    return ArtifactFidelityManager.strip_markdown_fences(content)

@staticmethod
def _insert_before_tag(content: str, closing_tag: str, snippet: str) -> str:
    return ArtifactFidelityManager.insert_before_tag(content, closing_tag, snippet)
    return content + snippet

@classmethod
def _deterministic_revision_fallback_content(
    cls,
    *,
    question: str,
    source_artifact: dict[str, Any],
    revision_mode: str,
) -> str:
    source_content = str(source_artifact.get("content") or "")
    language = str(source_artifact.get("language") or "html").lower()
    if not source_content.strip() or language != "html":
        return source_content

    normalized = question.lower()
    style_lines: list[str] = []
    revised = source_content
    requested_colors = [
        str(color).strip().lower()
        for color in cls._extract_style_hints(question).get("colors", [])
        if str(color).strip()
    ]

    requested_headline = cls._extract_requested_headline(question)
    if requested_headline:
        revised = cls._replace_first_tag_text(revised, "h1", requested_headline)

    requested_button_text = cls._extract_requested_button_text(question)
    if requested_button_text:
        revised = cls._replace_first_button_text(revised, requested_button_text)

    if any(token in normalized for token in ("script", "cursive", "handwritten")):
        style_lines.append(
            "h1, .hero-title { font-family: 'Brush Script MT', cursive; }"
        )
    if requested_colors:
        palette = cls._color_hex_map()
        primary = requested_colors[0]
        secondary = (
            requested_colors[1]
            if len(requested_colors) > 1
            else requested_colors[0]
        )
        tertiary = (
            requested_colors[2]
            if len(requested_colors) > 2
            else requested_colors[-1]
        )
        primary_hex = palette.get(primary, ["#2563eb"])[0]
        secondary_hex = palette.get(secondary, ["#22c55e"])[0]
        tertiary_hex = palette.get(tertiary, ["#f3f4f6"])[0]
        text_hex = (
            "#f5f5f5"
            if primary in {"black", "purple", "blue", "red"}
            else "#111827"
        )
        style_lines.append(
            ":root { "
            f"--xv7-primary: {primary_hex}; "
            f"--xv7-secondary: {secondary_hex}; "
            f"--xv7-tertiary: {tertiary_hex}; "
            f"--bg: {primary_hex}; "
            "--panel: rgba(18, 18, 18, 0.82); "
            f"--text: {text_hex}; "
            "--muted: color-mix(in srgb, var(--text) 72%, #9ca3af); "
            "--accent: var(--xv7-secondary); "
            "--accent-2: var(--xv7-tertiary); "
            "}"
        )
        style_lines.append(
            "body { background: linear-gradient(135deg, var(--xv7-primary), var(--xv7-secondary)); color: var(--text); }"
        )
        style_lines.append(
            ".button, .cta, .accent, .panel, .hero { border-color: var(--xv7-secondary); }"
        )
        style_lines.append(
            f".xv7-palette-note::before {{ content: 'Palette: {' '.join(requested_colors)}'; display: block; color: var(--text); }}"
        )
    elif "white" in normalized:
        style_lines.append(
            ":root { --bg: #ffffff; --panel: rgba(255, 255, 255, 0.98); --text: #111827; --muted: #4b5563; }"
        )
    if "easier to read" in normalized:
        style_lines.append(
            "body { line-height: 1.75; } .lead, .muted { font-size: 1.05rem; } h1 { letter-spacing: -0.02em; } .card { box-shadow: 0 20px 36px rgba(0, 0, 0, 0.16); }"
        )
    if any(token in normalized for token in ("premium", "luxury")):
        style_lines.append(
            ".card { box-shadow: 0 36px 90px rgba(0, 0, 0, 0.42); } .eyebrow { letter-spacing: 0.12em; }"
        )

    if style_lines:
        style_block = (
            '<style id="xv7-fallback-revision">'
            + " ".join(style_lines)
            + "</style>"
        )
        revised = cls._insert_before_tag(revised, "head", style_block)

    if "premium" in normalized and "premium" not in revised.lower():
        business_name = (
            cls._extract_business_name_from_html(revised) or "this business"
        )
        premium_note = f'<p class="xv7-premium">Premium presentation for {html.escape(business_name, quote=False)} with elevated styling and clearer polish.</p>'
        revised = cls._insert_before_tag(revised, "body", premium_note)

    if (
        revision_mode == "content_only"
        and requested_headline
        and requested_headline not in revised
    ):
        revised = cls._replace_first_tag_text(revised, "h1", requested_headline)

    return revised

def install_answer_contract_part_03(contract_cls):
    global AnswerContract
    AnswerContract = contract_cls
    setattr(contract_cls, "_artifact_history", _artifact_history)
    setattr(contract_cls, "_extract_target_text", _extract_target_text)
    setattr(contract_cls, "_artifact_refinement_mode", _artifact_refinement_mode)
    setattr(contract_cls, "_artifact_needs_context_message", _artifact_needs_context_message)
    setattr(contract_cls, "_extract_first_tag_text", _extract_first_tag_text)
    setattr(contract_cls, "_replace_first_tag_text", _replace_first_tag_text)
    setattr(contract_cls, "_current_capabilities_answer", _current_capabilities_answer)
    setattr(contract_cls, "_replace_first_button_text", _replace_first_button_text)
    setattr(contract_cls, "_artifact_change_summary", _artifact_change_summary)
    setattr(contract_cls, "_extract_requested_headline", _extract_requested_headline)
    setattr(contract_cls, "_extract_requested_button_text", _extract_requested_button_text)
    setattr(contract_cls, "_is_business_rename_request", _is_business_rename_request)
    setattr(contract_cls, "_validate_revision_candidate", _validate_revision_candidate)
    setattr(contract_cls, "_build_refinement_constraints", _build_refinement_constraints)
    setattr(contract_cls, "_typography_style_request", _typography_style_request)
    setattr(contract_cls, "_add_class_to_tag_openings", _add_class_to_tag_openings)
    setattr(contract_cls, "_add_class_to_eyebrow_labels", _add_class_to_eyebrow_labels)
    setattr(contract_cls, "_deterministic_typography_refinement_content", _deterministic_typography_refinement_content)
    setattr(contract_cls, "_build_local_artifact_revision_prompt", _build_local_artifact_revision_prompt)
    setattr(contract_cls, "_html_text_diff_summary", _html_text_diff_summary)
    setattr(contract_cls, "_strip_markdown_fences", _strip_markdown_fences)
    setattr(contract_cls, "_insert_before_tag", _insert_before_tag)
    setattr(contract_cls, "_deterministic_revision_fallback_content", _deterministic_revision_fallback_content)
