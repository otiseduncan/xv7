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
import core.brain.answer_contract as answer_contract_module

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
    endpoint_candidates = answer_contract_module.configured_ollama_base_url_candidates()
    if not isinstance(endpoint_candidates, list):
        endpoint_candidates = list(endpoint_candidates or [])
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
    endpoint_candidates = answer_contract_module.configured_ollama_base_url_candidates()
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
    endpoint_candidates = answer_contract_module.configured_ollama_base_url_candidates()
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
    return AnswerDecisionService.try_answer(
        contract=self,
        question=question,
        records_by_layer=records_by_layer,
        session_metadata=session_metadata,
    )

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

def install_answer_contract_part_04(contract_cls):
    global AnswerContract
    AnswerContract = contract_cls
    setattr(contract_cls, "_validate_artifact_content", _validate_artifact_content)
    setattr(contract_cls, "_generate_artifact_with_local_model", _generate_artifact_with_local_model)
    setattr(contract_cls, "_revise_artifact_with_local_model", _revise_artifact_with_local_model)
    setattr(contract_cls, "artifact_model_connectivity_diagnostic", artifact_model_connectivity_diagnostic)
    setattr(contract_cls, "build_code_artifact_response", build_code_artifact_response)
    setattr(contract_cls, "_tool_boundary_answer", _tool_boundary_answer)
    setattr(contract_cls, "_tool_intent_category", _tool_intent_category)
    setattr(contract_cls, "try_answer", try_answer)
    setattr(contract_cls, "_is_conceptual_website_advice_question", _is_conceptual_website_advice_question)
