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

def install_answer_contract_part_01(contract_cls):
    global AnswerContract
    AnswerContract = contract_cls
    setattr(contract_cls, "_normalize", _normalize)
    setattr(contract_cls, "_find_layer_record", _find_layer_record)
    setattr(contract_cls, "_facts", _facts)
    setattr(contract_cls, "_extract_user_name", _extract_user_name)
    setattr(contract_cls, "_session_active_focus_summary", _session_active_focus_summary)
    setattr(contract_cls, "_session_memory_hints", _session_memory_hints)
    setattr(contract_cls, "_normalize_reminder_request", _normalize_reminder_request)
    setattr(contract_cls, "_has_live_repo_check_proof", _has_live_repo_check_proof)
    setattr(contract_cls, "_latest_model_tag", _latest_model_tag)
    setattr(contract_cls, "_last_verified_operator_model", _last_verified_operator_model)
    setattr(contract_cls, "is_code_artifact_request", is_code_artifact_request)
    setattr(contract_cls, "_code_artifact_language", _code_artifact_language)
    setattr(contract_cls, "_code_artifact_filename", _code_artifact_filename)
    setattr(contract_cls, "_clean_artifact_label", _clean_artifact_label)
    setattr(contract_cls, "_extract_artifact_name", _extract_artifact_name)
    setattr(contract_cls, "_artifact_business_category", _artifact_business_category)
    setattr(contract_cls, "_artifact_style_profile", _artifact_style_profile)
    setattr(contract_cls, "_format_business_name", _format_business_name)
    setattr(contract_cls, "_build_business_site_template", _build_business_site_template)
    setattr(contract_cls, "_default_code_artifact_content", _default_code_artifact_content)
    setattr(contract_cls, "_extract_requested_filename", _extract_requested_filename)
    setattr(contract_cls, "_extract_requested_previewable", _extract_requested_previewable)
    setattr(contract_cls, "_extract_apply_intent", _extract_apply_intent)
    setattr(contract_cls, "_extract_style_hints", _extract_style_hints)
    setattr(contract_cls, "_extract_layout_hints", _extract_layout_hints)
    setattr(contract_cls, "_artifact_intent_label", _artifact_intent_label)
    setattr(contract_cls, "_extract_prompt_fidelity_contract", _extract_prompt_fidelity_contract)
    setattr(contract_cls, "_color_hex_map", _color_hex_map)
    setattr(contract_cls, "_service_terms_for_business_type", _service_terms_for_business_type)
    setattr(contract_cls, "_prompt_fidelity_forbidden_terms", _prompt_fidelity_forbidden_terms)
    setattr(contract_cls, "validate_artifact_prompt_fidelity", validate_artifact_prompt_fidelity)
    setattr(contract_cls, "_repair_artifact_prompt_fidelity", _repair_artifact_prompt_fidelity)
    setattr(contract_cls, "_build_local_artifact_prompt", _build_local_artifact_prompt)
    setattr(contract_cls, "_remediation_for_validation_reason", _remediation_for_validation_reason)
    setattr(contract_cls, "_looks_like_artifact_edit", _looks_like_artifact_edit)
    setattr(contract_cls, "_extract_business_name_from_html", _extract_business_name_from_html)
    setattr(contract_cls, "_extract_artifact_from_metadata", _extract_artifact_from_metadata)
    setattr(contract_cls, "_prompt_fidelity_history_metadata", _prompt_fidelity_history_metadata)
    setattr(contract_cls, "_latest_assistant_artifact", _latest_assistant_artifact)
    setattr(contract_cls, "_slugify_artifact_name", _slugify_artifact_name)
    setattr(contract_cls, "_is_patch_proposal_request", _is_patch_proposal_request)
    setattr(contract_cls, "_is_patch_apply_request", _is_patch_apply_request)
    setattr(contract_cls, "_is_post_apply_verify_request", _is_post_apply_verify_request)
    setattr(contract_cls, "_is_post_apply_preview_request", _is_post_apply_preview_request)
    setattr(contract_cls, "_is_post_apply_targeted_validation_request", _is_post_apply_targeted_validation_request)
    setattr(contract_cls, "_is_post_apply_full_test_guard_request", _is_post_apply_full_test_guard_request)
    setattr(contract_cls, "_is_commit_proposal_request", _is_commit_proposal_request)
    setattr(contract_cls, "_is_commit_approval_request", _is_commit_approval_request)
    setattr(contract_cls, "_is_post_apply_intent_request", _is_post_apply_intent_request)
    setattr(contract_cls, "_has_explicit_artifact_intent", _has_explicit_artifact_intent)
    setattr(contract_cls, "_is_preview_artifact_request", _is_preview_artifact_request)
    setattr(contract_cls, "_is_sandbox_build_request", _is_sandbox_build_request)
    setattr(contract_cls, "_is_operator_github_project_request", _is_operator_github_project_request)
    setattr(contract_cls, "_is_first_class_operator_request", _is_first_class_operator_request)
    setattr(contract_cls, "_is_repo_mutation_build_prompt", _is_repo_mutation_build_prompt)
    setattr(contract_cls, "_prioritize_artifact_over_build_guard", _prioritize_artifact_over_build_guard)
    setattr(contract_cls, "_workspace_root", _workspace_root)
    setattr(contract_cls, "_sandbox_root", _sandbox_root)
    setattr(contract_cls, "_sandbox_display_root", _sandbox_display_root)
    setattr(contract_cls, "_safe_slug", _safe_slug)
    setattr(contract_cls, "_sanitize_filename", _sanitize_filename)
    setattr(contract_cls, "_resolve_safe_sandbox_target", _resolve_safe_sandbox_target)
    setattr(contract_cls, "_sandbox_relative_file_path", _sandbox_relative_file_path)
    setattr(contract_cls, "_write_sandbox_file", _write_sandbox_file)
    setattr(contract_cls, "_write_sandbox_bundle", _write_sandbox_bundle)
    setattr(contract_cls, "_run_git", _run_git)
    setattr(contract_cls, "_proposed_patch_target_path", _proposed_patch_target_path)
    setattr(contract_cls, "_is_blocked_patch_target", _is_blocked_patch_target)
    setattr(contract_cls, "_is_blocked_commit_target", _is_blocked_commit_target)
    setattr(contract_cls, "_validate_patch_proposal", _validate_patch_proposal)
    setattr(contract_cls, "_content_sha256", _content_sha256)
    setattr(contract_cls, "_utc_now_iso", _utc_now_iso)
    setattr(contract_cls, "_resolve_safe_patch_target", _resolve_safe_patch_target)
