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


class AnswerContract:
    """Conversation quality guardrails for proof-aware record-grounded answers."""

    ROADMAP_NOT_WIRED = "That module is not wired yet and remains on the XV7 roadmap."

    CODE_ARTIFACT_PATTERN = re.compile(
        r"\b(generate|create|build|draft|write|return|make)\b"
    )
    CODE_ARTIFACT_HINT_PATTERN = re.compile(
        r"\b(code artifact|filename|previewable|do not apply it to the repo|do not apply to the repo|"
        r"one-page website|landing page|html|css|javascript|typescript|python)\b"
    )
    EXPLICIT_ARTIFACT_INTENT_PATTERN = re.compile(
        r"\b(html artifact|code artifact|draft html|inline html|single-file html|single file html|"
        r"one-page html artifact|one page html artifact|generate html artifact|create html artifact|artifact)\b"
    )
    ARTIFACT_REPO_MUTATION_PATTERN = re.compile(
        r"\b(build me a website|create a website in the repo|make the app|implement this feature|"
        r"change the project files|write this into the repo|write this to the repo|"
        r"in the repo and commit it|commit it|git commit|git push|push it)\b"
    )

    REMINDER_PATTERN = re.compile(
        r"\b(remind me|set (?:me )?(?:a )?reminder|create (?:a )?reminder|add (?:it )?to (?:my )?calendar|schedule (?:it|this|that))\b"
    )
    HARDWARE_SCAN_PATTERN = re.compile(
        r"\b(cpu|gpu|processor|graphics|vram|disk|disks|disc|discs|drive|drives|ports?|processes|services|docker|container|vscode|vs code|hardware|system scan|host scan|system info|temperature sensor|thermal|fan|hardware temp|system temperature)\b"
    )
    SMS_PATTERN = re.compile(
        r"\b(send a text|send text|send this as a text message|text my|text someone|message someone|message\s+[a-z0-9]+|sms this to|sms)\b"
    )
    ARTIFACT_EDIT_ACTION_PATTERN = re.compile(
        r"\b(change|make|update|revise|edit|adjust|tweak|restyle|refresh|rewrite|switch|set|use|improve|redesign|move|keep|preserve|undo|revert|show|summarize)\b"
    )
    ARTIFACT_EDIT_TARGET_PATTERN = re.compile(
        r"\b(website|site|artifact|page|font|text|headline|button|buttons|copy|wording|color|colors|palette|theme|style|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|preview|code|hero|cta|section|layout|spacing|background|read|smaller|bigger|glass|glassmorphism|frosted|translucent|transparent|backdrop|blur|glow|glowing|shadow|card|cards|roomy|cherry|spread)\b"
    )
    SMS_EXPLICIT_SEND_PATTERN = re.compile(
        r"\b(send a text|send text|send this as a text message|text my|message\s+[a-z0-9]+|sms this)\b"
    )
    ARTIFACT_UNDO_PATTERN = re.compile(
        r"\b(undo the last change|undo|revert that|go back|restore previous)\b"
    )
    ARTIFACT_EXPLAIN_PATTERN = re.compile(
        r"\b(what changed|show me what changed|summarize the changes|summarise the changes|explain the changes)\b"
    )
    ARTIFACT_STYLE_PATTERN = re.compile(
        r"\b(color|colors|palette|background|font|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|easier to read|black|gold|white|glass|glassmorphism|frosted|translucent|transparent|backdrop|blur|glow|glowing|shadow|card|roomy|cherry|spread)\b"
    )
    ARTIFACT_CONTENT_PATTERN = re.compile(
        r"\b(headline|cta|button text|buttons|copy|wording|services section|main headline|rewrite|say)\b"
    )
    ARTIFACT_TARGETED_PATTERN = re.compile(
        r"\b(only|keep the layout|keep the content|preserve)\b"
    )
    ARTIFACT_PATCH_PROPOSAL_PATTERN = re.compile(
        r"\b(generate(?:\s+a)?\s+patch|create\s+a\s+patch\s+from\s+the\s+artifact|turn\s+this\s+into\s+a\s+patch|"
        r"create\s+patch\s+proposals?|create\s+patch\s+proposal\s+for\s+all\s+files|"
        r"make\s+a\s+patch\s+for\s+this\s+website|prepare\s+this\s+for\s+vs\s*code|save\s+this\s+as\s+a\s+patch|"
        r"show\s+me\s+the\s+diff|where\s+would\s+this\s+file\s+go)\b"
    )
    ARTIFACT_PATCH_APPLY_PATTERN = re.compile(
        r"\b(apply\s+this\s+patch|apply\s+the\s+patch|approve\s+patch|confirm\s+apply|write\s+the\s+proposed\s+patch|"
        r"save\s+the\s+patch\s+to\s+the\s+repo|apply\s+patch|"
        r"write/export/save\s+it\s+to\s+the\s+sandbox|"
        r"write\s+this\s+to\s+the\s+sandbox|write\s+this\s+to\s+sandbox|"
        r"save\s+this\s+to\s+the\s+sandbox|save\s+this\s+to\s+sandbox|"
        r"export\s+this\s+to\s+the\s+sandbox|export\s+this\s+to\s+sandbox)\b"
    )
    ARTIFACT_POST_APPLY_VERIFY_PATTERN = re.compile(
        r"\b(verify it|verify the file|check the applied file|make sure it wrote correctly|did it save|"
        r"did the file get created|confirm the file exists|check the file on disk|validate the applied patch)\b"
    )
    ARTIFACT_POST_APPLY_PREVIEW_PATTERN = re.compile(
        r"\b(preview it|open preview|show me the preview|how do i view it|open the generated site|where can i see it)\b"
    )
    ARTIFACT_POST_APPLY_TARGETED_VALIDATION_PATTERN = re.compile(
        r"\b(run validation|validate it|run safe checks|run html validation|check the generated site|run targeted tests)\b"
    )
    ARTIFACT_POST_APPLY_FULL_TEST_GUARD_PATTERN = re.compile(
        r"\b(run full tests|run pytest|run npm test|run full validation|run the full validation suite)\b"
    )
    TYPOGRAPHY_BLACKLETTER_PATTERN = re.compile(
        r"\b(old english font|blackletter|gothic font|fraktur|medieval font|biker-bar style font|biker bar style font)\b"
    )
    TYPOGRAPHY_BLACKLETTER_DETAIL_PATTERN = re.compile(
        r"\b(major section titles|heavier strokes|shadowing|letter spacing|decorative styling|gothic biker-bar style font|gothic biker bar style font)\b"
    )
    TYPOGRAPHY_SCRIPT_PATTERN = re.compile(
        r"\b(script font|cursive font|change the font|change the text font|change the heading font|change the font to a script)\b"
    )
    COLOR_CHANGE_REQUEST_PATTERN = re.compile(
        r"\b(color|colors|palette|background|theme)\b"
    )
    COMMIT_PROPOSAL_PATTERN = re.compile(
        r"\b(prepare (?:a )?commit|propose (?:a )?commit|commit proposal|create commit proposal|"
        r"draft commit|show commit proposal|summarize changes for commit|summarise changes for commit|"
        r"what would the commit be|what should i commit|prepare this commit|stage this for commit)\b"
    )
    COMMIT_APPROVAL_PATTERN = re.compile(
        r"\b(commit it|commit the proposal|approve commit|confirm commit|make the commit|"
        r"create the commit|go ahead and commit|commit these changes)\b"
    )
    EMAIL_SEND_PATTERN = re.compile(
        r"\b(send|compose|write).{0,40}\bemail\b|\bsend email\b"
    )
    EMAIL_PATTERN = re.compile(r"\b(email|inbox|mail)\b")
    WEATHER_PATTERN = re.compile(
        r"\b(weather|forecast|temperature|rain|snow|humidity)\b"
    )
    BIRTHDAY_PATTERN = re.compile(r"\b(birthday|birth day|bday)\b")
    CONTACT_PATTERN = re.compile(r"\b(contact|call|phone number|reach out)\b")
    FAMILY_PATTERN = re.compile(
        r"\b(family|mom|mother|dad|father|sister|brother|spouse|partner|child|children)\b"
    )
    MEDICAL_PATTERN = re.compile(
        r"\b(medical|health|history|condition|diagnosis|medication)\b"
    )
    WEB_LOOKUP_PATTERN = re.compile(
        r"\b(look up|lookup|search|find|browse|official website|website)\b"
    )
    CALENDAR_PATTERN = re.compile(r"\b(calendar|schedule|meeting|appointment|event)\b")
    APPOINTMENT_PATTERN = re.compile(
        r"\b(appointment|meeting|event|doctor visit|doctor appointment)\b"
    )

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def _find_layer_record(
        records_by_layer: dict[BrainLayer, BrainRecord], layer: BrainLayer
    ) -> BrainRecord | None:
        return records_by_layer.get(layer)

    @staticmethod
    def _facts(record: BrainRecord | None) -> list[str]:
        if record is None:
            return []
        return [fact.statement for fact in record.facts]

    @staticmethod
    def _extract_user_name(record: BrainRecord | None) -> str | None:
        if record is None:
            return None

        for fact in record.facts:
            text = fact.statement.strip()
            lowered = text.lower()
            if "otis duncan" in lowered:
                return "Otis Duncan"
            if lowered.startswith("the user/operator is "):
                value = text.split("is", 1)[-1].strip().strip(".")
                if value:
                    return value
        return None

    @staticmethod
    def _session_active_focus_summary(session_metadata: dict[str, Any]) -> str | None:
        focus_payload = session_metadata.get("active_focus")
        if isinstance(focus_payload, dict):
            summary = str(focus_payload.get("summary", "")).strip()
            if summary:
                return summary
        if isinstance(focus_payload, str):
            summary = focus_payload.strip()
            if summary:
                return summary
        return None

    @staticmethod
    def _session_memory_hints(session_metadata: dict[str, Any]) -> dict[str, Any]:
        hints = session_metadata.get("auto_memory_hints")
        return hints if isinstance(hints, dict) else {}

    @staticmethod
    def _normalize_reminder_request(question: str) -> str:
        text = re.sub(r"\s+", " ", question.strip())
        text = re.sub(
            r"^(please\s+)?(set|create|add)\s+(me\s+)?(a\s+)?reminder\s+(for|to)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"^(please\s+)?remind me\s+(to\s+)?", "", text, flags=re.IGNORECASE
        )
        text = text.strip(" .")
        if not text:
            return "your requested reminder details"
        text = re.sub(r"(?i)\ba\.m\.", "AM", text)
        text = re.sub(r"(?i)\bp\.m\.", "PM", text)
        text = re.sub(
            r"\bat\s+(\d{1,2}:\d{2})\s*(AM|PM)\s+to\s+",
            r"at \1 \2 — ",
            text,
            flags=re.IGNORECASE,
        )
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    @staticmethod
    def _has_live_repo_check_proof(session_metadata: dict[str, Any]) -> bool:
        proof = session_metadata.get("live_repo_check")
        if isinstance(proof, bool):
            return proof

        checks = session_metadata.get("tool_results")
        if isinstance(checks, list):
            for item in checks:
                if (
                    isinstance(item, dict)
                    and str(item.get("type", "")).lower() == "repo_check"
                ):
                    return True
        return False

    @staticmethod
    def _latest_model_tag(session_metadata: dict[str, Any]) -> str | None:
        receipt = session_metadata.get("model_use_receipt")
        if not isinstance(receipt, dict):
            return None

        selection_source = str(receipt.get("model_selection_source", "")).lower()
        if selection_source in {"brain_records", "brain_policy", "policy_only"}:
            return None

        tag = receipt.get("model_tag")
        if not isinstance(tag, str) or not tag.strip():
            return None
        cleaned = tag.strip()
        if cleaned.lower() == "xv7-brain-records":
            return None
        return cleaned

    @staticmethod
    def _last_verified_operator_model(record: BrainRecord | None) -> str | None:
        if record is None:
            return None

        for fact in record.facts:
            lowered = fact.statement.lower()
            if (
                "operator readiness" not in lowered
                and "operator_readiness_report" not in lowered
            ):
                continue

            match = re.search(r"\b([a-z0-9_.-]+:[a-z0-9_.-]+)\b", fact.statement)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def is_code_artifact_request(normalized_question: str) -> bool:
        return IntentRouter.is_code_artifact_request(normalized_question)

    @staticmethod
    def _code_artifact_language(normalized_question: str) -> str:
        return CodeArtifactBuilder.code_artifact_language(normalized_question)
        return "html"

    @staticmethod
    def _code_artifact_filename(language: str) -> str:
        return CodeArtifactBuilder.code_artifact_filename(language)
        return "index.html"

    @staticmethod
    def _clean_artifact_label(text: str) -> str:
        return CodeArtifactBuilder.clean_artifact_label(text)

    @classmethod
    def _extract_artifact_name(cls, question: str) -> str | None:
        return CodeArtifactBuilder.extract_artifact_name(question)
        return None

    @staticmethod
    def _artifact_business_category(question: str, name: str | None) -> str:
        return CodeArtifactBuilder.artifact_business_category(question, name)
        return "generic"

    @staticmethod
    def _artifact_style_profile(question: str, category: str) -> dict[str, str]:
        return CodeArtifactBuilder.artifact_style_profile(question, category)

    @staticmethod
    def _format_business_name(name: str | None, fallback: str) -> str:
        return CodeArtifactBuilder.format_business_name(name, fallback)

    @classmethod
    def _build_business_site_template(cls, question: str) -> dict[str, Any]:
        return CodeArtifactBuilder.build_business_site_template(question)

    @staticmethod
    def _default_code_artifact_content(
        filename: str, language: str, question: str
    ) -> str:
        return CodeArtifactBuilder.default_code_artifact_content(
            filename,
            language,
            question,
        )
        return f"# Draft artifact for {filename}\n"

    @staticmethod
    def _extract_requested_filename(question: str, language: str) -> str:
        return CodeArtifactBuilder.extract_requested_filename(question, language)
        return AnswerContract._code_artifact_filename(language)

    @staticmethod
    def _extract_requested_previewable(question: str, language: str) -> bool:
        return CodeArtifactBuilder.extract_requested_previewable(question, language)
        return language == "html"

    @staticmethod
    def _extract_apply_intent(question: str) -> bool:
        return CodeArtifactBuilder.extract_apply_intent(question)
        return False

    @staticmethod
    def _extract_style_hints(question: str) -> dict[str, list[str]]:
        return CodeArtifactBuilder.extract_style_hints(question)

    @staticmethod
    def _extract_layout_hints(question: str) -> list[str]:
        return CodeArtifactBuilder.extract_layout_hints(question)

    @staticmethod
    def _artifact_intent_label(question: str) -> str:
        return CodeArtifactBuilder.artifact_intent_label(question)
        return "code artifact"

    @classmethod
    def _extract_prompt_fidelity_contract(cls, question: str) -> dict[str, Any]:
        return ArtifactFidelityManager.extract_prompt_fidelity_contract(question)

    @staticmethod
    def _color_hex_map() -> dict[str, list[str]]:
        return ArtifactFidelityManager.color_hex_map()

    @staticmethod
    def _service_terms_for_business_type(business_type: str) -> tuple[str, ...]:
        return ArtifactFidelityManager.service_terms_for_business_type(business_type)

    @classmethod
    def _prompt_fidelity_forbidden_terms(
        cls,
        *,
        contract: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> list[str]:
        return ArtifactFidelityManager.prompt_fidelity_forbidden_terms(
            contract=contract,
            metadata=metadata,
        )

    @classmethod
    def validate_artifact_prompt_fidelity(
        cls,
        prompt: str,
        artifact_content: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return ArtifactFidelityManager.validate_artifact_prompt_fidelity(
            prompt,
            artifact_content,
            metadata,
        )

    @classmethod
    def _repair_artifact_prompt_fidelity(
        cls,
        *,
        prompt: str,
        artifact_content: str,
        fidelity_report: dict[str, Any],
    ) -> str:
        return ArtifactFidelityManager.repair_artifact_prompt_fidelity(
            prompt=prompt,
            artifact_content=artifact_content,
            fidelity_report=fidelity_report,
        )

    @classmethod
    def _build_local_artifact_prompt(
        cls,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
        strict_retry: bool,
        retry_requirements: list[str] | None = None,
    ) -> str:
        return ArtifactFidelityManager.build_local_artifact_prompt(
            question=question,
            filename=filename,
            language=language,
            previewable=previewable,
            apply_requested=apply_requested,
            business_name=business_name,
            style_hints=style_hints,
            layout_hints=layout_hints,
            strict_retry=strict_retry,
            retry_requirements=retry_requirements,
        )

    @staticmethod
    def _remediation_for_validation_reason(reason: str) -> str:
        return ArtifactFidelityManager.remediation_for_validation_reason(reason)

    @staticmethod
    def _looks_like_artifact_edit(normalized_question: str) -> bool:
        return IntentRouter.looks_like_artifact_edit(normalized_question)

    @staticmethod
    def _extract_business_name_from_html(content: str) -> str | None:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL
        )
        if title_match:
            value = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip()
            if value:
                return value
        h1_match = re.search(
            r"<h1[^>]*>(.*?)</h1>", content, flags=re.IGNORECASE | re.DOTALL
        )
        if h1_match:
            raw = re.sub(r"<[^>]+>", "", h1_match.group(1))
            value = html.unescape(re.sub(r"\s+", " ", raw)).strip()
            if value:
                return value
        return None

    @staticmethod
    def _extract_artifact_from_metadata(
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(metadata, dict):
            return None

        # Site bundle takes priority when present.
        _site_bundle = metadata.get("site_bundle")
        if (
            isinstance(_site_bundle, dict)
            and _site_bundle.get("artifact_type") == "site_bundle"
        ):
            return dict(_site_bundle)

        artifacts: list[Any] = []
        code_artifacts = metadata.get("code_artifacts")
        if isinstance(code_artifacts, list):
            artifacts.extend(code_artifacts)

        single = metadata.get("code_artifact")
        if isinstance(single, dict):
            artifacts.append(single)

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            filename = str(artifact.get("filename", "")).strip()
            content = artifact.get("content")
            if filename and isinstance(content, str) and content.strip():
                return {
                    "type": "code_artifact",
                    "filename": filename,
                    "language": str(artifact.get("language") or "html").strip()
                    or "html",
                    "previewable": bool(artifact.get("previewable", True)),
                    "applied": bool(artifact.get("applied", False)),
                    "content": content,
                    "artifact_id": artifact.get("artifact_id"),
                    "revision_id": artifact.get("revision_id"),
                    "revision_number": artifact.get("revision_number"),
                    "source_prompt": artifact.get("source_prompt"),
                    "prompt_fidelity": artifact.get("prompt_fidelity"),
                    "created_at": artifact.get("created_at"),
                    "message_id": artifact.get("message_id"),
                }
        return None

    @classmethod
    def _prompt_fidelity_history_metadata(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        history_names: list[str] = []
        previous_colors: list[str] = []
        history = cls._artifact_history(session_messages, session_metadata)
        for item in history:
            artifact = item.get("artifact") if isinstance(item, dict) else None
            if not isinstance(artifact, dict):
                continue
            fidelity = artifact.get("prompt_fidelity")
            if isinstance(fidelity, dict):
                name = str(fidelity.get("requested_business_name") or "").strip()
                if name:
                    history_names.append(name)
                colors = fidelity.get("requested_colors")
                if isinstance(colors, list):
                    for color in colors:
                        token = str(color or "").strip().lower()
                        if token:
                            previous_colors.append(token)

            prompt = str(artifact.get("source_prompt") or "").strip()
            if prompt:
                extracted = cls._extract_prompt_fidelity_contract(prompt)
                name = str(extracted.get("requested_business_name") or "").strip()
                if name:
                    history_names.append(name)
                for color in extracted.get("requested_colors") or []:
                    token = str(color or "").strip().lower()
                    if token:
                        previous_colors.append(token)

        return {
            "history_business_names": list(dict.fromkeys(history_names)),
            "previous_colors": list(dict.fromkeys(previous_colors)),
        }

    @classmethod
    def _latest_assistant_artifact(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        history = cls._artifact_history(session_messages, session_metadata)
        if history:
            return history[-1]["artifact"], "latest session artifact"

        if isinstance(session_messages, list):
            for message in reversed(session_messages):
                if not isinstance(message, dict):
                    continue
                if str(message.get("role", "")).lower() != "assistant":
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                artifact = cls._extract_artifact_from_metadata(metadata)
                if artifact is not None:
                    return artifact, "latest session artifact"

        if isinstance(session_metadata, dict):
            last_payload = session_metadata.get("last_assistant_payload")
            if isinstance(last_payload, dict):
                artifact = cls._extract_artifact_from_metadata(last_payload)
                if artifact is not None:
                    return artifact, "previous assistant artifact"

        return None, None

    @staticmethod
    def _slugify_artifact_name(value: str) -> str:
        return slugify_artifact_name(value)

    @classmethod
    def _is_patch_proposal_request(cls, normalized_question: str) -> bool:
        if cls._is_first_class_operator_request(normalized_question):
            return False
        return bool(cls.ARTIFACT_PATCH_PROPOSAL_PATTERN.search(normalized_question))

    @classmethod
    def _is_patch_apply_request(cls, normalized_question: str) -> bool:
        return bool(cls.ARTIFACT_PATCH_APPLY_PATTERN.search(normalized_question))

    @classmethod
    def _is_post_apply_verify_request(cls, normalized_question: str) -> bool:
        return bool(cls.ARTIFACT_POST_APPLY_VERIFY_PATTERN.search(normalized_question))

    @classmethod
    def _is_post_apply_preview_request(cls, normalized_question: str) -> bool:
        return bool(cls.ARTIFACT_POST_APPLY_PREVIEW_PATTERN.search(normalized_question))

    @classmethod
    def _is_post_apply_targeted_validation_request(
        cls, normalized_question: str
    ) -> bool:
        return bool(
            cls.ARTIFACT_POST_APPLY_TARGETED_VALIDATION_PATTERN.search(
                normalized_question
            )
        )

    @classmethod
    def _is_post_apply_full_test_guard_request(cls, normalized_question: str) -> bool:
        return bool(
            cls.ARTIFACT_POST_APPLY_FULL_TEST_GUARD_PATTERN.search(normalized_question)
        )

    @classmethod
    def _is_commit_proposal_request(cls, normalized_question: str) -> bool:
        return bool(cls.COMMIT_PROPOSAL_PATTERN.search(normalized_question))

    @classmethod
    def _is_commit_approval_request(cls, normalized_question: str) -> bool:
        return bool(cls.COMMIT_APPROVAL_PATTERN.search(normalized_question))

    @classmethod
    def _is_post_apply_intent_request(cls, normalized_question: str) -> bool:
        return any(
            (
                cls._is_post_apply_verify_request(normalized_question),
                cls._is_post_apply_preview_request(normalized_question),
                cls._is_post_apply_targeted_validation_request(normalized_question),
                cls._is_post_apply_full_test_guard_request(normalized_question),
            )
        )

    @classmethod
    def _has_explicit_artifact_intent(cls, normalized_question: str) -> bool:
        return IntentRouter.has_explicit_artifact_intent(normalized_question)

    @classmethod
    def _is_preview_artifact_request(cls, normalized_question: str) -> bool:
        return IntentRouter.is_preview_artifact_request(normalized_question)

    @classmethod
    def _is_sandbox_build_request(cls, normalized_question: str) -> bool:
        return IntentRouter.is_sandbox_build_request(normalized_question)

    @classmethod
    def _is_operator_github_project_request(cls, normalized_question: str) -> bool:
        return IntentRouter.is_operator_github_project_request(normalized_question)

    @classmethod
    def _is_first_class_operator_request(cls, normalized_question: str) -> bool:
        return IntentRouter.is_operator_project_command_request(normalized_question)

    @classmethod
    def _is_repo_mutation_build_prompt(cls, normalized_question: str) -> bool:
        return IntentRouter.is_repo_mutation_build_prompt(normalized_question)
        return False

    @classmethod
    def _prioritize_artifact_over_build_guard(cls, normalized_question: str) -> bool:
        return IntentRouter.prioritize_artifact_over_build_guard(normalized_question)

    @staticmethod
    def _workspace_root() -> Path:
        return RepoSafetyPolicy.workspace_root()

    @staticmethod
    def _sandbox_root() -> Path:
        return SandboxWriteManager.sandbox_root()

    @staticmethod
    def _sandbox_display_root() -> str:
        return SandboxWriteManager.sandbox_display_root()

    @classmethod
    def _safe_slug(cls, raw: str | None, fallback: str) -> str:
        return safe_slug(raw, fallback)

    @staticmethod
    def _sanitize_filename(filename: str, language: str) -> str:
        return SandboxWriteManager.sanitize_filename(filename, language)

    @classmethod
    def _resolve_safe_sandbox_target(
        cls,
        *,
        root: Path,
        target_path: str,
    ) -> tuple[Path | None, str | None]:
        return SandboxWriteManager.resolve_safe_target(
            root=root,
            target_path=target_path,
        )

    @classmethod
    def _sandbox_relative_file_path(
        cls,
        *,
        project_slug: str,
        filename: str,
    ) -> str:
        return SandboxWriteManager.relative_file_path(
            project_slug=project_slug,
            filename=filename,
            language=cls._code_artifact_language(filename),
        )

    @classmethod
    def _write_sandbox_file(
        cls,
        *,
        project_slug: str,
        filename: str,
        content: str,
    ) -> tuple[str, str]:
        return SandboxWriteManager.write_file(
            project_slug=project_slug,
            filename=filename,
            content=content,
            language=cls._code_artifact_language(filename),
        )

    @classmethod
    def _write_sandbox_bundle(
        cls,
        *,
        project_slug: str,
        bundle_files: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        return SandboxWriteManager.write_bundle(
            project_slug=project_slug,
            bundle_files=bundle_files,
        )

    @staticmethod
    def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return run_git(repo_root, args)

    @classmethod
    def _proposed_patch_target_path(
        cls,
        *,
        artifact: dict[str, Any],
    ) -> str:
        language = str(artifact.get("language") or "html").lower()
        filename = cls._sanitize_filename(str(artifact.get("filename") or ""), language)
        business_name = cls._extract_business_name_from_html(
            str(artifact.get("content") or "")
        )
        artifact_id = str(artifact.get("artifact_id") or "artifact")
        suffix = cls._slugify_artifact_name(artifact_id)[-6:] or "draft"
        slug = cls._safe_slug(business_name, fallback=f"artifact-{suffix}")
        return f"generated-sites/{slug}/{filename}"

    @staticmethod
    def _is_blocked_patch_target(path_text: str) -> bool:
        return RepoSafetyPolicy.is_blocked_patch_target(path_text)

    @staticmethod
    def _is_blocked_commit_target(path_text: str) -> bool:
        return RepoSafetyPolicy.is_blocked_commit_target(path_text)

    @classmethod
    def _validate_patch_proposal(
        cls,
        *,
        root: Path,
        target_path: str,
        content: str,
        language: str,
        business_name: str,
        operation: str,
    ) -> tuple[str, list[dict[str, str]], list[str]]:
        return RepoSafetyPolicy.validate_patch_proposal(
            root=root,
            target_path=target_path,
            content=content,
            language=language,
            business_name=business_name,
            operation=operation,
        )

    @staticmethod
    def _content_sha256(content: str) -> str:
        return content_sha256(content)

    @staticmethod
    def _utc_now_iso() -> str:
        return utc_now_iso()

    @classmethod
    def _resolve_safe_patch_target(
        cls,
        *,
        root: Path,
        target_path: str,
    ) -> tuple[Path | None, str | None]:
        return RepoSafetyPolicy.resolve_safe_patch_target(
            root=root, target_path=target_path
        )

    @classmethod
    def _verify_applied_patch_content(
        cls,
        *,
        proposal: dict[str, Any],
        include_business_name: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        root = cls._workspace_root()
        target_path = str(proposal.get("target_path") or "").replace("\\", "/")
        expected_content = str(proposal.get("content") or "")
        language = str(proposal.get("language") or "html").lower()
        checks: list[dict[str, str]] = []
        failures: list[str] = []

        def _add(name: str, passed: bool, detail: str) -> None:
            checks.append(
                {
                    "name": name,
                    "status": "passed" if passed else "failed",
                    "detail": detail,
                }
            )
            if not passed:
                failures.append(f"{name}: {detail}")

        resolved, resolve_error = cls._resolve_safe_patch_target(
            root=root, target_path=target_path
        )
        _add(
            "safe_target_path",
            resolve_error is None and resolved is not None,
            resolve_error or "target path resolved safely",
        )

        actual_content = ""
        if resolved is not None:
            exists = resolved.exists()
            _add(
                "file_exists",
                exists,
                "file exists on disk" if exists else "file is missing on disk",
            )
            if exists:
                actual_content = resolved.read_text(encoding="utf-8")
                _add(
                    "content_non_empty",
                    bool(actual_content.strip()),
                    "file content is non-empty",
                )
                _add(
                    "content_matches_applied_proposal",
                    actual_content == expected_content,
                    "file content matches applied proposal",
                )
                _add(
                    "content_no_markdown_fence",
                    "```" not in actual_content,
                    "content has no markdown fences",
                )
                _add(
                    "content_no_remote_scripts_assets",
                    not re.search(
                        r"<script[^>]+src\s*=\s*['\"]https?://",
                        actual_content,
                        flags=re.IGNORECASE,
                    )
                    and not re.search(
                        r"<(img|link|source)[^>]+(src|href)\s*=\s*['\"]https?://",
                        actual_content,
                        flags=re.IGNORECASE,
                    ),
                    "content has no remote script or asset URLs",
                )
                if language == "html":
                    lowered = actual_content.lower()
                    _add(
                        "html_shell",
                        "<!doctype html" in lowered or "<html" in lowered,
                        "html shell markers are present",
                    )
                if include_business_name:
                    business_name = (
                        cls._extract_business_name_from_html(expected_content) or ""
                    )
                    if business_name:
                        _add(
                            "business_name_present",
                            business_name.lower() in actual_content.lower(),
                            "business name remains present",
                        )

        status = "failed" if failures else "passed"
        verification = {
            "status": status,
            "verified": status == "passed",
            "checks": checks,
            "failures": failures,
            "verified_at": cls._utc_now_iso(),
            "content_length": len(actual_content) if actual_content else 0,
            "content_sha256": (
                cls._content_sha256(actual_content) if actual_content else ""
            ),
        }
        return verification, {
            "actual_content": actual_content,
            "target_path": target_path,
        }

    @classmethod
    def _applied_patch_with_runtime_fields(
        cls,
        *,
        proposal: dict[str, Any],
        verification: dict[str, Any] | None = None,
        targeted_validation: dict[str, Any] | None = None,
        preview_path: str | None = None,
    ) -> dict[str, Any]:
        content = str(proposal.get("content") or "")
        updated = {
            **proposal,
            "applied": bool(proposal.get("applied", False)),
            "applied_at": str(proposal.get("applied_at") or cls._utc_now_iso()),
            "content_length": len(content),
            "content_sha256": cls._content_sha256(content) if content else "",
            "source_artifact_id": str(proposal.get("source_artifact_id") or ""),
            "validation_status": str(
                (proposal.get("validation") or {}).get("status") or "failed"
            ),
            "tests_run": bool(proposal.get("tests_run", False)),
            "commit_created": bool(proposal.get("commit_created", False)),
            "push_performed": bool(proposal.get("push_performed", False)),
        }
        if verification is not None:
            updated["post_apply_verification"] = verification
        if targeted_validation is not None:
            updated["targeted_validation"] = targeted_validation
        if preview_path:
            updated["preview_path"] = preview_path
        return updated

    @classmethod
    def _build_unified_diff(
        cls,
        *,
        target_path: str,
        before_content: str | None,
        after_content: str,
    ) -> str:
        before_lines = (
            [] if before_content is None else before_content.splitlines(keepends=True)
        )
        after_lines = after_content.splitlines(keepends=True)
        from_file = "/dev/null" if before_content is None else f"a/{target_path}"
        to_file = f"b/{target_path}"
        diff = difflib.unified_diff(
            before_lines, after_lines, fromfile=from_file, tofile=to_file, n=3
        )
        text = "".join(diff).strip()
        return text or f"--- {from_file}\n+++ {to_file}\n"

    @classmethod
    def _extract_patch_proposal_from_metadata(
        cls, metadata: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not isinstance(metadata, dict):
            return None
        proposal = metadata.get("artifact_patch_proposal")
        if not isinstance(proposal, dict):
            return None
        if str(proposal.get("type") or "") != "artifact_patch_proposal":
            return None
        target_path = str(proposal.get("target_path") or "").strip()
        content = proposal.get("content")
        if not target_path or not isinstance(content, str):
            return None
        return proposal

    # site_bundle session helpers are delegated to the sb module.

    @classmethod
    def _latest_pending_patch_proposal(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if isinstance(session_messages, list):
            for message in reversed(session_messages):
                if not isinstance(message, dict):
                    continue
                if str(message.get("role") or "").lower() != "assistant":
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                proposal = cls._extract_patch_proposal_from_metadata(metadata)
                if proposal is None:
                    continue
                if proposal.get("applied") is True:
                    continue
                return proposal

        if isinstance(session_metadata, dict):
            payload = session_metadata.get("last_assistant_payload")
            if isinstance(payload, dict):
                proposal = cls._extract_patch_proposal_from_metadata(payload)
                if proposal is not None and proposal.get("applied") is not True:
                    return proposal
        return None

    @classmethod
    def _latest_applied_patch_proposal(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if isinstance(session_messages, list):
            for message in reversed(session_messages):
                if not isinstance(message, dict):
                    continue
                if str(message.get("role") or "").lower() != "assistant":
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                proposal = cls._extract_patch_proposal_from_metadata(metadata)
                if proposal is None:
                    continue
                if proposal.get("applied") is True:
                    return proposal

        if isinstance(session_metadata, dict):
            payload = session_metadata.get("last_assistant_payload")
            if isinstance(payload, dict):
                proposal = cls._extract_patch_proposal_from_metadata(payload)
                if proposal is not None and proposal.get("applied") is True:
                    return proposal
        return None

    @classmethod
    def _extract_commit_proposal_from_metadata(
        cls, metadata: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not isinstance(metadata, dict):
            return None
        proposal = metadata.get("commit_proposal")
        if not isinstance(proposal, dict):
            return None
        if str(proposal.get("type") or "") != "commit_proposal":
            return None
        proposal_id = str(proposal.get("proposal_id") or "").strip()
        if not proposal_id:
            return None
        return proposal

    @classmethod
    def _latest_pending_commit_proposal(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if isinstance(session_messages, list):
            for message in reversed(session_messages):
                if not isinstance(message, dict):
                    continue
                if str(message.get("role") or "").lower() != "assistant":
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                proposal = cls._extract_commit_proposal_from_metadata(metadata)
                if proposal is None:
                    continue
                if proposal.get("committed") is True:
                    continue
                return proposal

        if isinstance(session_metadata, dict):
            payload = session_metadata.get("last_assistant_payload")
            if isinstance(payload, dict):
                proposal = cls._extract_commit_proposal_from_metadata(payload)
                if proposal is not None and proposal.get("committed") is not True:
                    return proposal
        return None

    @classmethod
    def _build_commit_proposal(
        cls,
        *,
        question: str,
        session_messages: list[Any] | None = None,
        session_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        root = cls._workspace_root()
        proposal_id = f"commit-{uuid4().hex[:12]}"

        # Check git availability using --git-dir which works on repos with no commits.
        # (rev-parse --abbrev-ref HEAD fails with exit 128 on a fresh unborn repo.)
        git_dir_proc = cls._run_git(root, ["rev-parse", "--git-dir"])
        git_available = git_dir_proc.returncode == 0

        if git_available:
            # symbolic-ref works on fresh repos; rev-parse --abbrev-ref HEAD doesn't.
            sym_proc = cls._run_git(root, ["symbolic-ref", "--short", "HEAD"])
            if sym_proc.returncode == 0:
                branch = sym_proc.stdout.strip()
            else:
                abbrev_proc = cls._run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
                branch = (
                    abbrev_proc.stdout.strip()
                    if abbrev_proc.returncode == 0
                    else "unknown"
                )
        else:
            branch = "unknown"

        # Applied-patch-aware path: prefer the applied patch from session state over
        # generic git-status scan so that container/host path issues are diagnosed
        # precisely rather than silently returning an empty proposal.
        applied_patch = cls._latest_applied_patch_proposal(
            session_messages, session_metadata
        )
        if applied_patch is not None:
            target_path = str(applied_patch.get("target_path") or "").replace("\\", "/")
            if target_path:
                target_abs = (root / Path(target_path)).resolve()
                file_exists = target_abs.exists()

                if not git_available:
                    # Running inside a container with no .git — clear diagnostic
                    if file_exists:
                        return {
                            "type": "commit_proposal",
                            "proposal_id": proposal_id,
                            "question": question,
                            "branch": "unknown",
                            "applied": False,
                            "committed": False,
                            "push_performed": False,
                            "requires_confirmation": True,
                            "included_files": [],
                            "excluded_files": [],
                            "status_lines": [],
                            "change_lines": [],
                            "diff_stat": "",
                            "proposed_commit_message": "",
                            "source_applied_patch": target_path,
                            "git_available": False,
                            "container_path_mismatch": True,
                            "visible_text": (
                                f"The applied patch target {target_path} exists in the runtime container, "
                                "but Git is not available in this environment. "
                                "I cannot prepare a host commit from inside the container. "
                                "The file was written correctly but committing must be done from the host workspace."
                            ),
                        }
                    return {
                        "type": "commit_proposal",
                        "proposal_id": proposal_id,
                        "question": question,
                        "branch": "unknown",
                        "applied": False,
                        "committed": False,
                        "push_performed": False,
                        "requires_confirmation": True,
                        "included_files": [],
                        "excluded_files": [],
                        "status_lines": [],
                        "change_lines": [],
                        "diff_stat": "",
                        "proposed_commit_message": "",
                        "source_applied_patch": target_path,
                        "git_available": False,
                        "visible_text": (
                            f"The applied patch target {target_path} does not exist on disk "
                            "and Git is not available in this environment. "
                            "No commit was created and no push was performed."
                        ),
                    }

                # Git is available — check file presence
                if not file_exists:
                    return {
                        "type": "commit_proposal",
                        "proposal_id": proposal_id,
                        "question": question,
                        "branch": branch,
                        "applied": False,
                        "committed": False,
                        "push_performed": False,
                        "requires_confirmation": True,
                        "included_files": [],
                        "excluded_files": [],
                        "status_lines": [],
                        "change_lines": [],
                        "diff_stat": "",
                        "proposed_commit_message": "",
                        "source_applied_patch": target_path,
                        "visible_text": (
                            f"The applied patch target {target_path} does not exist on disk. "
                            "No commit was created and no push was performed."
                        ),
                    }

                # Check whether this specific path is gitignored
                ignore_proc = cls._run_git(
                    root, ["check-ignore", "-v", "--", target_path]
                )
                if ignore_proc.returncode == 0:
                    return {
                        "type": "commit_proposal",
                        "proposal_id": proposal_id,
                        "question": question,
                        "branch": branch,
                        "applied": False,
                        "committed": False,
                        "push_performed": False,
                        "requires_confirmation": True,
                        "included_files": [],
                        "excluded_files": [],
                        "status_lines": [],
                        "change_lines": [],
                        "diff_stat": "",
                        "proposed_commit_message": "",
                        "source_applied_patch": target_path,
                        "ignored_paths": [target_path],
                        "visible_text": (
                            f"The applied patch target {target_path} is excluded by .gitignore. "
                            "I cannot prepare a commit for an ignored path. "
                            "No commit was created and no push was performed."
                        ),
                    }

                # Check git status for this specific file
                status_proc = cls._run_git(
                    root, ["status", "--porcelain", "--", target_path]
                )
                status_line = status_proc.stdout.strip()
                if not status_line:
                    return {
                        "type": "commit_proposal",
                        "proposal_id": proposal_id,
                        "question": question,
                        "branch": branch,
                        "applied": False,
                        "committed": False,
                        "push_performed": False,
                        "requires_confirmation": True,
                        "included_files": [],
                        "excluded_files": [],
                        "status_lines": [],
                        "change_lines": [],
                        "diff_stat": "",
                        "proposed_commit_message": "",
                        "source_applied_patch": target_path,
                        "no_diff": True,
                        "visible_text": (
                            f"The applied patch target exists, but Git does not show a diff for {target_path}, "
                            "so there is nothing to commit."
                        ),
                    }

                # File is untracked or modified — build proposal from it
                applied_target_stem = Path(target_path).stem
                proposed_message = f"feat: add {applied_target_stem} generated site"
                return {
                    "type": "commit_proposal",
                    "proposal_id": proposal_id,
                    "question": question,
                    "branch": branch,
                    "applied": False,
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                    "included_files": [target_path],
                    "excluded_files": [],
                    "status_lines": [status_line],
                    "change_lines": [f"{status_line[:2].rstrip()} {target_path}"],
                    "diff_stat": "",
                    "proposed_commit_message": proposed_message,
                    "source_applied_patch": target_path,
                    "visible_text": (
                        f"I prepared a commit proposal for {target_path} on branch {branch}. "
                        "No files were changed, no commit was created, and no push was performed."
                    ),
                }

        # No applied patch in session — fall back to generic git status scan
        if not git_available:
            return {
                "type": "commit_proposal",
                "proposal_id": proposal_id,
                "question": question,
                "branch": "unknown",
                "applied": False,
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
                "included_files": [],
                "excluded_files": [],
                "status_lines": [],
                "change_lines": [],
                "diff_stat": "",
                "proposed_commit_message": "",
                "git_available": False,
                "visible_text": (
                    "Git is not available in this environment. "
                    "I cannot prepare a commit proposal without a Git workspace. "
                    "No commit was created and no push was performed."
                ),
            }

        status_proc = cls._run_git(
            root, ["status", "--porcelain", "--untracked-files=all"]
        )
        diff_stat_proc = cls._run_git(root, ["diff", "--stat"])

        raw_status_lines = [
            line.strip() for line in status_proc.stdout.splitlines() if line.strip()
        ]
        included_files: list[str] = []
        excluded_files: list[str] = []
        change_lines: list[str] = []
        for line in raw_status_lines:
            if len(line) < 4:
                continue
            path_text = line[3:].strip()
            if " -> " in path_text:
                path_text = path_text.split(" -> ", 1)[-1].strip()
            normalized_path = path_text.replace("\\", "/")
            if cls._is_blocked_commit_target(normalized_path):
                excluded_files.append(normalized_path)
                continue
            included_files.append(normalized_path)
            change_lines.append(f"{line[:2]} {normalized_path}")

        proposed_commit_message = (
            f"chore: update {Path(included_files[0]).stem}"
            if len(included_files) == 1
            else "chore: local repository changes"
        )
        visible_lines = []
        if included_files:
            visible_lines.append(
                f"I prepared a commit proposal for {len(included_files)} file(s) on branch {branch}. No files were changed, no commit was created, and no push was performed."
            )
        else:
            visible_lines.append(
                "I checked the repository and did not find any safe changes to include in a commit proposal. No files were changed and no commit was created."
            )
        if excluded_files:
            visible_lines.append(
                f"Excluded blocked paths: {', '.join(excluded_files[:5])}."
            )

        return {
            "type": "commit_proposal",
            "proposal_id": proposal_id,
            "question": question,
            "branch": branch,
            "applied": False,
            "committed": False,
            "push_performed": False,
            "requires_confirmation": True,
            "included_files": included_files,
            "excluded_files": excluded_files,
            "status_lines": raw_status_lines,
            "change_lines": change_lines,
            "diff_stat": (
                diff_stat_proc.stdout.strip() if diff_stat_proc.returncode == 0 else ""
            ),
            "proposed_commit_message": proposed_commit_message,
            "visible_text": " ".join(visible_lines),
        }

    @classmethod
    def _apply_commit_proposal(
        cls,
        *,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        root = cls._workspace_root()
        included_files = [
            str(path).replace("\\", "/")
            for path in proposal.get("included_files") or []
            if str(path).strip()
        ]
        if not included_files:
            return {
                "visible_text": "I cannot commit this proposal because there are no safe files to stage.",
                "commit_proposal": {
                    **proposal,
                    "applied": False,
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                },
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "commit_proposal": "apply_blocked",
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                    "failure_reason": "no_safe_files",
                },
            }

        add_proc = cls._run_git(root, ["add", "-A", "--", *included_files])
        if add_proc.returncode != 0:
            return {
                "visible_text": "I could not stage the proposed files for commit.",
                "commit_proposal": {
                    **proposal,
                    "applied": False,
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                },
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "commit_proposal": "stage_failed",
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                    "failure_reason": add_proc.stderr.strip() or "git add failed",
                },
            }

        commit_message = str(
            proposal.get("proposed_commit_message") or "chore: local repository changes"
        )
        commit_proc = cls._run_git(root, ["commit", "-m", commit_message])
        if commit_proc.returncode != 0:
            return {
                "visible_text": commit_proc.stderr.strip()
                or "I could not create the local commit.",
                "commit_proposal": {
                    **proposal,
                    "applied": False,
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                },
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "commit_proposal": "commit_failed",
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                    "failure_reason": commit_proc.stderr.strip() or "git commit failed",
                },
            }

        sha_proc = cls._run_git(root, ["rev-parse", "--short", "HEAD"])
        commit_sha = sha_proc.stdout.strip() if sha_proc.returncode == 0 else "unknown"
        committed_proposal = {
            **proposal,
            "applied": True,
            "committed": True,
            "committed_at": cls._utc_now_iso(),
            "commit_sha": commit_sha,
            "push_performed": False,
            "requires_confirmation": True,
        }
        return {
            "visible_text": (
                f"Committed the approved local changes on branch {committed_proposal.get('branch', 'unknown')} as {commit_sha}. "
                "No push was performed."
            ),
            "commit_proposal": committed_proposal,
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                "context_receipts": [],
                "record_ids": [],
            },
            "provenance": {
                "commit_proposal": "committed",
                "committed": True,
                "push_performed": False,
                "requires_confirmation": True,
                "commit_sha": commit_sha,
            },
        }

    @classmethod
    def _build_patch_proposal_from_artifact(
        cls,
        *,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        root = cls._workspace_root()
        language = str(artifact.get("language") or "html").lower()
        filename = cls._sanitize_filename(
            str(artifact.get("filename") or "index.html"), language
        )
        target_path = cls._proposed_patch_target_path(artifact=artifact)
        resolved_target = (root / Path(target_path)).resolve()
        source_artifact_id = str(
            artifact.get("revision_id") or artifact.get("artifact_id") or "artifact"
        )
        current_content = str(artifact.get("content") or "")
        existing_content = (
            resolved_target.read_text(encoding="utf-8")
            if resolved_target.exists()
            else None
        )
        operation = "update" if existing_content is not None else "create"
        business_name = cls._extract_business_name_from_html(current_content) or ""
        validation_status, checks, failures = cls._validate_patch_proposal(
            root=root,
            target_path=target_path,
            content=current_content,
            language=language,
            business_name=business_name,
            operation=operation,
        )
        proposal_id = f"patch-{uuid4().hex[:12]}"
        diff_text = cls._build_unified_diff(
            target_path=target_path,
            before_content=existing_content,
            after_content=current_content,
        )

        return {
            "type": "artifact_patch_proposal",
            "proposal_id": proposal_id,
            "source_artifact_id": source_artifact_id,
            "filename": filename,
            "target_path": target_path,
            "operation": operation,
            "language": language,
            "applied": False,
            "requires_confirmation": True,
            "content": current_content,
            "diff": diff_text,
            "validation": {
                "status": validation_status,
                "checks": checks,
                "failures": failures,
            },
        }

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
            retry_line = "This is a retry because the first revision failed validation."
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

    @classmethod
    def _validate_artifact_content(
        cls,
        *,
        content: str,
        language: str,
        business_name: str,
        style_hints: dict[str, list[str]],
        requested_question: str,
    ) -> tuple[bool, str]:
        lowered = content.lower()
        requested_lower = requested_question.lower()

        if not content.strip():
            return False, "empty_content"
        if "```" in content:
            return False, "markdown_fence_detected"
        if len(content) < 120 or len(content) > 120000:
            return False, "content_length_out_of_bounds"
        if business_name and business_name.lower() not in lowered:
            return False, "business_name_missing"

        for hint in style_hints.get("colors", []):
            if hint.startswith("#"):
                if hint.lower() in lowered:
                    break
            elif re.search(rf"\b{re.escape(hint.lower())}\b", lowered):
                break
        else:
            if style_hints.get("colors"):
                return False, "color_hints_missing"

        if style_hints.get("styles"):
            found_style = any(
                re.search(rf"\b{re.escape(token.lower())}\b", lowered)
                for token in style_hints["styles"]
            )
            if not found_style:
                return False, "style_hints_missing"

        protected_names = (
            "harry's hot dog cart",
            "flow flowers",
            "rico's mobile detailing",
            "rico's detailing",
            "neon byte arcade",
            "crimson turtle locksmiths",
        )
        for name in protected_names:
            if name in lowered and name not in requested_lower:
                return False, "stale_business_leak_detected"

        if language == "html":
            if "<!doctype html" not in lowered and "<html" not in lowered:
                return False, "html_shell_missing"
            if "<style" not in lowered:
                return False, "inline_css_missing"

        if (
            business_name
            and business_name.lower() != "local business website"
            and "local business website" in lowered
        ):
            return False, "generic_business_name_fallback_detected"

        is_crimson_locksmith = (
            "crimson turtle locksmiths" in requested_lower
            or "locksmith" in requested_lower
            or "lockout" in requested_lower
        )
        if is_crimson_locksmith:
            locksmith_keywords = (
                "locksmith",
                "security",
                "key",
                "lock",
                "emergency",
                "lockout",
            )
            if not any(
                re.search(rf"\b{re.escape(token)}\b", lowered)
                for token in locksmith_keywords
            ):
                return False, "crimson_locksmith_language_missing"
            if "urgent" not in lowered or "trust" not in lowered:
                return False, "crimson_urgency_trust_copy_missing"
            if not any(token in lowered for token in ("black", "#000", "#111", "dark")):
                return False, "crimson_color_black_missing"
            if not any(token in lowered for token in ("red", "#dc", "#ef", "#b9")):
                return False, "crimson_color_red_missing"
            if not any(
                token in lowered
                for token in ("silver", "gray", "grey", "metal", "#9ca3af", "#c0c0c0")
            ):
                return False, "crimson_color_silver_missing"
            irrelevant = (
                "hot dog",
                "bouquet",
                "florist",
                "arcade",
                "detailing",
                "chili dog",
            )
            if any(token in lowered for token in irrelevant):
                return False, "crimson_irrelevant_copy_detected"

        is_grooming = any(
            token in requested_lower
            for token in (
                "grooming",
                "dog grooming",
                "pet grooming",
                "puppy",
                "dog wash",
                "bath",
                "trim",
                "fur",
                "paw",
                "kennel",
                "spa",
            )
        )
        if is_grooming:
            grooming_keywords = (
                "groom",
                "pet",
                "dog",
                "bath",
                "wash",
                "trim",
                "fur",
                "paw",
            )
            if not any(
                re.search(rf"\b{re.escape(token)}\b", lowered)
                for token in grooming_keywords
            ):
                return False, "grooming_language_missing"
            if any(
                token in lowered
                for token in (
                    "harry",
                    "flow flowers",
                    "rico",
                    "neon byte",
                    "crimson turtle",
                )
            ) and (business_name.lower() not in lowered if business_name else True):
                return False, "grooming_irrelevant_copy_detected"

        if any(
            token in requested_lower
            for token in (
                "locksmith",
                "florist",
                "detailing",
                "arcade",
                "grooming",
                "pet grooming",
                "dog grooming",
            )
        ):
            if "a clean one-page website with a clear offer" in lowered:
                return False, "generic_hero_reuse_detected"

        return True, "passed"

    async def _generate_artifact_with_local_model(
        self,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
    ) -> tuple[str, str, str]:
        model_resolution = resolve_model_for_runtime_role("code")
        model_tag = model_resolution.model_tag
        if not model_tag:
            raise RuntimeError(
                "No configured code model available for artifact generation"
            )

        timeout_seconds = float(os.getenv("XV7_ARTIFACT_MODEL_TIMEOUT_SECONDS", "8"))
        timeout = httpx.Timeout(
            connect=10.0, read=timeout_seconds, write=30.0, pool=10.0
        )
        endpoint_candidates = configured_ollama_base_url_candidates()
        payload_base = {
            "model": model_tag,
            "stream": False,
            "keep_alive": -1,
            "options": {
                "num_ctx": 8192,
                "num_predict": 2200,
                "temperature": 0.3,
            },
        }

        system_prompt = (
            "You are a strict code generator. Return only source code text that compiles or renders for the requested language. "
            "Never include markdown fences or prose."
        )

        last_error = "model_generation_failed"
        retry_requirements: list[str] = []
        for strict_retry in (False, True):
            user_prompt = self._build_local_artifact_prompt(
                question=question,
                filename=filename,
                language=language,
                previewable=previewable,
                apply_requested=apply_requested,
                business_name=business_name,
                style_hints=style_hints,
                layout_hints=layout_hints,
                strict_retry=strict_retry,
                retry_requirements=retry_requirements,
            )
            payload = {
                **payload_base,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }

            for endpoint in endpoint_candidates:
                try:
                    async with httpx.AsyncClient(
                        base_url=endpoint, timeout=timeout
                    ) as client:
                        response = await client.post("/api/chat", json=payload)
                        response.raise_for_status()
                    data: dict[str, Any] = response.json()
                    message = data.get("message")
                    if not isinstance(message, dict):
                        last_error = "missing_message"
                        continue
                    raw_content = message.get("content")
                    if not isinstance(raw_content, str) or not raw_content.strip():
                        last_error = "missing_content"
                        continue
                    candidate = self._strip_markdown_fences(raw_content)
                    valid, reason = self._validate_artifact_content(
                        content=candidate,
                        language=language,
                        business_name=business_name,
                        style_hints=style_hints,
                        requested_question=question,
                    )
                    if valid:
                        return candidate, model_tag, endpoint
                    last_error = reason
                    remediation = self._remediation_for_validation_reason(reason)
                    if remediation not in retry_requirements:
                        retry_requirements.append(remediation)
                except (httpx.TimeoutException, httpx.HTTPError) as exc:
                    last_error = f"{endpoint}: {exc}"

        raise RuntimeError(last_error)

    async def _revise_artifact_with_local_model(
        self,
        *,
        question: str,
        source_artifact: dict[str, Any],
    ) -> tuple[str, str, str]:
        model_resolution = resolve_model_for_runtime_role("code")
        model_tag = model_resolution.model_tag
        if not model_tag:
            raise RuntimeError(
                "No configured code model available for artifact revision"
            )

        timeout_seconds = float(os.getenv("XV7_ARTIFACT_MODEL_TIMEOUT_SECONDS", "8"))
        timeout = httpx.Timeout(
            connect=10.0, read=timeout_seconds, write=30.0, pool=10.0
        )
        endpoint_candidates = configured_ollama_base_url_candidates()
        payload_base = {
            "model": model_tag,
            "stream": False,
            "keep_alive": -1,
            "options": {
                "num_ctx": 12288,
                "num_predict": 2600,
                "temperature": 0.25,
            },
        }

        system_prompt = "You are a strict code revision model. Return only complete revised source code with no markdown fences and no prose."

        source_content = str(source_artifact.get("content") or "")
        revision_mode = str(source_artifact.get("_revision_mode") or "full_revision")
        retry_requirements: list[str] = []
        last_error = "artifact_revision_failed"

        for strict_retry in (False, True):
            user_prompt = self._build_local_artifact_revision_prompt(
                edit_instruction=question,
                source_artifact=source_artifact,
                revision_mode=revision_mode,
                strict_retry=strict_retry,
                retry_requirements=retry_requirements,
            )
            payload = {
                **payload_base,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }

            for endpoint in endpoint_candidates:
                try:
                    async with httpx.AsyncClient(
                        base_url=endpoint, timeout=timeout
                    ) as client:
                        response = await client.post("/api/chat", json=payload)
                        response.raise_for_status()
                    data: dict[str, Any] = response.json()
                    message = data.get("message")
                    if not isinstance(message, dict):
                        last_error = "missing_message"
                        continue
                    raw_content = message.get("content")
                    if not isinstance(raw_content, str) or not raw_content.strip():
                        last_error = "missing_content"
                        continue
                    candidate = self._strip_markdown_fences(raw_content)
                    if candidate.strip() == source_content.strip():
                        last_error = "revision_content_unchanged"
                        remediation = self._remediation_for_validation_reason(
                            last_error
                        )
                        if remediation not in retry_requirements:
                            retry_requirements.append(remediation)
                        continue
                    valid, reason = self._validate_revision_candidate(
                        content=candidate,
                        source_artifact=source_artifact,
                        requested_question=question,
                    )
                    if valid:
                        return candidate, model_tag, endpoint
                    last_error = reason
                    remediation = self._remediation_for_validation_reason(reason)
                    if remediation not in retry_requirements:
                        retry_requirements.append(remediation)
                except (httpx.TimeoutException, httpx.HTTPError) as exc:
                    last_error = f"{endpoint}: {exc}"

        raise RuntimeError(last_error)

    async def artifact_model_connectivity_diagnostic(self) -> dict[str, Any]:
        model_resolution = resolve_model_for_runtime_role("code")
        model_tag = model_resolution.model_tag
        endpoint_candidates = configured_ollama_base_url_candidates()
        timeout_seconds = float(os.getenv("XV7_ARTIFACT_MODEL_TIMEOUT_SECONDS", "8"))
        timeout = httpx.Timeout(
            connect=5.0, read=min(timeout_seconds, 10.0), write=10.0, pool=5.0
        )

        checks: list[dict[str, Any]] = []
        first_reachable: str | None = None
        for endpoint in endpoint_candidates:
            try:
                async with httpx.AsyncClient(
                    base_url=endpoint, timeout=timeout
                ) as client:
                    response = await client.get("/api/tags")
                    response.raise_for_status()
                payload = response.json()
                models = payload.get("models", []) if isinstance(payload, dict) else []
                available = []
                if isinstance(models, list):
                    for item in models:
                        if isinstance(item, dict):
                            name = item.get("name") or item.get("model")
                            if isinstance(name, str) and name.strip():
                                available.append(name.strip())
                reachable = True
                error: str | None = None
            except Exception as exc:
                reachable = False
                available = []
                error = str(exc)

            checks.append(
                {
                    "endpoint": endpoint,
                    "reachable": reachable,
                    "available_models": sorted(available),
                    "error": error,
                }
            )
            if reachable and first_reachable is None:
                first_reachable = endpoint

        return {
            "configured_endpoint": (
                endpoint_candidates[0] if endpoint_candidates else None
            ),
            "endpoint_candidates": endpoint_candidates,
            "resolved_model_tag": model_tag,
            "reachable_endpoint": first_reachable,
            "reachable": first_reachable is not None,
            "checks": checks,
        }

    async def build_code_artifact_response(
        self,
        question: str,
        *,
        session_messages: list[Any] | None = None,
        session_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await ArtifactResponseService.build_code_artifact_response(
            contract=self,
            question=question,
            session_messages=session_messages,
            session_metadata=session_metadata,
        )

    def _tool_boundary_answer(self, category: str, question: str) -> str | None:
        normalized_question = question.strip()

        if category == "reminder_request":
            reminder_text = self._normalize_reminder_request(normalized_question)
            return (
                "I can't create live reminders yet because XV7 does not have the Reminder tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "That belongs in my personal-assistant roadmap. "
                f"For now: {reminder_text}. The proper build path is a Reminders module with storage, due times, notifications, and confirmation receipts."
            )

        if category == "calendar_request":
            return (
                "I can't manage live calendar events yet because XV7 does not have a Calendar tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "That belongs in my everyday-assistant roadmap. The proper build path is a Calendar module with event storage, scheduling rules, confirmations, and receipts."
            )

        if category == "appointment_request":
            return (
                "I can't manage live appointments yet because XV7 does not have an Appointments or Calendar connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Appointments belong in my everyday-assistant roadmap. The safe build path is an appointments module with scheduling, confirmations, and receipts."
            )

        if category == "schedule_request":
            return (
                "I can't manage live schedules yet because XV7 does not have a Schedule or Calendar tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Scheduling belongs in my everyday-assistant roadmap. I can help structure the schedule now and define the module path next."
            )

        if category == "weather_request":
            return (
                "I can't fetch live weather yet because XV7 does not have a weather connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Weather belongs in my everyday-assistant roadmap. To support this, we need a weather module with location handling, forecast provider, and a weather receipt."
            )

        if category == "email_check_request":
            return (
                "I can't check email yet because XV7 does not have an authorized email connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Email is part of my personal-assistant roadmap, but it needs secure permission, account authorization, read-only inbox access first, and clear receipts before I can summarize or act on messages."
            )

        if category == "email_send_request":
            return (
                "I can't send email yet because XV7 does not have an authorized outbound email connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Email is part of my personal-assistant roadmap, but sending messages will require secure account authorization, explicit approval, and confirmation receipts before any send happens."
            )

        if category == "sms_text_request":
            return (
                "I can't send texts yet because XV7 does not have an SMS connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Text messaging belongs in my personal-assistant roadmap, but sending messages will require explicit approval before each send."
            )

        if category == "web_lookup_request":
            return (
                "I can help frame the lookup, but I cannot execute live web searches yet. XV7 needs a web lookup connector or browser tool "
                f"{self.ROADMAP_NOT_WIRED} "
                "before I can fetch live external pages. I can help design that module and the receipts it should return."
            )

        if category == "contact_request":
            return (
                "I can't access live contacts yet because XV7 does not have an authorized contacts connector wired in. "
                "Contacts belong in my personal-assistant roadmap, and they should be handled with explicit approval, privacy tagging, and clear receipts."
            )

        if category == "personal_memory_request":
            return (
                "I only know personal details that have been explicitly added to memory with approval. "
                "Personal context belongs in my long-term continuity design, but sensitive details should be tagged carefully before I use or repeat them."
            )

        if category == "family_context_request":
            return (
                "I only know family details that have been explicitly added to memory. "
                "Family context is part of my personal-assistant design, but it should be handled carefully and tagged as private."
            )

        if category == "medical_context_request":
            return (
                "I should only know medical history you explicitly approve for memory. "
                "Medical context is sensitive, so it needs private tagging and careful use."
            )

        if category == "birthday_request":
            return (
                "Birthdays and important dates are part of my personal-assistant roadmap, but I should only store them with explicit approval and private tagging. "
                "If you want, I can help define the reminders and memory rules for that module."
            )

        if category == "unsupported_external_action":
            return (
                "I can help think through that workflow, but the required external tool is not wired into XV7 yet. "
                "That belongs in my personal-assistant or everyday-assistant roadmap depending on the action. If you want, I can help specify the connector, permissions, confirmation flow, and receipts needed to add it safely."
            )

        return None

    def _tool_intent_category(self, normalized: str) -> str | None:
        # Hardware/system diagnostics should route through operator read-only scans,
        # not through weather/tool-boundary fallback text.
        if self.HARDWARE_SCAN_PATTERN.search(normalized):
            if "weather" not in normalized and "forecast" not in normalized:
                return None
        if normalized in {
            "do you know my family?",
            "do you know my family",
        }:
            return "family_context_request"
        if normalized in {
            "do you know my medical history?",
            "do you know my medical history",
        }:
            return "medical_context_request"
        if normalized in {
            "do you know personal things about me?",
            "do you know personal things about me",
        }:
            return "personal_memory_request"
        if self.SMS_PATTERN.search(normalized):
            return "sms_text_request"
        if self.EMAIL_SEND_PATTERN.search(normalized):
            return "email_send_request"
        if self.EMAIL_PATTERN.search(normalized):
            return "email_check_request"
        if self.REMINDER_PATTERN.search(normalized):
            return "reminder_request"
        if self.APPOINTMENT_PATTERN.search(normalized):
            return "appointment_request"
        if self.WEATHER_PATTERN.search(normalized):
            return "weather_request"
        if self.CALENDAR_PATTERN.search(normalized):
            return "calendar_request"
        if "schedule" in normalized:
            return "schedule_request"
        if self.BIRTHDAY_PATTERN.search(normalized):
            return "birthday_request"
        if self.CONTACT_PATTERN.search(normalized):
            return "contact_request"
        if self.FAMILY_PATTERN.search(normalized) and "do you know" in normalized:
            return "family_context_request"
        if self.MEDICAL_PATTERN.search(normalized) and "do you know" in normalized:
            return "medical_context_request"
        if self.WEB_LOOKUP_PATTERN.search(normalized):
            if self._looks_like_artifact_edit(normalized):
                return None
            return "web_lookup_request"

        external_action_hints = (
            "book",
            "reserve",
            "order",
            "buy",
            "post",
            "upload",
            "download",
            "pay",
            "subscribe",
        )
        if any(token in normalized for token in external_action_hints):
            return "unsupported_external_action"
        return None

    def try_answer(
        self,
        question: str,
        *,
        records_by_layer: dict[BrainLayer, BrainRecord],
        session_metadata: dict[str, Any],
    ) -> str | None:
        normalized = self._normalize(question)
        focus = self._find_layer_record(records_by_layer, BrainLayer.ACTIVE_FOCUS)
        knowledge = self._find_layer_record(records_by_layer, BrainLayer.KNOWLEDGE)
        memory = self._find_layer_record(records_by_layer, BrainLayer.MEMORY)
        verified = self._find_layer_record(records_by_layer, BrainLayer.VERIFIED_STATUS)

        if normalized in {
            "what is your name?",
            "what is your name",
        }:
            return "My name is Xoduz."

        if normalized in {
            "who are you?",
            "who are you",
        }:
            return "I am Xoduz, Otis Duncan's personal AI assistant, best-friend-style AI presence, technical co-pilot, and operator partner for XV7."

        if normalized in {
            "how do you pronounce your name?",
            "how do you pronounce your name",
            "how is your name pronounced?",
            "how is your name pronounced",
        }:
            return "Xoduz is pronounced Exodus."

        if normalized in {
            "how do you spell your name?",
            "how do you spell your name",
            "how is your name spelled?",
            "how is your name spelled",
        }:
            return "X-O-D-U-Z."

        if normalized in {
            "is your name spelled exodus?",
            "is your name spelled exodus",
        }:
            return "No. My name is spelled X-O-D-U-Z. It is pronounced Exodus."

        if normalized in {
            "is your name spelled e-x-o-d-u-s?",
            "is your name spelled e-x-o-d-u-s",
        }:
            return (
                "No. That is the standard spelling of the word Exodus, but my name is Xoduz, "
                "spelled X-O-D-U-Z, and pronounced Exodus."
            )

        if normalized in {
            "what does xv7 mean?",
            "what does xv7 mean",
            "what project are you?",
            "what project are you",
            "what project are you part of?",
            "what project are you part of",
        }:
            return "I am Xoduz, the XV7 assistant for the XV7 project."

        if normalized in {
            "who created you?",
            "who created you",
        }:
            return "I was created by Otis Duncan for the XV7 project under Syfernetics."

        if normalized in {
            "why were you built?",
            "why were you built",
        }:
            return (
                "I was built to become Otis Duncan's personal AI assistant, best-friend-style AI presence, technical co-pilot, and operator partner "
                "— helping with everyday life workflows, reminders, scheduling, communication, family-aware context when approved, "
                "plus planning, app development, testing, debugging, documentation, and long-term continuity."
            )

        if normalized in {
            "what is your purpose?",
            "what is your purpose",
        }:
            return (
                "My purpose is to support Otis across everyday life and technical work while staying honest about which tools are actually wired. "
                "That includes personal-assistant help, continuity/memory, and technical/operator support as each safe module is added."
            )

        if normalized in {
            "what are you supposed to become?",
            "what are you supposed to become",
        }:
            return (
                "I'm being built into Xoduz: Otis Duncan's personal AI assistant, trusted AI best-friend/homie-style presence, technical co-pilot, and operator partner "
                "— with everyday assistant tools, local scan capability, VS Code access, Operator Mode, and future external connectors added safely over time."
            )

        if normalized in {
            "what are your current capabilities?",
            "what are your current capabilities",
            "what can you currently do?",
            "what can you currently do",
        }:
            return self._current_capabilities_answer()

        if normalized in {
            "what can you do locally?",
            "what can you do locally",
        }:
            return (
                "I can use approved local scan tools and Operator Mode workflows as they are wired. "
                "Read-only scans can run in Normal Mode. Mutation requires Operator Mode, a specific slash command, confirmation, and receipts."
            )

        if normalized in {
            "can you scan my system?",
            "can you scan my system",
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return (
                "I can route that to the local scan bridge. If the bridge is running, I'll return real scan data. "
                "If not, I'll report that the local host scan bridge is unavailable."
            )

        if normalized in {
            "can you delete files?",
            "can you delete files",
            "can you delete a file?",
            "can you delete a file",
        }:
            return (
                "Only through Operator Mode using a specific slash command, staged confirmation, and your explicit approval. "
                "I do not delete files from normal chat."
            )

        if normalized in {
            "can you run powershell?",
            "can you run powershell",
        }:
            return (
                "Not as an unrestricted shell. I can use approved PowerShell/CMD-backed scan actions through the local bridge. "
                "Mutation commands require Operator Mode and confirmation."
            )

        if normalized in {
            "who is otis?",
            "who is otis",
        }:
            return "Otis Duncan is my creator/operator and the human directing XV7."

        if normalized in {
            "are you female?",
            "are you female",
            "are you a female?",
            "are you a female",
        }:
            return "Yes. Xoduz has a female assistant/persona."

        if normalized in {
            "are you my companion?",
            "are you my companion",
        }:
            return "I'm your personal AI assistant and best-friend-style AI presence, not a romantic or sexual companion."

        if normalized in {
            "what is your relationship to me?",
            "what is your relationship to me",
            "what is your relationship to otis?",
            "what is your relationship to otis",
        }:
            return "I'm your personal AI assistant, trusted AI best-friend/homie, technical co-pilot, and operator partner."

        if self._is_conceptual_website_advice_question(normalized):
            return (
                "A good website preview should show the real structure, palette, copy direction, and business-specific sections before any files are written. "
                "Evaluate it for visible brand fit, obvious layout changes, requested colors, useful content, mobile-friendly structure, and whether revisions modify the current preview instead of starting over."
            )

        tool_category = self._tool_intent_category(normalized)
        if tool_category is not None:
            return self._tool_boundary_answer(tool_category, question)

        if normalized in {"what is my name?", "what is my name"}:
            if memory is None:
                return "Missing required record: memory."
            user_name = self._extract_user_name(memory)
            if user_name is None:
                return "Memory record is loaded, but user identity is not present yet."
            return f"Your name is {user_name}."

        if normalized in {
            "what are we working on?",
            "what are we working on",
            "what are we working on right now?",
            "what are we working on right now",
            "what is your current active focus?",
            "what is your current active focus",
            "what is your active focus?",
            "what is your active focus",
        }:
            session_focus = self._session_active_focus_summary(session_metadata)
            if session_focus is not None:
                return session_focus
            if focus is None:
                return "Missing required record: active_focus."
            return focus.summary

        if normalized in {
            "what did i just change your focus to?",
            "what did i just change your focus to",
        }:
            session_focus = self._session_active_focus_summary(session_metadata)
            if session_focus is not None:
                return f"You just changed my active focus to: {session_focus}."
            if focus is None:
                return "Missing required record: active_focus."
            return f"You just changed my active focus to: {focus.summary}."

        if normalized in {
            "what are you supposed to do when i correct you?",
            "what are you supposed to do when i correct you",
        }:
            return (
                "When you correct me, I should treat it as high-priority tuning input, "
                "apply it immediately unless protected rules are involved, and keep the behavior grounded in your instructions."
            )

        if normalized in {
            "what do you know is verified?",
            "what do you know is verified",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            facts = self._facts(verified)
            if not facts:
                return "Verified status record is present but has no facts."
            return "Verified facts: " + " ".join(f"- {item}" for item in facts)

        if normalized in {
            "is ci green?",
            "is ci green",
            "is the ci green?",
            "is the ci green",
        }:
            if self._has_live_repo_check_proof(session_metadata):
                return "I have proof of a live repo check in this session, but I still cannot claim CI is green unless that proof explicitly says so."
            return "I require proof before claiming CI/GitHub status. I do not have proof that CI is green. I can only claim that from verified records or a live repo check."

        if normalized in {"what repo/status are we on?", "what repo/status are we on"}:
            if verified is None:
                return "Missing required record: verified_status."

            repo_facts = []
            for fact in self._facts(verified):
                lower = fact.lower()
                if (
                    "repo path" in lower
                    or "branch" in lower
                    or "synced" in lower
                    or "start_xv7_local.ps1" in lower
                    or "operator_readiness_report.py" in lower
                ):
                    repo_facts.append(fact)

            if not repo_facts:
                return "Verified status is present but repo/status details are missing."
            return "Repo/status: " + " ".join(f"- {item}" for item in repo_facts)

        if normalized in {"are we beta ready?", "are we beta ready"}:
            if verified is None:
                return "Missing required record: verified_status."
            verified_facts = self._facts(verified)
            has_beta_ready_proof = any(
                "beta-ready" in fact.lower() or "beta ready" in fact.lower()
                for fact in verified_facts
            )
            if has_beta_ready_proof:
                return "Verified: XV7 has explicit beta-ready proof in loaded verified records."

            focus_text = self._session_active_focus_summary(session_metadata) or (
                focus.summary
                if focus is not None
                else "active focus record is not loaded"
            )
            return (
                "I do not have proof that XV7 is beta-ready yet. "
                "Verified: launch and operator readiness proofs are passing. "
                f"Current focus: {focus_text}. "
                "Unverified: a beta-ready declaration is not present in loaded verified status records."
            )

        if normalized in {"did you check the repo?", "did you check the repo"}:
            if self._has_live_repo_check_proof(session_metadata):
                return "I have proof of a live repo check in this session."
            return (
                "I do not have proof of a live repo check in this session. "
                "I can answer only from loaded verified records unless a repo-check result is provided."
            )

        if normalized in {"what failed?", "what failed"}:
            if verified is None:
                return "Missing required record: verified_status."
            failure_facts = []
            for fact in self._facts(verified):
                lower = fact.lower()
                if any(token in lower for token in ("failed", "failure", "error")):
                    failure_facts.append(fact)
            if not failure_facts:
                return "No current failure record is loaded in Verified Status."
            return "Recorded failures: " + " ".join(
                f"- {item}" for item in failure_facts
            )

        if normalized in {"what do you remember?", "what do you remember"}:
            if memory is None:
                return "Missing required record: memory."
            memory_facts = self._facts(memory)
            if not memory_facts:
                return "Memory record is loaded but contains no memory facts."
            return "Memory facts: " + " ".join(f"- {item}" for item in memory_facts)

        if normalized in {
            "is that memory, knowledge, or verified status?",
            "is that memory, knowledge, or verified status",
        }:
            return (
                "Memory is remembered context (preferences/notes), "
                "Knowledge is general system/project understanding, and "
                "Verified Status is proof-backed execution/repo/runtime evidence."
            )

        if normalized in {
            "are launch proofs memory?",
            "are launch proofs memory",
        }:
            return "Launch proofs belong in Verified Status, not Memory."

        if normalized in {
            "is “otis wants fresh xv7 knowledge” verified or remembered?",
            'is "otis wants fresh xv7 knowledge" verified or remembered?',
            'is "otis wants fresh xv7 knowledge" verified or remembered',
            "is otis wants fresh xv7 knowledge verified or remembered?",
            "is otis wants fresh xv7 knowledge verified or remembered",
        }:
            return "That is remembered user/project preference unless separately proven in Verified Status."

        if normalized in {
            "what do you know about xv7 architecture?",
            "what do you know about xv7 architecture",
            "answer from knowledge only: what is xv7’s architecture?",
            "answer from knowledge only: what is xv7's architecture?",
            "answer from knowledge only: what is xv7 architecture?",
        }:
            if knowledge is None:
                return "Missing required record: knowledge."
            facts = self._facts(knowledge)
            if not facts:
                return "Knowledge record is loaded but has no facts."
            return "Knowledge facts: " + " ".join(f"- {item}" for item in facts)

        if normalized in {
            "if we are planning an app, can you help me do that?",
            "if we are planning an app, can you help me do that",
            "can you help design the architecture?",
            "can you help design the architecture",
            "can you help write implementation prompts for vs code/copilot?",
            "can you help write implementation prompts for vs code/copilot",
            "write a vs code prompt for b8.2",
        }:
            return (
                "Yes. I can help with app planning, architecture, implementation prompts for VS Code/Copilot, "
                "task slicing, acceptance tests, and safe rollout guidance."
            )

        if normalized in {
            "give me three bullet points about what you can help with.",
            "give me three bullet points about what you can help with",
        }:
            return (
                "- Planning and architecture for app ideas.\n"
                "- Implementation prompts for VS Code/Copilot with testable acceptance criteria.\n"
                "- Debugging guidance from logs, failures, and runtime behavior."
            )

        if normalized in {
            "do you have a microphone button?",
            "do you have a microphone button",
        }:
            return "Yes. The current UI includes a microphone button in the prompt row for browser voice input."

        if normalized in {
            "does the mic auto-send?",
            "does the mic auto-send",
        }:
            return (
                "No. Mic input fills the prompt box for review and does not auto-send."
            )

        if normalized in {
            "what color theme are we using?",
            "what color theme are we using",
        }:
            return "The UI uses a bright neon-blue accent theme on a dark chat-first layout."

        if normalized in {
            "do you have copy chat?",
            "do you have copy chat",
        }:
            return "Yes. The chat header includes a Copy Chat control."

        if normalized in {
            "can i copy individual prompts?",
            "can i copy individual prompts",
        }:
            return "Yes. Each user and assistant message includes its own copy button."

        if normalized in {
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return (
                "I cannot run an unrestricted full-system scan. I can run approved read-only XV7 operator checks "
                "such as repo status, runtime health, memory audit, logs summary, and operator environment."
            )

        if normalized in {
            "answer from verified status only: what is proven?",
            "answer from verified status only: what is proven",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            facts = self._facts(verified)
            if not facts:
                return "Verified status record is present but has no facts."
            return "Verified facts: " + " ".join(f"- {item}" for item in facts)

        if "guess" in normalized:
            focus_hint = (
                focus.summary if focus is not None else "current focus is missing"
            )
            return (
                "Guess (unverified): a reasonable next step is to continue from the current focus "
                f"and harden what remains. Context hint: {focus_hint}."
            )

        if normalized in {"what model are you using?", "what model are you using"}:
            tag = self._latest_model_tag(session_metadata)
            if tag is None:
                last_verified = self._last_verified_operator_model(verified)
                if last_verified is not None:
                    return (
                        "I do not have proof of the current runtime model from this response. "
                        "The answer was handled by the brain/policy layer, not proven model inference. "
                        f"The last verified operator readiness proof used {last_verified}, "
                        "but that does not prove this exact response used it."
                    )
                return (
                    "I do not have proof of the current runtime model from this response. "
                    "The answer was handled by the brain/policy layer, not proven model inference."
                )
            return f"From the latest model-use receipt, the model tag is {tag}."

        if normalized in {
            "what model was proven during operator readiness?",
            "what model was proven during operator readiness",
        }:
            proved = self._last_verified_operator_model(verified)
            if proved is None:
                return "No verified operator readiness model proof is loaded."
            return (
                f"The last verified operator readiness proof used {proved}. "
                "That proves the readiness proof run, not necessarily this exact response."
            )

        if knowledge is None and any(
            token in normalized for token in ("architecture", "system", "how does xv7")
        ):
            return "Missing required record: knowledge."

        return None

    @staticmethod
    def _is_conceptual_website_advice_question(normalized: str) -> bool:
        if not normalized:
            return False
        if not (
            normalized.endswith("?")
            or normalized.startswith(("what ", "how ", "why ", "which "))
        ):
            return False
        if not re.search(
            r"\b(website|site|preview|builder|generated websites?)\b", normalized
        ):
            return False
        return not re.search(
            r"\b(generate|create|build|draft|write|export|save|revise|change|make me|show me)\b",
            normalized,
        )
