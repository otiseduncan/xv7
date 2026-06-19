from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.brain import site_bundle as sb
from core.brain.intent_router import IntentRouter
from core.memory.auto_pilot import MemoryDecision
from core.x_kernel.decision import XDecisionKernel


NormalizeText = Callable[[str], str]


@dataclass
class KernelRuntimeDependencies:
    answer_contract: Any
    operator_manager: Any
    persistent_memory_manager: Any
    memory_auto_pilot: Any
    classify_speech_act: Callable[[str], str]
    extract_active_focus_instruction: Callable[[str], str | None]
    active_focus_candidate_checker: Callable[[str], bool]
    is_runtime_clock_question: Callable[[str], bool]
    normalize_text: NormalizeText

    def artifact_mode_hints(
        self,
        normalized_message: str,
        *,
        session_messages: list[dict[str, Any]],
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        latest_applied_patch = self.answer_contract._latest_applied_patch_proposal(
            session_messages,
            session_metadata,
        )
        artifact_history = self.answer_contract._artifact_history(
            session_messages,
            session_metadata,
        )
        latest_artifact = artifact_history[-1]["artifact"] if artifact_history else None
        has_artifact_edit_intent = self.answer_contract._looks_like_artifact_edit(
            normalized_message
        )
        has_explicit_artifact_generation_language = bool(
            self.answer_contract.EXPLICIT_ARTIFACT_INTENT_PATTERN.search(
                normalized_message
            )
        )
        is_generation = self.answer_contract.is_code_artifact_request(
            normalized_message
        )
        is_site_bundle_generation = (
            sb.is_site_bundle_request(normalized_message)
            or IntentRouter.is_explicit_chat_site_display_request(normalized_message)
        )
        if (
            latest_artifact is not None
            and has_artifact_edit_intent
            and not has_explicit_artifact_generation_language
        ):
            is_generation = False
            is_site_bundle_generation = False

        is_post_apply_file_check_prompt = normalized_message in {
            "verify it",
            "preview it",
        } or (
            latest_applied_patch is not None
            and (
                self.answer_contract._is_post_apply_verify_request(normalized_message)
                or self.answer_contract._is_post_apply_preview_request(
                    normalized_message
                )
                or self.answer_contract._is_post_apply_targeted_validation_request(
                    normalized_message
                )
            )
        )
        is_post_apply_full_test_prompt = (
            self.answer_contract._is_post_apply_full_test_guard_request(
                normalized_message
            )
            and latest_applied_patch is not None
        )
        is_commit_lane_request = (
            self.answer_contract._is_commit_proposal_request(normalized_message)
            or self.answer_contract._is_commit_approval_request(normalized_message)
        )
        is_sandbox_build = self.answer_contract._is_sandbox_build_request(
            normalized_message
        )
        prioritize_artifact_over_build_guard = (
            self.answer_contract._prioritize_artifact_over_build_guard(
                normalized_message
            )
        )
        refinement_mode = (
            self.answer_contract._artifact_refinement_mode(normalized_message)
            if has_artifact_edit_intent
            else None
        )
        is_refinement_request = (
            refinement_mode is not None
            and not is_generation
            and not is_site_bundle_generation
        )
        artifact_domain_language = any(
            token in normalized_message
            for token in (
                "website",
                "site bundle",
                "site",
                "html",
                "css",
                "preview",
                "artifact",
                "sandbox",
                "landing page",
            )
        )
        implementation_language = any(
            token in normalized_message
            for token in (
                "feature",
                "add tests",
                "run pytest",
                "git commit",
                "git push",
                "endpoint",
                "refactor",
                "repair",
                "fix the first failure",
            )
        )
        repo_mutation_language = any(
            token in normalized_message
            for token in (
                "commit it",
                "commit these changes",
                "commit the changes",
                "push it",
                "git commit",
                "git push",
                "apply this patch",
                "in the repo",
                "repo mutation",
            )
        )
        force_operator_mutation = any(
            phrase in normalized_message
            for phrase in (
                "apply this patch",
                "commit these changes",
                "commit the changes",
            )
        )

        is_artifact_request = (
            self.answer_contract._is_patch_proposal_request(normalized_message)
            or self.answer_contract._is_patch_apply_request(normalized_message)
            or self.answer_contract._is_preview_artifact_request(normalized_message)
            or has_artifact_edit_intent
            or is_generation
            or is_site_bundle_generation
            or is_sandbox_build
            or is_commit_lane_request
            or is_post_apply_file_check_prompt
            or is_post_apply_full_test_prompt
            or prioritize_artifact_over_build_guard
        )
        if implementation_language and not artifact_domain_language:
            is_artifact_request = False
            is_sandbox_build = False
            is_refinement_request = False
        if repo_mutation_language and artifact_domain_language:
            is_commit_lane_request = False
            is_artifact_request = False
            is_sandbox_build = False
            is_refinement_request = False
        if force_operator_mutation:
            is_commit_lane_request = False
            is_artifact_request = False
            is_sandbox_build = False
            is_refinement_request = False
        return {
            "is_artifact_request": is_artifact_request,
            "is_sandbox_build": is_sandbox_build,
            "is_export_request": any(
                phrase in normalized_message
                for phrase in (
                    "export",
                    "save to sandbox",
                    "write this to disk",
                    "save",
                )
            ),
            "is_refinement_request": is_refinement_request,
            "is_commit_lane_request": is_commit_lane_request,
            "force_implementation_guard": repo_mutation_language and artifact_domain_language,
            "force_operator_mutation": force_operator_mutation,
            "latest_artifact_present": latest_artifact is not None,
            "prioritize_artifact_over_build_guard": prioritize_artifact_over_build_guard,
        }

    def x_kernel_decision(self, raw_message: str) -> dict[str, Any]:
        try:
            return XDecisionKernel().decide(raw_message).to_dict()
        except Exception as exc:
            return {
                "intent": "kernel_error",
                "risk": "none",
                "route": "answer_only",
                "summary": str(exc),
                "requires_confirmation": False,
                "command": [],
                "package_action": "none",
                "reasons": ["x_kernel_exception"],
            }

    def auto_memory_decision(
        self,
        raw_message: str,
        *,
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        decision: MemoryDecision = self.memory_auto_pilot.intake(
            raw_message,
            session_metadata=session_metadata,
            active_records=self.persistent_memory_manager.list_active_memories(),
        )
        candidate = getattr(decision, "candidate", None)
        signal = getattr(decision, "signal", None)
        state = getattr(decision, "state", None)
        return {
            "state": getattr(state, "value", str(state or "")),
            "signal": getattr(signal, "value", str(signal or "")),
            "has_candidate": candidate is not None,
        }

    def speech_act(self, raw_message: str) -> str:
        return self.classify_speech_act(raw_message)

    def active_focus_instruction(self, raw_message: str) -> str | None:
        return self.extract_active_focus_instruction(raw_message)

    def is_active_focus_candidate(self, raw_message: str) -> bool:
        return self.active_focus_candidate_checker(raw_message)

    def is_runtime_status_request(self, raw_message: str) -> bool:
        normalized = self.normalize_text(raw_message)
        if self.is_runtime_clock_question(raw_message):
            return True
        return normalized in {
            "is the runtime healthy?",
            "is the runtime healthy",
            "are containers running?",
            "are containers running",
            "check the repo",
            "give me repo status",
            "repo status",
            "what is git status",
        }

    def is_operator_request(self, raw_message: str) -> bool:
        normalized = self.normalize_text(raw_message)
        if normalized == "/export sandbox":
            return False
        if raw_message.strip().startswith("/"):
            return True
        if self.operator_manager.is_first_class_operator_prompt(raw_message):
            return True
        if any(
            phrase in normalized
            for phrase in (
                "check the repo",
                "give me repo status",
                "repo status",
                "inspect repo branch",
                "what is git status",
                "what branch are we on",
                "is the working tree clean",
                "is the runtime healthy?",
                "is the runtime healthy",
                "what did you just check?",
                "what did you just check",
                "show the last operator receipt.",
                "show the last operator receipt",
                "show last operator receipt.",
                "show last operator receipt",
                "last operator receipt",
                "what is the gpu status",
                "gpu status",
                "what gpu am i running",
                "what gpus do i have",
                "how many drives do i have",
                "how many drives",
                "what drives do i have",
                "show me my drives",
                "scan gpu",
                "scan disk",
                "scan disks",
                "scan cpu",
                "what processor am i running",
                "are containers running",
                "can you delete files",
                "delete files",
                "commit it",
                "push it",
                "run it",
                "make it happen",
                "finish it",
                "do it",
                "implemente patch",
            )
        ):
            return True
        return normalized in {
            "run validation",
            "run the checks",
            "run checks",
            "what's failing",
            "what is failing",
            "fix the first failure",
            "fix first failure",
            "fix it",
        }

    def is_memory_context_request(self, raw_message: str) -> bool:
        normalized = self.normalize_text(raw_message)
        if normalized in {
            "what is my name?",
            "what is my name",
            "what are we working on right now?",
            "what are we working on right now",
            "what do you know is verified?",
            "what do you know is verified",
        }:
            return True
        if self.is_operator_request(raw_message):
            return False
        return (
            self.persistent_memory_manager.try_handle_chat(
                raw_message,
                session_metadata={},
            )
            is not None
        )
