from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from core.kernel.request_context import RequestContext


class KernelResolutionDependencies(Protocol):
    def artifact_mode_hints(
        self,
        normalized_message: str,
        *,
        session_messages: list[dict[str, Any]],
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]: ...

    def x_kernel_decision(self, raw_message: str) -> dict[str, Any]: ...

    def auto_memory_decision(
        self,
        raw_message: str,
        *,
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]: ...

    def speech_act(self, raw_message: str) -> str: ...

    def active_focus_instruction(self, raw_message: str) -> str | None: ...

    def is_active_focus_candidate(self, raw_message: str) -> bool: ...

    def is_runtime_status_request(self, raw_message: str) -> bool: ...

    def is_operator_request(self, raw_message: str) -> bool: ...

    def is_memory_context_request(self, raw_message: str) -> bool: ...


@dataclass(frozen=True)
class KernelModeResolution:
    mode: str
    reason: str
    executor: str
    diagnostics: dict[str, Any] = field(default_factory=dict)


class KernelModeResolver:
    PROTECTED_X_KERNEL_ROUTES = {"require_confirmation"}
    PROTECTED_X_KERNEL_INTENTS = {"system_control_request"}
    PROTECTED_X_KERNEL_RISKS = {"system_control", "destructive"}
    LEARNING_STATES = {
        "save_active",
        "save_pending_review",
        "ask_clarification",
        "reject_protected",
    }
    LEARNING_SPEECH_ACTS = {
        "user_correction",
        "communication_preference",
        "workflow_habit_learning",
        "hallucination_guard",
        "answer_style_preference",
        "diagnostic_rule",
    }

    def resolve(
        self,
        context: RequestContext,
        dependencies: KernelResolutionDependencies,
    ) -> KernelModeResolution:
        normalized = context.normalized_message
        artifact_hints = dependencies.artifact_mode_hints(
            normalized,
            session_messages=context.session_messages,
            session_metadata=context.session_metadata,
        )
        x_kernel_decision = dependencies.x_kernel_decision(context.raw_user_message)
        auto_memory = dependencies.auto_memory_decision(
            context.raw_user_message,
            session_metadata=context.session_metadata,
        )
        speech_act = dependencies.speech_act(context.raw_user_message)
        active_focus_instruction = dependencies.active_focus_instruction(
            context.raw_user_message
        )

        diagnostics = {
            "artifact_hints": artifact_hints,
            "x_kernel_decision": x_kernel_decision,
            "auto_memory": auto_memory,
            "speech_act": speech_act,
            "active_focus_instruction": active_focus_instruction,
        }

        artifact_mode = self._resolve_artifact_mode(artifact_hints)
        if self._is_learning_mode(
            auto_memory=auto_memory,
            speech_act=speech_act,
        ):
            return KernelModeResolution(
                mode="learning_preference",
                reason="learning_request_detected",
                executor="memory_learning_service",
                diagnostics=diagnostics,
            )

        if artifact_hints.get("force_implementation_guard"):
            return KernelModeResolution(
                mode="protected_confirmation",
                reason="implementation_repo_mutation_guard",
                executor="protected_confirmation_service",
                diagnostics=diagnostics,
            )

        if artifact_hints.get("force_operator_mutation"):
            return KernelModeResolution(
                mode="operator",
                reason="operator_mutation_request_detected",
                executor="operator_service",
                diagnostics=diagnostics,
            )

        if self._is_protected_confirmation(
            x_kernel_decision=x_kernel_decision,
            artifact_mode=artifact_mode,
        ):
            return KernelModeResolution(
                mode="protected_confirmation",
                reason="protected_confirmation_required",
                executor="protected_confirmation_service",
                diagnostics=diagnostics,
            )

        if artifact_hints.get("is_commit_lane_request") and artifact_mode is not None:
            return KernelModeResolution(
                mode=artifact_mode,
                reason="artifact_commit_lane_detected",
                executor="artifact_service",
                diagnostics=diagnostics,
            )
        if (
            context.normalized_message in {"verify it", "preview it"}
            and artifact_hints.get("is_artifact_request")
            and artifact_mode is not None
        ):
            return KernelModeResolution(
                mode=artifact_mode,
                reason="artifact_post_apply_shorthand_detected",
                executor="artifact_service",
                diagnostics=diagnostics,
            )
        if active_focus_instruction or dependencies.is_active_focus_candidate(
            context.raw_user_message
        ):
            return KernelModeResolution(
                mode="memory_context",
                reason="active_focus_request_detected",
                executor="context_service",
                diagnostics=diagnostics,
            )

        if self._is_active_focus_guided_follow_up(context):
            return KernelModeResolution(
                mode="memory_context",
                reason="active_focus_guided_follow_up",
                executor="context_service",
                diagnostics=diagnostics,
            )

        if self._is_explicit_operator_mode(context) and dependencies.is_operator_request(
            context.raw_user_message
        ):
            return KernelModeResolution(
                mode="operator",
                reason="explicit_operator_mode_request_detected",
                executor="operator_service",
                diagnostics=diagnostics,
            )

        if artifact_mode in {"build", "export"}:
            return KernelModeResolution(
                mode=artifact_mode,
                reason="sandbox_write_mode_detected",
                executor="artifact_service",
                diagnostics=diagnostics,
            )

        if dependencies.is_memory_context_request(context.raw_user_message):
            return KernelModeResolution(
                mode="memory_context",
                reason="memory_context_request_detected",
                executor="context_service",
                diagnostics=diagnostics,
            )

        if artifact_mode is not None:
            return KernelModeResolution(
                mode=artifact_mode,
                reason="artifact_mode_detected",
                executor="artifact_service",
                diagnostics=diagnostics,
            )

        if dependencies.is_operator_request(context.raw_user_message):
            return KernelModeResolution(
                mode="operator",
                reason="operator_request_detected",
                executor="operator_service",
                diagnostics=diagnostics,
            )

        if self._is_status_mode(
            context.raw_user_message,
            x_kernel_decision=x_kernel_decision,
            dependencies=dependencies,
        ):
            return KernelModeResolution(
                mode="status",
                reason="status_request_detected",
                executor="runtime_status_service",
                diagnostics=diagnostics,
            )

        if speech_act == "implementation_task":
            return KernelModeResolution(
                mode="coding",
                reason="implementation_task_detected",
                executor="chat_model_service",
                diagnostics=diagnostics,
            )

        if normalized in {
            "what is your name?",
            "what is your name",
            "whats your name?",
            "whats your name",
            "what's your name?",
            "what's your name",
            "your name?",
            "your name",
            "who is otis duncan?",
            "who is otis duncan",
            "what is xv7?",
            "what is xv7",
            "can you read github repos?",
            "can you read github repos",
        }:
            return KernelModeResolution(
                mode="unknown_safe_chat",
                reason="deterministic_identity_policy",
                executor="context_service",
                diagnostics=diagnostics,
            )

        return KernelModeResolution(
            mode="normal_chat",
            reason="default_safe_chat",
            executor="chat_model_service",
            diagnostics=diagnostics,
        )

    @staticmethod
    def _resolve_artifact_mode(artifact_hints: dict[str, Any]) -> str | None:
        if not isinstance(artifact_hints, dict):
            return None
        if artifact_hints.get("is_commit_lane_request"):
            return "artifact_revision"
        if artifact_hints.get("is_sandbox_build"):
            if artifact_hints.get("is_export_request"):
                return "export"
            return "build"
        if artifact_hints.get("is_refinement_request"):
            return "artifact_revision"
        if artifact_hints.get("is_artifact_request"):
            return "preview"
        return None

    def _is_protected_confirmation(
        self,
        *,
        x_kernel_decision: dict[str, Any],
        artifact_mode: str | None,
    ) -> bool:
        if artifact_mode in {"build", "export"}:
            return False
        route = str(x_kernel_decision.get("route") or "").strip().lower()
        intent = str(x_kernel_decision.get("intent") or "").strip().lower()
        risk = str(x_kernel_decision.get("risk") or "").strip().lower()
        requires_confirmation = bool(x_kernel_decision.get("requires_confirmation"))
        return (
            route in self.PROTECTED_X_KERNEL_ROUTES
            or intent in self.PROTECTED_X_KERNEL_INTENTS
            or risk in self.PROTECTED_X_KERNEL_RISKS
            or (
                requires_confirmation
                and artifact_mode not in {"preview", "artifact_revision"}
            )
        )

    def _is_learning_mode(
        self,
        *,
        auto_memory: dict[str, Any],
        speech_act: str,
    ) -> bool:
        state = str(auto_memory.get("state") or "").strip()
        if state in self.LEARNING_STATES:
            return True
        return speech_act in self.LEARNING_SPEECH_ACTS

    @staticmethod
    def _is_status_mode(
        raw_message: str,
        *,
        x_kernel_decision: dict[str, Any],
        dependencies: KernelResolutionDependencies,
    ) -> bool:
        if dependencies.is_runtime_status_request(raw_message):
            return True
        intent = str(x_kernel_decision.get("intent") or "").strip().lower()
        return intent in {"state", "diagnose", "readiness", "proof"}

    @staticmethod
    def _is_active_focus_guided_follow_up(context: RequestContext) -> bool:
        focus = context.session_metadata.get("active_focus")
        if not isinstance(focus, dict):
            return False
        summary = str(focus.get("summary", "")).lower()
        if not any(
            token in summary
            for token in ("communicat", "workflow", "habit", "otis", "operator")
        ):
            return False

        normalized = context.normalized_message
        return any(
            phrase in normalized
            for phrase in (
                "next steps",
                "what should we do next",
                "what are the next steps",
                "fluid communication",
                "better communication",
            )
        )

    @staticmethod
    def _is_explicit_operator_mode(context: RequestContext) -> bool:
        normalized = context.normalized_message
        return (
            context.operator_mode_enabled
            or normalized.startswith("operator mode:")
            or "github proof" in normalized
            or "github project" in normalized
        )
