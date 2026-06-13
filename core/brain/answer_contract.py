from __future__ import annotations

import os
import html
import re
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from core.brain import site_bundle as sb
from core.brain.artifact_fidelity_manager import ArtifactFidelityManager
from core.brain.artifact_history_manager import ArtifactHistoryManager
from core.brain.code_artifact_builder import CodeArtifactBuilder
from core.brain.commit_proposal_manager import CommitProposalManager
from core.brain.intent_router import IntentRouter
from core.brain.patch_proposal_manager import PatchProposalManager
from core.brain.repo_safety_policy import RepoSafetyPolicy
from core.brain.sandbox_writer import SandboxWriteManager
from core.brain.schema import BrainLayer, BrainRecord
from core.brain.session_signal_manager import SessionSignalManager
from core.brain.website_build_plan_manager import (
    BundlePlan as WebsiteBuildBundlePlan,
    CallsToActionPlan as WebsiteBuildCallsToActionPlan,
    ContactPlan as WebsiteBuildContactPlan,
    ContentBlockPlan as WebsiteBuildContentBlockPlan,
    ContentBlockPlanItem as WebsiteBuildContentBlockPlanItem,
    PageRoute as WebsiteBuildPageRoute,
    SeoPlan as WebsiteBuildSeoPlan,
    StylePlan as WebsiteBuildStylePlan,
    WebsiteBuildPlanManager,
)
from core.brain.website_bundle_assembly_manager import WebsiteBundleAssemblyManager
from core.brain.website_contact_plan_manager import WebsiteContactPlanManager
from core.brain.website_content_block_plan_manager import (
    WebsiteContentBlockPlanManager,
)
from core.brain.website_cta_plan_manager import WebsiteCallToActionManager
from core.brain.website_page_plan_manager import WebsitePagePlanManager
from core.brain.website_project_name_manager import WebsiteProjectNameManager
from core.brain.website_section_plan_manager import WebsiteSectionPlanManager
from core.brain.website_seo_plan_manager import WebsiteSeoPlanManager
from core.brain.website_style_plan_manager import WebsiteStylePlanManager
from core.brain.visible_response_plan_manager import VisibleResponsePlanManager
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
    WEBSITE_BUILD_ARTIFACT_PATTERN = re.compile(
        r"\b(build|create|make|generate|draft)\b.*\b(website|site)\b.*\bfor\b"
    )
    EXPLICIT_ARTIFACT_INTENT_PATTERN = re.compile(
        r"\b(html artifact|code artifact|draft html|inline html|single-file html|single file html|"
        r"one-page html artifact|one page html artifact|generate html artifact|create html artifact|artifact)\b"
    )
    PREVIEW_ARTIFACT_PATTERN = re.compile(
        r"\b(preview|show|render|display|mock\s*up|mockup)\b"
    )
    SANDBOX_BUILD_ACTION_PATTERN = re.compile(
        r"\b(build|write|create|scaffold)\b|\bmake\s+(?:a\s+)?project\b|\bgenerate\s+files\b|\bwrite\s+files\b"
    )
    SANDBOX_BUILD_TARGET_PATTERN = re.compile(
        r"\b(website|site|page|design|project|app|files|react|vite|frontend|landing page|web page|homepage)\b"
    )
    ARTIFACT_REPO_MUTATION_PATTERN = re.compile(
        r"\b(create a website in the repo|make the app|implement this feature|"
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
        r"\b(change|make|update|revise|edit|adjust|tweak|restyle|refresh|rewrite|switch|set|use|improve|redesign|move|keep|preserve|undo|revert|summarize|add)\b"
    )
    ARTIFACT_EDIT_TARGET_PATTERN = re.compile(
        r"\b(website|site|artifact|page|pages|font|text|headline|button|buttons|copy|wording|color|colors|palette|theme|style|css|html|javascript|js|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|preview|code|hero|cta|section|layout|spacing|background|read|smaller|bigger|home\s?page|homepage|specials?)\b"
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
        r"\b(color|colors|palette|background|font|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|easier to read|black|gold|white)\b"
    )
    ARTIFACT_CONTENT_PATTERN = re.compile(
        r"\b(headline|cta|button text|buttons|copy|wording|services section|specials section|specials page|main headline|rewrite|rewrite the homepage|rewrite homepage|say)\b"
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
        r"save\s+the\s+patch\s+to\s+the\s+repo|apply\s+patch)\b"
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
    ARTIFACT_SANDBOX_LOCATION_PATTERN = re.compile(
        r"\b(show me where the files went|where did the files go|where are the files|where are the sandbox files|"
        r"where was it saved|where did it save|what is the sandbox path|show me the sandbox path|show me the file path|"
        r"where are the generated files|where did the site go|show me where it was written|where were the files written)\b"
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
        r"\b(look up|lookup|search|find|browse|official website)\b"
    )
    CALENDAR_PATTERN = re.compile(r"\b(calendar|schedule|meeting|appointment|event)\b")
    APPOINTMENT_PATTERN = re.compile(
        r"\b(appointment|meeting|event|doctor visit|doctor appointment)\b"
    )

    @staticmethod
    def _normalize(text: str) -> str:
        return IntentRouter.normalize(text)

    @staticmethod
    def _find_layer_record(
        records_by_layer: dict[BrainLayer, BrainRecord], layer: BrainLayer
    ) -> BrainRecord | None:
        return records_by_layer.get(layer)

    @staticmethod
    def _facts(record: BrainRecord | None) -> list[str]:
        return SessionSignalManager.facts(record)

    @staticmethod
    def _extract_user_name(record: BrainRecord | None) -> str | None:
        return SessionSignalManager.extract_user_name(record)

    @staticmethod
    def _session_active_focus_summary(session_metadata: dict[str, Any]) -> str | None:
        return SessionSignalManager.active_focus_summary(session_metadata)

    @staticmethod
    def _normalize_reminder_request(question: str) -> str:
        return SessionSignalManager.normalize_reminder_request(question)

    @staticmethod
    def _has_live_repo_check_proof(session_metadata: dict[str, Any]) -> bool:
        return SessionSignalManager.has_live_repo_check_proof(session_metadata)

    @staticmethod
    def _latest_model_tag(session_metadata: dict[str, Any]) -> str | None:
        return SessionSignalManager.latest_model_tag(session_metadata)

    @staticmethod
    def _last_verified_operator_model(record: BrainRecord | None) -> str | None:
        return SessionSignalManager.last_verified_operator_model(record)

    @staticmethod
    def is_code_artifact_request(normalized_question: str) -> bool:
        return IntentRouter.is_code_artifact_request(normalized_question)

    @staticmethod
    def _code_artifact_language(normalized_question: str) -> str:
        return CodeArtifactBuilder.code_artifact_language(normalized_question)

    @staticmethod
    def _code_artifact_filename(language: str) -> str:
        return CodeArtifactBuilder.code_artifact_filename(language)

    @staticmethod
    def _clean_artifact_label(text: str) -> str:
        return CodeArtifactBuilder.clean_artifact_label(text)

    @classmethod
    def _extract_artifact_name(cls, question: str) -> str | None:
        return CodeArtifactBuilder.extract_artifact_name(question)

    @staticmethod
    def _artifact_business_category(question: str, name: str | None) -> str:
        return CodeArtifactBuilder.artifact_business_category(question, name)

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

    @staticmethod
    def _extract_requested_filename(question: str, language: str) -> str:
        return CodeArtifactBuilder.extract_requested_filename(question, language)

    @staticmethod
    def _extract_requested_previewable(question: str, language: str) -> bool:
        return CodeArtifactBuilder.extract_requested_previewable(question, language)

    @staticmethod
    def _extract_apply_intent(question: str) -> bool:
        return CodeArtifactBuilder.extract_apply_intent(question)

    @staticmethod
    def _extract_style_hints(question: str) -> dict[str, list[str]]:
        return CodeArtifactBuilder.extract_style_hints(question)

    @staticmethod
    def _extract_layout_hints(question: str) -> list[str]:
        return CodeArtifactBuilder.extract_layout_hints(question)

    @staticmethod
    def _artifact_intent_label(question: str) -> str:
        return CodeArtifactBuilder.artifact_intent_label(question)

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
        return ArtifactHistoryManager.extract_business_name_from_html(content)

    @staticmethod
    def _extract_artifact_from_metadata(
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        return ArtifactHistoryManager.extract_artifact_from_metadata(metadata)

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
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "artifact"

    @classmethod
    def _is_patch_proposal_request(cls, normalized_question: str) -> bool:
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
    def _is_sandbox_location_query(cls, normalized_question: str) -> bool:
        return bool(cls.ARTIFACT_SANDBOX_LOCATION_PATTERN.search(normalized_question))

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
    def _is_repo_mutation_build_prompt(cls, normalized_question: str) -> bool:
        return IntentRouter.is_repo_mutation_build_prompt(normalized_question)

    @classmethod
    def _prioritize_artifact_over_build_guard(cls, normalized_question: str) -> bool:
        return IntentRouter.prioritize_artifact_over_build_guard(normalized_question)

    @staticmethod
    def _workspace_root() -> Path:
        return RepoSafetyPolicy.workspace_root()

    @staticmethod
    def _sandbox_root() -> Path:
        return SandboxWriteManager.sandbox_root()

    @classmethod
    def _safe_slug(cls, raw: str | None, fallback: str) -> str:
        return WebsiteProjectNameManager.safe_folder_name(raw, fallback=fallback)

    @staticmethod
    def _sanitize_filename(filename: str, language: str) -> str:
        return SandboxWriteManager.sanitize_filename(filename, language)

    @staticmethod
    def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                text=True,
                capture_output=True,
                check=False,
                timeout=8,
            )
        except FileNotFoundError:
            return subprocess.CompletedProcess(
                args=["git", *args],
                returncode=127,
                stdout="",
                stderr="git executable not found",
            )
        except subprocess.TimeoutExpired:
            command = "git " + " ".join(args)
            return subprocess.CompletedProcess(
                args=["git", *args],
                returncode=124,
                stdout="",
                stderr=f"git command timed out after 8s while running {command}",
            )

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
        return PatchProposalManager.content_sha256(content)

    @staticmethod
    def _utc_now_iso() -> str:
        return PatchProposalManager.utc_now_iso()

    @classmethod
    def _resolve_safe_patch_target(
        cls,
        *,
        root: Path,
        target_path: str,
    ) -> tuple[Path | None, str | None]:
        return RepoSafetyPolicy.resolve_safe_patch_target(
            root=root,
            target_path=target_path,
        )

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
        return PatchProposalManager.applied_patch_with_runtime_fields(
            proposal=proposal,
            verification=verification,
            targeted_validation=targeted_validation,
            preview_path=preview_path,
        )

    @classmethod
    def _build_unified_diff(
        cls,
        *,
        target_path: str,
        before_content: str | None,
        after_content: str,
    ) -> str:
        return PatchProposalManager.build_unified_diff(
            target_path=target_path,
            before_content=before_content,
            after_content=after_content,
        )

    @classmethod
    def _extract_patch_proposal_from_metadata(
        cls, metadata: dict[str, Any]
    ) -> dict[str, Any] | None:
        return PatchProposalManager.extract_patch_proposal_from_metadata(metadata)

    # site_bundle session helpers are delegated to the sb module.

    @classmethod
    def _latest_pending_patch_proposal(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return PatchProposalManager.latest_pending_patch_proposal(
            session_messages,
            session_metadata,
        )

    @classmethod
    def _latest_applied_patch_proposal(
        cls,
        session_messages: list[Any] | None,
        session_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return PatchProposalManager.latest_applied_patch_proposal(
            session_messages,
            session_metadata,
        )

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
            return CommitProposalManager.build_no_git_proposal(
                question=question,
                proposal_id=proposal_id,
            )

        status_proc = cls._run_git(
            root, ["status", "--porcelain", "--untracked-files=all"]
        )
        diff_stat_proc = cls._run_git(root, ["diff", "--stat"])

        return CommitProposalManager.build_status_scan_proposal(
            question=question,
            branch=branch,
            status_output=status_proc.stdout,
            diff_stat=(
                diff_stat_proc.stdout.strip() if diff_stat_proc.returncode == 0 else ""
            ),
            proposal_id=proposal_id,
            is_blocked=cls._is_blocked_commit_target,
        )

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
        proposal = PatchProposalManager.build_patch_proposal_payload(
            question="",
            target_path=target_path,
            content=current_content,
            language=language,
            source_artifact_id=source_artifact_id,
            before_content=existing_content,
            proposal_id=f"patch-{uuid4().hex[:12]}",
            validation={
                "status": validation_status,
                "checks": checks,
                "failures": failures,
            },
        )
        proposal.pop("question", None)
        proposal.pop("content_length", None)
        proposal.pop("content_sha256", None)
        proposal["filename"] = filename
        return proposal

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
        return ArtifactFidelityManager.replace_first_tag_text(
            content,
            tag,
            replacement,
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

        wants_specials = bool(
            re.search(r"\b(add\s+)?specials?\b", normalized)
            or "specials section" in normalized
            or "specials page" in normalized
        )
        if wants_specials and "xv7-specials" not in revised.lower():
            specials_style = (
                '<style id="xv7-specials-revision">'
                ".xv7-specials{margin-top:1.25rem;padding:1rem;border-radius:12px;"
                "border:1px solid color-mix(in srgb,var(--accent, #f59e0b) 45%, transparent);"
                "background:color-mix(in srgb,var(--panel, rgba(0,0,0,0.2)) 88%, transparent);}"
                ".xv7-specials h2{margin:0 0 .5rem;}"
                "</style>"
            )
            revised = cls._insert_before_tag(revised, "head", specials_style)
            specials_markup = (
                '<section class="xv7-specials" aria-label="Specials">'
                "<h2>Specials</h2>"
                '<p class="muted">Limited-time cart favorites and combo deals available this week.</p>'
                "<ul><li>Classic Dog Combo</li><li>Loaded Chili Dog Special</li><li>Family Pack Deal</li></ul>"
                "</section>"
            )
            if re.search(r"</main>", revised, flags=re.IGNORECASE):
                revised = re.sub(
                    r"</main>",
                    specials_markup + "</main>",
                    revised,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                revised = cls._insert_before_tag(revised, "body", specials_markup)

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
        normalized = self._normalize(question)
        artifact_history = self._artifact_history(
            session_messages,
            session_metadata,
        )
        latest_artifact = artifact_history[-1]["artifact"] if artifact_history else None
        source_artifact_label = (
            "latest session artifact" if latest_artifact is not None else None
        )

        # ─── Sandbox location fast-path ─────────────────────────────────────────────
        if self._is_sandbox_location_query(normalized):
            if latest_artifact is not None:
                sandbox_project_path = str(
                    latest_artifact.get("sandbox_project_path") or ""
                ).strip()
                sandbox_written_paths: list[str] = [
                    str(p)
                    for p in (latest_artifact.get("sandbox_written_paths") or [])
                    if str(p).strip()
                ]
                if sandbox_project_path:
                    file_lines = (
                        "\n".join(f"  - {p}" for p in sandbox_written_paths[:8])
                        if sandbox_written_paths
                        else "  (paths not recorded)"
                    )
                    return {
                        "visible_text": (
                            f"The sandbox files are in: {sandbox_project_path}\n\n"
                            f"Written files:\n{file_lines}"
                        ),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-location",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "sandbox_location_query",
                            "sandbox_project_path": sandbox_project_path,
                            "sandbox_written_paths": sandbox_written_paths,
                        },
                    }
            return {
                "visible_text": "The last artifact was delivered as a chat preview. No sandbox files were written.",
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-location",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "sandbox_location_query",
                    "delivery_mode": "chat_artifact",
                },
            }

        is_generation = self.is_code_artifact_request(normalized)
        is_site_bundle_generation = sb.is_site_bundle_request(normalized)
        is_sandbox_build_request = self._is_sandbox_build_request(normalized)
        has_artifact_edit_intent = self._looks_like_artifact_edit(normalized)
        explicit_sandbox_delivery_request = bool(
            re.search(
                r"\b(write|export|save)\b.*\b(sandbox|files?|folder|disk)\b|"
                r"\b(build|generate|create)\b.*\b(to files|as files|file bundle|project files|sandbox)\b",
                normalized,
            )
        )
        is_site_bundle_sandbox_delivery_request = (
            latest_artifact is not None
            and latest_artifact.get("artifact_type") == "site_bundle"
            and explicit_sandbox_delivery_request
        )
        has_explicit_artifact_generation_language = bool(
            self.EXPLICIT_ARTIFACT_INTENT_PATTERN.search(normalized)
        )
        if (
            latest_artifact is not None
            and has_artifact_edit_intent
            and not has_explicit_artifact_generation_language
        ):
            # Active-artifact edit prompts may still mention "html"/"css" but should stay in revision flow.
            is_generation = False
            is_site_bundle_generation = False
        is_patch_proposal_request = self._is_patch_proposal_request(normalized)
        is_patch_apply_request = self._is_patch_apply_request(normalized)
        is_post_apply_verify_request = self._is_post_apply_verify_request(normalized)
        is_post_apply_preview_request = self._is_post_apply_preview_request(normalized)
        is_post_apply_targeted_validation_request = (
            self._is_post_apply_targeted_validation_request(normalized)
        )
        is_post_apply_full_test_guard_request = (
            self._is_post_apply_full_test_guard_request(normalized)
        )
        refinement_mode = (
            self._artifact_refinement_mode(normalized)
            if (not is_patch_proposal_request and has_artifact_edit_intent)
            else None
        )
        is_refinement_request = (
            latest_artifact is not None
            and refinement_mode is not None
            and not self.SMS_EXPLICIT_SEND_PATTERN.search(normalized)
            and not is_generation
            and not is_site_bundle_generation
        ) or is_site_bundle_sandbox_delivery_request
        latest_delivery_mode = (
            str(latest_artifact.get("delivery_mode") or "")
            if isinstance(latest_artifact, dict)
            else ""
        )
        deliver_to_sandbox = is_sandbox_build_request or (
            is_refinement_request and latest_delivery_mode == "sandbox_write"
        )
        site_bundle_deliver_to_sandbox = explicit_sandbox_delivery_request or (
            is_refinement_request and latest_delivery_mode == "sandbox_write"
        )
        is_commit_proposal_request = self._is_commit_proposal_request(normalized)
        is_commit_approval_request = self._is_commit_approval_request(normalized)
        allow_commit_lane = (
            is_commit_proposal_request or is_commit_approval_request
        ) and not (
            is_generation
            or is_site_bundle_generation
            or is_refinement_request
            or self._looks_like_artifact_edit(normalized)
        )

        # ─── Explicit sandbox export of active single-file code artifact ──────────
        # "Write it to the sandbox" / "save to sandbox" with an active code_artifact
        # (not a site_bundle) must write the existing artifact content to the sandbox
        # and return a receipt — it must NOT generate a new draft artifact.
        # Note: extract_artifact_from_metadata normalizes single artifacts with key
        # "type" (not "artifact_type"), while site bundles use "artifact_type".
        _latest_artifact_kind = str(
            (latest_artifact.get("artifact_type") or latest_artifact.get("type") or "")
            if isinstance(latest_artifact, dict)
            else ""
        )
        is_explicit_single_artifact_sandbox_export = (
            explicit_sandbox_delivery_request
            and latest_artifact is not None
            and isinstance(latest_artifact, dict)
            and _latest_artifact_kind == "code_artifact"
            and not is_site_bundle_sandbox_delivery_request
            and not is_generation
            and not is_site_bundle_generation
        )
        if is_explicit_single_artifact_sandbox_export:
            assert isinstance(latest_artifact, dict)
            _filename = str(latest_artifact.get("filename") or "index.html")
            _content = str(latest_artifact.get("content") or "")
            _language = str(latest_artifact.get("language") or "html")
            _artifact_id = str(
                latest_artifact.get("artifact_id")
                or self._slugify_artifact_name(_filename)
                or "artifact-export"
            )
            # Derive project slug from artifact_id (strip "-artifact" suffix if present).
            _export_slug = self._safe_slug(
                _artifact_id.replace("-artifact", ""), fallback="artifact-export"
            )
            if not _content.strip():
                return {
                    "visible_text": "The active artifact has no content to write to sandbox.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-artifact-export",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "sandbox_artifact_export_empty",
                        "delivery_mode": "chat_artifact",
                    },
                }
            _sandbox_relative_path, _sandbox_target_path = self._write_sandbox_file(
                project_slug=_export_slug,
                filename=_filename,
                content=_content,
            )
            _sandbox_root_str = str(self._sandbox_root())
            return {
                "visible_text": (
                    f"Wrote the active artifact to sandbox: {_sandbox_target_path}\n"
                    f"Sandbox root: {_sandbox_root_str}"
                ),
                "code_artifact": {
                    **latest_artifact,
                    "delivery_mode": "sandbox_write",
                    "applied": True,
                    "sandbox_root": _sandbox_root_str,
                    "sandbox_project_slug": _export_slug,
                    "sandbox_relative_path": _sandbox_relative_path,
                    "sandbox_target_path": _sandbox_target_path,
                },
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: sandbox-artifact-export",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "sandbox_artifact_export",
                    "artifact_validation": "passed",
                    "delivery_mode": "sandbox_write",
                    "sandbox_root": _sandbox_root_str,
                    "sandbox_project_slug": _export_slug,
                    "sandbox_relative_path": _sandbox_relative_path,
                    "sandbox_target_path": _sandbox_target_path,
                },
            }

        # ─── Site bundle patch proposal ────────────────────────────────────────────
        if (
            is_patch_proposal_request
            and latest_artifact is not None
            and latest_artifact.get("artifact_type") == "site_bundle"
        ):
            slug = str(latest_artifact.get("slug") or "site-bundle")
            bundle_files_raw = latest_artifact.get("site_bundle") or {}
            bundle_files: list[dict[str, str]] = []
            if isinstance(bundle_files_raw, dict):
                bundle_files = list(bundle_files_raw.get("files") or [])
            if not bundle_files:
                return {
                    "visible_text": "I do not have any files in the active site bundle to patch.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": latest_artifact,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "proposal_unavailable",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "empty_bundle",
                    },
                }
            root = self._workspace_root()
            bundle_proposals = sb.build_patch_proposals(
                bundle_files=bundle_files,
                slug=slug,
                root=root,
                validate_fn=self._validate_patch_proposal,
                diff_fn=self._build_unified_diff,
            )
            all_passed = all(
                p.get("validation", {}).get("status") == "passed"
                for p in bundle_proposals
            )
            return {
                "visible_text": (
                    f"I prepared patch proposals for all {len(bundle_proposals)} file(s) in the site bundle. "
                    'No files were written. Use "apply it" to write them.'
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "site_bundle": latest_artifact,
                "site_bundle_patch_proposals": bundle_proposals,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "bundle_proposed",
                    "applied": False,
                    "requires_confirmation": True,
                    "slug": slug,
                    "file_count": len(bundle_proposals),
                    "all_valid": all_passed,
                    "source_artifact": source_artifact_label
                    or "latest session artifact",
                },
            }

        # ─── Site bundle apply ──────────────────────────────────────────────────────
        if is_patch_apply_request:
            _bundle_proposals_pending = sb.latest_pending_bundle_proposals(
                session_messages, session_metadata
            )
            if _bundle_proposals_pending is not None:
                root = self._workspace_root()
                written, errors = sb.apply_proposals(
                    proposals=_bundle_proposals_pending,
                    root=root,
                    resolve_fn=self._resolve_safe_patch_target,
                )
                latest_bundle_art = sb.latest_bundle_artifact(
                    session_messages, session_metadata
                )
                slug = str((latest_bundle_art or {}).get("slug") or "site-bundle")
                entry = str((latest_bundle_art or {}).get("entry") or "index.html")
                preview_path = f"/generated-sites/{slug}/{entry}"
                applied_bundle_proposals = [
                    {**p, "applied": True, "preview_path": preview_path}
                    for p in _bundle_proposals_pending
                    if p.get("target_path") in written
                ]
                return {
                    "visible_text": (
                        f"Applied {len(written)} file(s) for the site bundle under generated-sites/{slug}/. "
                        + (f"Errors: {'; '.join(errors)}" if errors else "No errors.")
                        + f" Preview entry page at {preview_path}."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": latest_bundle_art or {},
                    "site_bundle_patch_proposals": applied_bundle_proposals,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "bundle_applied",
                        "applied": True,
                        "requires_confirmation": True,
                        "slug": slug,
                        "files_written": written,
                        "errors": errors,
                        "preview_path": preview_path,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

        if is_patch_proposal_request:
            if latest_artifact is None:
                return {
                    "visible_text": "I do not have an active code artifact to turn into a patch yet. Generate or paste an artifact first.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "proposal_unavailable",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_active_artifact",
                    },
                }

            proposal = self._build_patch_proposal_from_artifact(
                artifact=latest_artifact
            )
            validation_raw = proposal.get("validation")
            validation: dict[str, Any] = (
                validation_raw if isinstance(validation_raw, dict) else {}
            )
            validation_status = str(validation.get("status") or "failed")
            return {
                "visible_text": "I prepared a patch proposal from the active artifact. No files were changed.",
                "code_artifact": {},
                "artifact_patch_proposal": proposal,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-proposal",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "proposed",
                    "applied": False,
                    "requires_confirmation": True,
                    "target_path": proposal.get("target_path"),
                    "validation": validation_status,
                    "source_artifact": source_artifact_label
                    or "latest session artifact",
                    "source_artifact_id": proposal.get("source_artifact_id"),
                },
            }

        if is_patch_apply_request:
            pending = self._latest_pending_patch_proposal(
                session_messages, session_metadata
            )
            if pending is None:
                return {
                    "visible_text": "I do not have a pending patch proposal to apply.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_refused",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_pending_patch_proposal",
                    },
                }

            pending_validation_raw = pending.get("validation")
            pending_validation: dict[str, Any] = (
                pending_validation_raw
                if isinstance(pending_validation_raw, dict)
                else {}
            )
            validation_status = str(
                pending_validation.get("status") or "failed"
            ).lower()
            failures_raw = pending_validation.get("failures")
            failures: list[str] = (
                [str(item) for item in failures_raw]
                if isinstance(failures_raw, list)
                else []
            )
            if validation_status != "passed":
                reason = (
                    "; ".join(str(item) for item in failures if str(item).strip())
                    or "validation did not pass"
                )
                return {
                    "visible_text": f"I cannot apply this patch because validation failed: {reason}.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_blocked",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": pending.get("target_path"),
                        "validation": "failed",
                        "failure_reason": reason,
                    },
                }

            target_path = str(pending.get("target_path") or "").replace("\\", "/")
            operation = str(pending.get("operation") or "create")
            content = str(pending.get("content") or "")
            if operation not in {"create", "update"} or not target_path:
                return {
                    "visible_text": "I cannot apply this patch because validation failed: operation/path is not allowed.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_blocked",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "validation": "failed",
                        "failure_reason": "operation_or_target_invalid",
                    },
                }

            root = self._workspace_root()
            target, resolve_error = self._resolve_safe_patch_target(
                root=root, target_path=target_path
            )
            if target is None:
                return {
                    "visible_text": "I cannot apply this patch because validation failed: target path failed safety checks.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_blocked",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "validation": "failed",
                        "failure_reason": resolve_error or "unsafe_target_path",
                    },
                }

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written_content = target.read_text(encoding="utf-8")
            if written_content != content:
                return {
                    "visible_text": "I attempted to apply the patch, but post-write validation failed because the file content does not match the proposal.",
                    "code_artifact": {},
                    "artifact_patch_proposal": pending,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "apply_failed",
                        "applied": False,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "validation": "failed",
                        "failure_reason": "post_write_content_mismatch",
                    },
                }

            preview_path = f"/{target_path}"
            applied_base = {
                **pending,
                "applied": True,
                "applied_at": self._utc_now_iso(),
                "preview_path": preview_path,
            }
            verification = {
                "status": "passed",
                "verified": True,
                "checks": [
                    {
                        "name": "post_write_content_match",
                        "status": "passed",
                        "detail": "written content matches applied proposal",
                    },
                ],
                "failures": [],
                "verified_at": self._utc_now_iso(),
                "content_length": len(content),
                "content_sha256": self._content_sha256(content),
            }
            applied_proposal = self._applied_patch_with_runtime_fields(
                proposal=applied_base,
                verification=verification,
                preview_path=preview_path,
            )
            return {
                "visible_text": (
                    f"Applied the proposed patch to {target_path}. File written locally with operation {operation}. "
                    "No commit was created, no push was performed, and tests were not run."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": applied_proposal,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "applied",
                    "applied": True,
                    "requires_confirmation": True,
                    "target_path": target_path,
                    "operation": operation,
                    "validation": "passed",
                    "commit_created": False,
                    "push_performed": False,
                    "preview_path": preview_path,
                },
            }

        if is_post_apply_full_test_guard_request:
            latest_applied = self._latest_applied_patch_proposal(
                session_messages, session_metadata
            )
            if latest_applied is None:
                return None
            target_path = str((latest_applied or {}).get("target_path") or "")
            return {
                "visible_text": (
                    "I did not run full tests automatically. I can only run the focused checks for the applied file in this lane. "
                    "If you want full-suite validation, ask me explicitly and I will request confirmation before running it."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": latest_applied or {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_patch": "full_test_guard",
                    "applied": bool(latest_applied),
                    "requires_confirmation": True,
                    "target_path": target_path or None,
                    "tests_run": False,
                    "commit_created": False,
                    "push_performed": False,
                },
            }

        if (
            is_post_apply_verify_request
            or is_post_apply_preview_request
            or is_post_apply_targeted_validation_request
        ):
            applied = self._latest_applied_patch_proposal(
                session_messages, session_metadata
            )
            if applied is None:
                return {
                    "visible_text": "I do not have an applied patch to verify in this session.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_unavailable",
                        "applied": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_applied_patch",
                    },
                }

            target_path = str(applied.get("target_path") or "")
            preview_path = str(applied.get("preview_path") or f"/{target_path}")
            updated_applied = dict(applied)

            if is_post_apply_verify_request:
                verification, _verify_data = self._verify_applied_patch_content(
                    proposal=applied,
                    include_business_name=True,
                )
                updated_applied = self._applied_patch_with_runtime_fields(
                    proposal=applied,
                    verification=verification,
                    preview_path=preview_path,
                )
                checks_raw = verification.get("checks")
                failures_raw = verification.get("failures")
                checks_total = len(checks_raw) if isinstance(checks_raw, list) else 0
                failures_total = (
                    len(failures_raw) if isinstance(failures_raw, list) else 0
                )
                return {
                    "visible_text": (
                        f"Post-apply verification {'passed' if verification.get('status') == 'passed' else 'failed'} for {target_path}. "
                        f"Checked {checks_total} items with {failures_total} failure(s)."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": updated_applied,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_verified",
                        "applied": True,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "preview_path": preview_path,
                        "verification_status": verification.get("status"),
                        "tests_run": False,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

            if is_post_apply_preview_request:
                updated_applied = self._applied_patch_with_runtime_fields(
                    proposal=applied,
                    preview_path=preview_path,
                )
                return {
                    "visible_text": (
                        f"Preview path is {preview_path}. If the local app is running, open that route in your browser to view {target_path}."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": updated_applied,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_preview",
                        "applied": True,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "preview_path": preview_path,
                        "tests_run": False,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

            if is_post_apply_targeted_validation_request:
                verification, verify_data = self._verify_applied_patch_content(
                    proposal=applied,
                    include_business_name=False,
                )
                actual_content = str((verify_data or {}).get("actual_content") or "")
                targeted_status, targeted_checks, targeted_failures = (
                    self._validate_patch_proposal(
                        root=self._workspace_root(),
                        target_path=target_path,
                        content=actual_content,
                        language=str(applied.get("language") or "html"),
                        business_name="",
                        operation=str(applied.get("operation") or "update"),
                    )
                )
                targeted_validation = {
                    "status": targeted_status,
                    "checks": targeted_checks,
                    "failures": targeted_failures,
                    "validated_at": self._utc_now_iso(),
                    "mode": "post_apply_targeted",
                }
                updated_applied = self._applied_patch_with_runtime_fields(
                    proposal=applied,
                    verification=verification,
                    targeted_validation=targeted_validation,
                    preview_path=preview_path,
                )
                return {
                    "visible_text": (
                        f"Targeted validation {'passed' if targeted_status == 'passed' else 'failed'} for {target_path}. "
                        "Only focused file checks were run; no broad test suites were executed."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": updated_applied,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: artifact-patch-post-apply",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_patch": "post_apply_targeted_validation",
                        "applied": True,
                        "requires_confirmation": True,
                        "target_path": target_path,
                        "preview_path": preview_path,
                        "targeted_validation": targeted_status,
                        "tests_run": False,
                        "commit_created": False,
                        "push_performed": False,
                    },
                }

        if allow_commit_lane and is_commit_proposal_request:
            proposal = self._build_commit_proposal(
                question=question,
                session_messages=session_messages,
                session_metadata=session_metadata,
            )
            return {
                "visible_text": str(
                    proposal.get("visible_text")
                    or "I prepared a commit proposal. No files were changed, no commit was created, and no push was performed."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "commit_proposal": proposal,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "commit_proposal": "proposed",
                    "committed": False,
                    "push_performed": False,
                    "requires_confirmation": True,
                    "branch": proposal.get("branch"),
                    "proposal_id": proposal.get("proposal_id"),
                },
            }

        if allow_commit_lane and is_commit_approval_request:
            pending_commit = self._latest_pending_commit_proposal(
                session_messages, session_metadata
            )
            if pending_commit is None:
                return {
                    "visible_text": "I do not have a pending commit proposal to approve in this session.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "commit_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "commit_proposal": "approval_refused",
                        "committed": False,
                        "push_performed": False,
                        "requires_confirmation": True,
                        "failure_reason": "no_pending_commit_proposal",
                    },
                }
            applied_commit = self._apply_commit_proposal(proposal=pending_commit)
            return {
                "visible_text": str(
                    applied_commit.get("visible_text")
                    or "Committed the approved local changes. No push was performed."
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "commit_proposal": applied_commit.get("commit_proposal", {}),
                "context_receipt": applied_commit.get("context_receipt"),
                "provenance": applied_commit.get("provenance", {}),
            }

        if (
            not is_generation
            and not is_site_bundle_generation
            and refinement_mode is not None
            and latest_artifact is None
        ):
            return {
                "visible_text": self._artifact_needs_context_message(),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "artifact_refinement_unavailable",
                    "artifact_validation": "failed",
                    "failure_reason": "no_active_artifact",
                },
            }

        if (
            not is_generation
            and not is_refinement_request
            and not is_site_bundle_generation
            and not is_sandbox_build_request
        ):
            return None

        # ─── Site bundle generation ─────────────────────────────────────────────────
        if is_site_bundle_generation and not is_refinement_request:
            _biz = self._format_business_name(
                self._extract_artifact_name(question), "Local Business Website"
            )
            _project_plan = WebsiteProjectNameManager.build_project_name_payload(
                question,
                fallback=_biz,
            )
            _page_plan = WebsitePagePlanManager.build_manifest_pages(question)
            _style_plan = WebsiteStylePlanManager.build_style_plan(question)
            _section_plan = WebsiteSectionPlanManager.build_section_plan(question)
            _content_block_plan = (
                WebsiteContentBlockPlanManager.build_content_block_plan(question)
            )
            _cta_plan = WebsiteCallToActionManager.build_cta_plan(
                question,
                business_type=str(_content_block_plan.get("profile") or ""),
            )
            _contact_plan = WebsiteContactPlanManager.build_plan(question)
            _seo_plan = WebsiteSeoPlanManager.build_plan(question, _biz)
            _style = self._extract_style_hints(question)
            _slug = self._safe_slug(_biz, fallback="site-bundle")
            _pages = sb.default_pages_for_business(_biz, question)
            _files = sb.build_bundle_files(
                business_name=_biz,
                slug=_slug,
                pages=_pages,
                style_hints=_style,
                question=question,
            )
            _passed, _failures = sb.validate_bundle(
                bundle_files=_files,
                entry="index.html",
                business_name=_biz,
                style_hints=_style,
            )
            if not _passed:
                return {
                    "visible_text": "I could not generate a valid site bundle. "
                    + "; ".join(_failures),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "site_bundle_generation_failed",
                        "artifact_validation": "failed",
                        "failure_reason": "; ".join(_failures),
                    },
                }
            _bundle_id = f"{_slug}-bundle"
            _rev = len(artifact_history) + 1
            _route_manifest = [
                {
                    "path": page,
                    "label": sb.page_label(page),
                    "route": "/" if page == "index.html" else f"/{page}",
                    "is_entry": page == "index.html",
                }
                for page in _pages
                if page.endswith(".html")
            ]
            _code_artifacts = [
                {
                    "filename": str(file_item.get("path") or ""),
                    "language": str(file_item.get("language") or "html"),
                    "content": str(file_item.get("content") or ""),
                    "previewable": str(file_item.get("path") or "").endswith(".html"),
                    "applied": False,
                }
                for file_item in _files
                if isinstance(file_item, dict)
                and str(file_item.get("path") or "").strip()
                and str(file_item.get("content") or "").strip()
            ]
            _bundle_page_names = [
                page[:-5] if page.endswith(".html") else page
                for page in _pages
                if page.endswith(".html")
            ]
            _bundle_asset_files = [
                str(file_item.get("path") or "")
                for file_item in _files
                if isinstance(file_item, dict)
                and str(file_item.get("path") or "").strip()
                and not str(file_item.get("path") or "").endswith(".html")
            ]
            _bundle_plan_raw = WebsiteBundleAssemblyManager.plan_bundle(
                pages=_bundle_page_names,
                asset_files=_bundle_asset_files,
            )
            _build_style_plan: WebsiteBuildStylePlan = {}
            _style_colors = [
                str(color).strip()
                for color in _style_plan.get("colors", [])
                if str(color).strip()
            ]
            _style_notes = [
                str(style).strip()
                for style in _style_plan.get("styles", [])
                if str(style).strip()
            ]
            _style_theme = str(_style_plan.get("theme") or "").strip()
            if _style_colors:
                _build_style_plan["colors"] = _style_colors
            if _style_theme:
                _build_style_plan["tone"] = _style_theme
            if _style_notes:
                _build_style_plan["notes"] = _style_notes

            _cta_actions = _cta_plan.get("actions")
            _cta_labels: list[str] = []
            if isinstance(_cta_actions, list):
                for action in _cta_actions:
                    if not isinstance(action, dict):
                        continue
                    label = str(action.get("label") or "").strip()
                    if label:
                        _cta_labels.append(label)
            _build_cta_plan: WebsiteBuildCallsToActionPlan = {}
            if _cta_labels:
                _build_cta_plan["primary"] = _cta_labels[0]
                if len(_cta_labels) > 1:
                    _build_cta_plan["secondary"] = _cta_labels[1:]

            _build_contact_plan: WebsiteBuildContactPlan = {}
            _primary_phone = str(_contact_plan.get("primary_phone") or "").strip()
            _primary_email = str(_contact_plan.get("primary_email") or "").strip()
            if _primary_phone:
                _build_contact_plan["phone"] = _primary_phone
            if _primary_email:
                _build_contact_plan["email"] = _primary_email

            _build_seo_plan: WebsiteBuildSeoPlan = {}
            _seo_title = str(_seo_plan.get("title") or "").strip()
            _seo_description = str(_seo_plan.get("description") or "").strip()
            _seo_keywords_raw = _seo_plan.get("keywords")
            _seo_keywords: list[str] = []
            if isinstance(_seo_keywords_raw, list):
                _seo_keywords = [
                    str(keyword).strip()
                    for keyword in _seo_keywords_raw
                    if str(keyword).strip()
                ]
            if _seo_title:
                _build_seo_plan["title"] = _seo_title
            if _seo_description:
                _build_seo_plan["description"] = _seo_description
            if _seo_keywords:
                _build_seo_plan["keywords"] = _seo_keywords

            _build_content_blocks: list[WebsiteBuildContentBlockPlanItem] = []
            for block in _content_block_plan.get("blocks", []):
                build_block: WebsiteBuildContentBlockPlanItem = {
                    "id": str(block.get("id") or "").strip(),
                    "slug": str(block.get("slug") or "").strip(),
                    "kind": str(block.get("kind") or "").strip(),
                    "label": str(block.get("label") or "").strip(),
                    "source": str(block.get("source") or "").strip(),
                }
                if build_block["id"] or build_block["slug"] or build_block["kind"]:
                    _build_content_blocks.append(build_block)
            _build_content_block_plan: WebsiteBuildContentBlockPlan = {
                "profile": str(_content_block_plan.get("profile") or "").strip(),
                "blocks": _build_content_blocks,
            }

            _build_page_routes: list[WebsiteBuildPageRoute] = []
            for route in _bundle_plan_raw.get("page_routes", []):
                page_route: WebsiteBuildPageRoute = {
                    "slug": str(route.get("slug") or "").strip(),
                    "path": str(route.get("path") or "").strip(),
                    "route": str(route.get("route") or "").strip(),
                }
                if page_route["slug"] or page_route["path"] or page_route["route"]:
                    _build_page_routes.append(page_route)
            _build_bundle_plan: WebsiteBuildBundlePlan = {
                "entrypoint": str(_bundle_plan_raw.get("entrypoint") or "").strip(),
                "html_files": [
                    str(path).strip()
                    for path in _bundle_plan_raw.get("html_files", [])
                    if str(path).strip()
                ],
                "asset_files": [
                    str(path).strip()
                    for path in _bundle_plan_raw.get("asset_files", [])
                    if str(path).strip()
                ],
                "page_routes": _build_page_routes,
                "warnings": [
                    str(warning).strip()
                    for warning in _bundle_plan_raw.get("warnings", [])
                    if str(warning).strip()
                ],
            }
            _build_sections = [
                str(section.get("title") or "").strip()
                for section in _section_plan
                if isinstance(section, dict) and str(section.get("title") or "").strip()
            ]
            _build_plan = WebsiteBuildPlanManager.build_plan(
                project_name=_biz,
                project_slug=_slug,
                business_type=str(_content_block_plan.get("profile") or ""),
                pages=_bundle_page_names,
                sections=_build_sections,
                style_plan=_build_style_plan,
                cta_plan=_build_cta_plan,
                contact_plan=_build_contact_plan,
                seo_plan=_build_seo_plan,
                content_block_plan=_build_content_block_plan,
                bundle_plan=_build_bundle_plan,
            )
            _created_file_paths = [
                str(file_item.get("path") or "").strip()
                for file_item in _files
                if isinstance(file_item, dict)
                and str(file_item.get("path") or "").strip()
            ]
            _visible_response_plan = VisibleResponsePlanManager.build_plan(
                action_name="created",
                artifact_type="website bundle",
                project_name=_biz,
                created_files=_created_file_paths,
                warnings=_build_plan.get("warnings", []),
                next_actions=["Review and preview the generated files inline."],
            )
            _bundle_artifact: dict[str, Any] = {
                "artifact_type": "site_bundle",
                "artifact_id": _bundle_id,
                "revision_id": f"{_bundle_id}:r{_rev}",
                "revision_number": _rev,
                "title": _biz,
                "slug": _slug,
                "entry": "index.html",
                "active_file": "index.html",
                "preview_entrypoint": "index.html",
                "route_manifest": _route_manifest,
                "render_mode": "code_editor_preview",
                "files": _files,
                "project_plan": _project_plan,
                "page_plan": _page_plan,
                "style_plan": _style_plan,
                "section_plan": _section_plan,
                "content_block_plan": _content_block_plan,
                "cta_plan": _cta_plan,
                "contact_plan": _contact_plan,
                "seo_plan": _seo_plan,
                "bundle_plan": _bundle_plan_raw,
                "build_plan": _build_plan,
                "visible_response_plan": _visible_response_plan,
                "source_prompt": question.strip(),
                "site_bundle": {"files": _files},
            }
            if site_bundle_deliver_to_sandbox:
                written_relative, written_absolute = self._write_sandbox_bundle(
                    project_slug=_slug,
                    bundle_files=_files,
                )
                _bundle_artifact.update(
                    {
                        "delivery_mode": "sandbox_write",
                        "sandbox_root": str(self._sandbox_root()),
                        "sandbox_project_slug": _slug,
                        "sandbox_project_path": str(self._sandbox_root() / _slug),
                        "sandbox_written_paths": written_absolute,
                    }
                )
                _code_artifacts = [
                    {
                        **artifact,
                        "applied": True,
                        "delivery_mode": "sandbox_write",
                        "sandbox_root": str(self._sandbox_root()),
                        "sandbox_project_slug": _slug,
                        "sandbox_relative_path": written_relative[idx],
                        "sandbox_target_path": written_absolute[idx],
                    }
                    for idx, artifact in enumerate(_code_artifacts)
                    if idx < len(written_relative) and idx < len(written_absolute)
                ]
            _html_pages = [p for p in _pages if p.endswith(".html")]
            return {
                "visible_text": (
                    f"Built a {len(_html_pages)}-page website for {_biz} in {self._sandbox_root() / _slug}. "
                    "You can review and preview the generated files inline."
                    if site_bundle_deliver_to_sandbox
                    else f"Here is a {len(_html_pages)}-page website artifact for {_biz}. You can review and preview the generated files inline."
                ),
                "code_artifact": {},
                "code_artifacts": _code_artifacts,
                "artifact_patch_proposal": {},
                "site_bundle": _bundle_artifact,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "site_bundle",
                    "artifact_validation": "passed",
                    "revision_number": _rev,
                    "business_name": _biz,
                    "slug": _slug,
                    "project_plan": _project_plan,
                    "page_plan": _page_plan,
                    "style_plan": _style_plan,
                    "section_plan": _section_plan,
                    "content_block_plan": _content_block_plan,
                    "cta_plan": _cta_plan,
                    "contact_plan": _contact_plan,
                    "seo_plan": _seo_plan,
                    "bundle_plan": _bundle_plan_raw,
                    "build_plan": _build_plan,
                    "visible_response_plan": _visible_response_plan,
                    "file_count": len(_files),
                    "delivery_mode": "sandbox_write"
                    if site_bundle_deliver_to_sandbox
                    else "chat_artifact",
                },
            }

        if (
            is_refinement_request
            and latest_artifact is not None
            and str(latest_artifact.get("artifact_type") or "") == "site_bundle"
        ):
            latest_bundle = latest_artifact.get("site_bundle")
            latest_files_raw: list[dict[str, Any]] = []
            if isinstance(latest_bundle, dict):
                files_candidate = latest_bundle.get("files")
                if isinstance(files_candidate, list):
                    for item in files_candidate:
                        if isinstance(item, dict):
                            latest_files_raw.append(item)
            latest_files = [
                item
                for item in latest_files_raw
                if sb.is_safe_bundle_path(str(item.get("path") or ""))
            ]
            existing_pages = [
                str(item.get("path") or "")
                for item in latest_files
                if str(item.get("path") or "")
            ]
            source_prompt = str(latest_artifact.get("source_prompt") or question)
            _biz = self._format_business_name(
                str(
                    latest_artifact.get("title")
                    or self._extract_artifact_name(source_prompt)
                ),
                "Local Business Website",
            )
            _slug = self._safe_slug(
                str(latest_artifact.get("slug") or _biz), fallback="site-bundle"
            )
            _pages = existing_pages or sb.default_pages_for_business(
                _biz, source_prompt
            )

            _style = self._extract_style_hints(question)
            if not _style.get("colors"):
                css_text = ""
                for item in latest_files:
                    if str(item.get("path") or "").endswith(".css"):
                        css_text = str(item.get("content") or "")
                        break
                if css_text:
                    colors_from_css: list[str] = []
                    for var_name in ("bg", "accent", "text"):
                        match = re.search(rf"--{var_name}:\s*([^;]+);", css_text)
                        if match:
                            colors_from_css.append(match.group(1).strip())
                    if colors_from_css:
                        _style["colors"] = colors_from_css

            typo_style = self._typography_style_request(normalized)
            if typo_style and typo_style not in _style.get("styles", []):
                _style.setdefault("styles", []).append(typo_style)

            _files = sb.build_bundle_files(
                business_name=_biz,
                slug=_slug,
                pages=_pages,
                style_hints=_style,
                question=question,
            )
            _passed, _failures = sb.validate_bundle(
                bundle_files=_files,
                entry=str(latest_artifact.get("entry") or "index.html"),
                business_name=_biz,
                style_hints=_style,
            )
            if not _passed:
                return {
                    "visible_text": (
                        "I could not complete the requested site bundle refinement safely, so I preserved the current bundle unchanged. "
                        + "; ".join(_failures)
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "site_bundle": latest_artifact,
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "site_bundle_refinement_failed",
                        "artifact_validation": "failed",
                        "failure_reason": "; ".join(_failures),
                    },
                }

            _bundle_id = str(latest_artifact.get("artifact_id") or f"{_slug}-bundle")
            _rev = len(artifact_history) + 1
            _entry = str(latest_artifact.get("entry") or "index.html")
            _route_manifest = [
                {
                    "path": page,
                    "label": sb.page_label(page),
                    "route": "/" if page == "index.html" else f"/{page}",
                    "is_entry": page == _entry,
                }
                for page in _pages
                if page.endswith(".html")
            ]
            _code_artifacts = [
                {
                    "filename": str(file_item.get("path") or ""),
                    "language": str(file_item.get("language") or "html"),
                    "content": str(file_item.get("content") or ""),
                    "previewable": str(file_item.get("path") or "").endswith(".html"),
                    "applied": False,
                }
                for file_item in _files
                if isinstance(file_item, dict)
                and str(file_item.get("path") or "").strip()
                and str(file_item.get("content") or "").strip()
            ]
            revised_bundle_artifact: dict[str, Any] = {
                **latest_artifact,
                "artifact_type": "site_bundle",
                "artifact_id": _bundle_id,
                "revision_id": f"{_bundle_id}:r{_rev}",
                "revision_number": _rev,
                "title": _biz,
                "slug": _slug,
                "entry": _entry,
                "active_file": _entry,
                "preview_entrypoint": _entry,
                "route_manifest": _route_manifest,
                "render_mode": "code_editor_preview",
                "files": _files,
                "source_prompt": source_prompt,
                "site_bundle": {"files": _files},
            }
            if site_bundle_deliver_to_sandbox:
                written_relative, written_absolute = self._write_sandbox_bundle(
                    project_slug=_slug,
                    bundle_files=_files,
                )
                revised_bundle_artifact.update(
                    {
                        "delivery_mode": "sandbox_write",
                        "sandbox_root": str(self._sandbox_root()),
                        "sandbox_project_slug": _slug,
                        "sandbox_project_path": str(self._sandbox_root() / _slug),
                        "sandbox_written_paths": written_absolute,
                    }
                )
                _code_artifacts = [
                    {
                        **artifact,
                        "applied": True,
                        "delivery_mode": "sandbox_write",
                        "sandbox_root": str(self._sandbox_root()),
                        "sandbox_project_slug": _slug,
                        "sandbox_relative_path": written_relative[idx],
                        "sandbox_target_path": written_absolute[idx],
                    }
                    for idx, artifact in enumerate(_code_artifacts)
                    if idx < len(written_relative) and idx < len(written_absolute)
                ]

            return {
                "visible_text": (
                    f"Updated the sandbox website in {self._sandbox_root() / _slug} and refreshed the inline preview."
                    if site_bundle_deliver_to_sandbox
                    else 'Updated the active site bundle revision and preserved all pages/content. Review it here, then say "write this to the sandbox" when it is ready.'
                ),
                "code_artifact": {},
                "code_artifacts": _code_artifacts,
                "artifact_patch_proposal": {},
                "site_bundle": revised_bundle_artifact,
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: site-bundle-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "site_bundle_refinement",
                    "artifact_validation": "passed",
                    "revision_number": _rev,
                    "business_name": _biz,
                    "slug": _slug,
                    "file_count": len(_files),
                    "delivery_mode": "sandbox_write"
                    if site_bundle_deliver_to_sandbox
                    else "chat_artifact",
                },
            }

        next_revision_number = len(artifact_history) + 1

        if refinement_mode == "undo" and latest_artifact is not None:
            if len(artifact_history) < 2:
                return {
                    "visible_text": "I do not have an earlier artifact revision to restore in this session.",
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        "artifact_generation": "artifact_undo",
                        "source_artifact": "previous_session_revision",
                        "artifact_validation": "failed",
                        "failure_reason": "no_previous_revision",
                    },
                }
            restored_artifact = dict(artifact_history[-2]["artifact"])
            restored_artifact.update(
                {
                    "revision_id": f"{restored_artifact.get('artifact_id')}:r{next_revision_number}",
                    "revision_number": next_revision_number,
                    "source_prompt": question.strip(),
                }
            )
            return {
                "visible_text": f"I restored the previous {str(restored_artifact.get('language') or 'HTML').upper()} artifact for {restored_artifact.get('filename', 'index.html')}.",
                "code_artifact": restored_artifact,
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "artifact_undo",
                    "source_artifact": "previous_session_revision",
                    "revision_number": next_revision_number,
                },
            }

        if refinement_mode == "explain" and latest_artifact is not None:
            previous_artifact = (
                artifact_history[-2]["artifact"] if len(artifact_history) >= 2 else None
            )
            return {
                "visible_text": self._artifact_change_summary(
                    latest_artifact, previous_artifact
                ),
                "code_artifact": {},
                "artifact_patch_proposal": {},
                "context_receipt": {
                    "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                    "context_receipts": [],
                    "record_ids": [],
                },
                "provenance": {
                    "artifact_generation": "artifact_change_summary",
                    "source_artifact": "latest session artifact",
                    "source_artifact_key": "latest_session_artifact",
                },
            }

        if is_refinement_request and latest_artifact is not None:
            filename = str(latest_artifact.get("filename") or "index.html")
            language = str(
                latest_artifact.get("language")
                or self._code_artifact_language(normalized)
            )
            previewable = bool(latest_artifact.get("previewable", language == "html"))
            apply_requested = False
            business_name = self._extract_business_name_from_html(
                str(latest_artifact.get("content") or "")
            )
            business_name = self._format_business_name(
                business_name,
                "Local Business Website" if language == "html" else "Draft Artifact",
            )
            style_hints = self._extract_style_hints(question)
            layout_hints = self._extract_layout_hints(question)
        else:
            language = self._code_artifact_language(normalized)
            filename = self._extract_requested_filename(question, language)
            previewable = self._extract_requested_previewable(question, language)
            apply_requested = self._extract_apply_intent(question)
            business_name = self._format_business_name(
                self._extract_artifact_name(question),
                "Local Business Website" if language == "html" else "Draft Artifact",
            )
            style_hints = self._extract_style_hints(question)
            layout_hints = self._extract_layout_hints(question)

        artifact_content: str = ""
        provenance: dict[str, Any]
        typography_refinement_payload: dict[str, Any] | None = None
        if is_refinement_request and latest_artifact is not None:
            typography_style = (
                self._typography_style_request(normalized)
                if refinement_mode == "typography_only"
                else None
            )
            if typography_style:
                artifact_content, typography_refinement_payload, typ_ok, typ_reason = (
                    self._deterministic_typography_refinement_content(
                        source_artifact=latest_artifact,
                        requested_style=typography_style,
                    )
                )
                typography_business_name = (
                    self._extract_business_name_from_html(
                        str(latest_artifact.get("content") or "")
                    )
                    or ""
                )
                valid, reason = self._validate_artifact_content(
                    content=artifact_content,
                    language=str(latest_artifact.get("language") or "html"),
                    business_name=typography_business_name,
                    style_hints={"colors": [], "styles": []},
                    requested_question="",
                )
                if not typ_ok or not valid:
                    return {
                        "visible_text": (
                            "I could not safely apply the typography refinement, so I preserved the current artifact unchanged."
                        ),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "typography_refinement_failed",
                            "artifact_validation": "failed",
                            "source_artifact": source_artifact_label
                            or "latest session artifact",
                            "source_artifact_key": "latest_session_artifact",
                            "revision_mode": "typography_only",
                            "failure_reason": typ_reason if not typ_ok else reason,
                            "typography_refinement": {
                                **(typography_refinement_payload or {}),
                                "status": "failed",
                            },
                        },
                    }
                provenance = {
                    "artifact_generation": "deterministic_typography_refinement",
                    "artifact_validation": "passed",
                    "source_artifact": source_artifact_label
                    or "latest session artifact",
                    "source_artifact_key": "latest_session_artifact",
                    "revision_mode": "typography_only",
                    "revision_number": next_revision_number,
                    "typography_refinement": typography_refinement_payload,
                }
            else:
                try:
                    revision_source_artifact = dict(latest_artifact)
                    revision_source_artifact["_revision_mode"] = (
                        refinement_mode or "full_revision"
                    )
                    (
                        artifact_content,
                        model_used,
                        model_endpoint,
                    ) = await self._revise_artifact_with_local_model(
                        question=question,
                        source_artifact=revision_source_artifact,
                    )
                    provenance = {
                        "artifact_generation": "local_model_revision",
                        "model_used": model_used,
                        "model_endpoint": model_endpoint,
                        "artifact_validation": "passed",
                        "source_artifact": source_artifact_label
                        or "latest session artifact",
                        "source_artifact_key": "latest_session_artifact",
                        "revision_mode": refinement_mode or "full_revision",
                        "revision_number": next_revision_number,
                    }
                except Exception as exc:
                    fallback_reason = str(exc).strip() or "artifact_revision_failed"
                    artifact_content = self._deterministic_revision_fallback_content(
                        question=question,
                        source_artifact=latest_artifact,
                        revision_mode=refinement_mode or "full_revision",
                    )
                    valid, reason = self._validate_revision_candidate(
                        content=artifact_content,
                        source_artifact=latest_artifact,
                        requested_question=question,
                    )
                    model_resolution = resolve_model_for_runtime_role("code")
                    if not valid:
                        return {
                            "visible_text": (
                                "I could not complete the requested artifact revision safely, so I preserved the current artifact unchanged. "
                                "The requested edit failed validation."
                            ),
                            "code_artifact": {},
                            "artifact_patch_proposal": {},
                            "context_receipt": {
                                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                                "context_receipts": [],
                                "record_ids": [],
                            },
                            "provenance": {
                                "artifact_generation": "artifact_refinement_failed",
                                "artifact_validation": "failed",
                                "source_artifact": source_artifact_label
                                or "latest session artifact",
                                "source_artifact_key": "latest_session_artifact",
                                "revision_mode": refinement_mode or "full_revision",
                                "failure_reason": reason,
                            },
                        }
                    provenance = {
                        "artifact_generation": "deterministic_prompt_template_fallback",
                        "model_used": model_resolution.model_tag or "unknown",
                        "fallback_reason": f"artifact revision fallback: {fallback_reason}",
                        "fallback_prevalidation": (
                            "passed" if valid else f"failed:{reason}"
                        ),
                        "source_artifact": source_artifact_label
                        or "latest session artifact",
                        "source_artifact_key": "latest_session_artifact",
                        "revision_mode": refinement_mode or "full_revision",
                        "revision_number": next_revision_number,
                    }
        else:
            try:
                generation_result = await self._generate_artifact_with_local_model(
                    question=question,
                    filename=filename,
                    language=language,
                    previewable=previewable,
                    apply_requested=apply_requested,
                    business_name=business_name,
                    style_hints=style_hints,
                    layout_hints=layout_hints,
                )
                if len(generation_result) == 3:
                    artifact_content, model_used, model_endpoint = generation_result
                else:
                    artifact_content, model_used = generation_result  # type: ignore[misc]
                    model_endpoint = configured_ollama_base_url_candidates()[0]
                provenance = {
                    "artifact_generation": "local_model",
                    "model_used": model_used,
                    "model_endpoint": model_endpoint,
                    "artifact_validation": "passed",
                    "revision_number": next_revision_number,
                }
            except Exception as exc:
                fallback_reason = str(exc).strip() or "local_model_error"
                artifact_content = self._default_code_artifact_content(
                    filename, language, question
                )
                valid, reason = self._validate_artifact_content(
                    content=artifact_content,
                    language=language,
                    business_name=business_name,
                    style_hints=style_hints,
                    requested_question=question,
                )
                if not valid:
                    return {
                        "visible_text": (
                            "I could not generate a safe artifact draft right now. "
                            "Please try again with a slightly simpler prompt and I will keep the requested business identity intact."
                        ),
                        "code_artifact": {},
                        "artifact_patch_proposal": {},
                        "context_receipt": {
                            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                            "context_receipts": [],
                            "record_ids": [],
                        },
                        "provenance": {
                            "artifact_generation": "artifact_generation_failed",
                            "artifact_validation": "failed",
                            "failure_reason": "fallback_validation_failed",
                            "revision_number": next_revision_number,
                        },
                    }
                model_resolution = resolve_model_for_runtime_role("code")
                provenance = {
                    "artifact_generation": "deterministic_prompt_template_fallback",
                    "model_used": model_resolution.model_tag or "unknown",
                    "fallback_reason": fallback_reason,
                    "revision_number": next_revision_number,
                }

        fidelity_context = self._prompt_fidelity_history_metadata(
            session_messages,
            session_metadata,
        )
        if business_name:
            fidelity_context["requested_business_name_override"] = business_name
        if is_refinement_request and latest_artifact is not None:
            fidelity_source_prompt = str(
                latest_artifact.get("source_prompt") or question
            )
            fidelity_context["requested_business_type_override"] = (
                self._artifact_business_category(
                    fidelity_source_prompt,
                    business_name,
                )
            )
        fidelity_prompt = question
        if refinement_mode == "typography_only" and latest_artifact is not None:
            fidelity_prompt = str(latest_artifact.get("source_prompt") or question)

        prompt_fidelity = self.validate_artifact_prompt_fidelity(
            fidelity_prompt,
            artifact_content,
            fidelity_context,
        )
        prompt_fidelity_payload = {
            "status": str(prompt_fidelity.get("status") or "failed"),
            "requested_business_name": str(
                prompt_fidelity.get("requested_business_name") or ""
            ).strip(),
            "requested_business_type": str(
                prompt_fidelity.get("requested_business_type") or ""
            ).strip(),
            "requested_colors": [
                str(item).strip()
                for item in (prompt_fidelity.get("requested_colors") or [])
                if str(item).strip()
            ],
            "forbidden_terms_checked": [
                str(item).strip()
                for item in (prompt_fidelity.get("forbidden_terms_checked") or [])
                if str(item).strip()
            ],
            "repair_attempted": False,
        }

        if not bool(prompt_fidelity.get("passed")):
            repaired_content = self._repair_artifact_prompt_fidelity(
                prompt=question,
                artifact_content=artifact_content,
                fidelity_report=prompt_fidelity,
            )
            repaired_fidelity = self.validate_artifact_prompt_fidelity(
                fidelity_prompt,
                repaired_content,
                fidelity_context,
            )
            if bool(repaired_fidelity.get("passed")):
                artifact_content = repaired_content
                prompt_fidelity_payload = {
                    "status": "repaired",
                    "requested_business_name": str(
                        repaired_fidelity.get("requested_business_name") or ""
                    ).strip(),
                    "requested_business_type": str(
                        repaired_fidelity.get("requested_business_type") or ""
                    ).strip(),
                    "requested_colors": [
                        str(item).strip()
                        for item in (repaired_fidelity.get("requested_colors") or [])
                        if str(item).strip()
                    ],
                    "forbidden_terms_checked": [
                        str(item).strip()
                        for item in (
                            repaired_fidelity.get("forbidden_terms_checked") or []
                        )
                        if str(item).strip()
                    ],
                    "repair_attempted": True,
                }
            else:
                failure_reason = ", ".join(
                    repaired_fidelity.get("failures")
                    or prompt_fidelity.get("failures")
                    or ["prompt_fidelity_failed"]
                )
                return {
                    "visible_text": (
                        "I generated an artifact, but it failed prompt-fidelity validation because it still contained stale template or palette content. "
                        "I did not return the unsafe artifact."
                    ),
                    "code_artifact": {},
                    "artifact_patch_proposal": {},
                    "context_receipt": {
                        "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                        "context_receipts": [],
                        "record_ids": [],
                    },
                    "provenance": {
                        **provenance,
                        "artifact_generation": "artifact_prompt_fidelity_blocked",
                        "artifact_validation": "failed",
                        "failure_reason": failure_reason,
                        "prompt_fidelity": {
                            **prompt_fidelity_payload,
                            "status": "failed",
                            "repair_attempted": True,
                        },
                    },
                }

        provenance["prompt_fidelity"] = prompt_fidelity_payload
        provenance["artifact_validation"] = prompt_fidelity_payload.get(
            "status", "passed"
        )
        if typography_refinement_payload is not None:
            provenance["typography_refinement"] = typography_refinement_payload

        delivery_mode = "sandbox_write" if deliver_to_sandbox else "chat_artifact"
        project_slug = self._safe_slug(
            business_name,
            fallback=self._slugify_artifact_name(filename),
        )
        sandbox_relative_path = None
        sandbox_target_path = None
        applied_flag = False
        if deliver_to_sandbox:
            sandbox_relative_path = (
                str(
                    latest_artifact.get("sandbox_relative_path")
                    or f"{project_slug}/{filename}"
                )
                if latest_artifact is not None
                else f"{project_slug}/{filename}"
            )
            project_slug = (
                str(latest_artifact.get("sandbox_project_slug") or project_slug)
                if latest_artifact is not None
                else project_slug
            )
            sandbox_relative_path, sandbox_target_path = self._write_sandbox_file(
                project_slug=project_slug,
                filename=filename,
                content=artifact_content,
            )
            applied_flag = True
            provenance["delivery_mode"] = "sandbox_write"
            provenance["sandbox_root"] = str(self._sandbox_root())
            provenance["sandbox_project_slug"] = project_slug
            provenance["sandbox_target_path"] = sandbox_target_path
        else:
            provenance["delivery_mode"] = "chat_artifact"

        return {
            "visible_text": (
                f"Updated the sandbox file at {sandbox_target_path} and refreshed the inline preview."
                if (
                    is_refinement_request and deliver_to_sandbox and sandbox_target_path
                )
                else f"Built the sandbox file at {sandbox_target_path} and rendered it inline."
                if (deliver_to_sandbox and sandbox_target_path)
                else f"Here is a revised {language.upper()} artifact for {filename}."
                if is_refinement_request
                else f"Here is a draft {language.upper()} artifact for {filename}."
            ),
            "code_artifact": {
                "type": "code_artifact",
                "filename": filename,
                "language": language,
                "previewable": previewable,
                "applied": applied_flag,
                "content": artifact_content,
                "artifact_id": (
                    latest_artifact.get("artifact_id")
                    if latest_artifact is not None
                    else f"{self._slugify_artifact_name(filename)}-artifact"
                ),
                "revision_id": f"{(latest_artifact.get('artifact_id') if latest_artifact is not None else self._slugify_artifact_name(filename) + '-artifact')}:r{next_revision_number}",
                "revision_number": next_revision_number,
                "source_prompt": question.strip(),
                "prompt_fidelity": prompt_fidelity_payload,
                "typography_refinement": typography_refinement_payload or {},
                "delivery_mode": delivery_mode,
                "sandbox_root": str(self._sandbox_root()) if deliver_to_sandbox else "",
                "sandbox_project_slug": project_slug if deliver_to_sandbox else "",
                "sandbox_relative_path": sandbox_relative_path or "",
                "sandbox_target_path": sandbox_target_path or "",
            },
            "artifact_patch_proposal": {},
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                "context_receipts": [],
                "record_ids": [],
            },
            "provenance": provenance,
        }

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
