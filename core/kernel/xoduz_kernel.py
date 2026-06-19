from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from core.api.schemas import AddMessageRequest
from core.kernel.execution_plan import ExecutionPlan
from core.kernel.mode_resolver import (
    KernelModeResolution,
    KernelModeResolver,
    KernelResolutionDependencies,
)
from core.kernel.request_context import RequestContext


ResolvedExecutor = Callable[
    [UUID, AddMessageRequest],
    Awaitable[Any],
]
KernelExecutor = Callable[
    [UUID, AddMessageRequest, str, dict[str, Any]],
    Awaitable[Any],
]
SessionLoader = Callable[[UUID], Awaitable[Any]]
Normalizer = Callable[[str], str]


@dataclass
class XoduzApplicationKernel:
    mode_resolver: KernelModeResolver
    resolution_dependencies: KernelResolutionDependencies
    execute_resolved: KernelExecutor
    load_session: SessionLoader
    normalize_message: Normalizer

    async def handle_request(
        self,
        session_id: UUID,
        payload: AddMessageRequest,
        *,
        source_channel: str = "session_message",
    ) -> Any:
        session_state = await self.load_session(session_id)
        session_messages = []
        if hasattr(session_state, "messages"):
            for message in getattr(session_state, "messages", []):
                model_dump = getattr(message, "model_dump", None)
                if callable(model_dump):
                    session_messages.append(model_dump(mode="json"))
                else:
                    session_messages.append(dict(getattr(message, "metadata", {})))

        context = RequestContext(
            raw_user_message=payload.raw_text,
            normalized_message=self.normalize_message(payload.raw_text),
            session_id=session_id,
            operator_mode_enabled=bool(
                payload.operator_mode
                or getattr(session_state, "metadata", {}).get(
                    "operator_mode_enabled", False
                )
            ),
            source_channel=source_channel,
            request_metadata={},
            session_metadata=dict(getattr(session_state, "metadata", {})),
            session_messages=session_messages,
        )
        resolution = self.mode_resolver.resolve(context, self.resolution_dependencies)
        plan = self._build_plan(context, resolution)
        return await self.execute_resolved(
            session_id,
            payload,
            resolution.mode,
            self._plan_metadata(plan, resolution),
        )

    @staticmethod
    def _build_plan(
        context: RequestContext,
        resolution: KernelModeResolution,
    ) -> ExecutionPlan:
        return ExecutionPlan(
            mode=resolution.mode,
            executor=resolution.executor,
            request_context=context,
            selected_model_path=(
                "coding" if resolution.mode == "coding" else "chat"
            ),
            safety_decision=(
                "protected_confirmation_required"
                if resolution.mode == "protected_confirmation"
                else "operator_safe_gate"
                if resolution.mode == "operator"
                else "sandbox_write_guard"
                if resolution.mode in {"build", "export"}
                else "preview_only"
                if resolution.mode in {"preview", "artifact_revision"}
                else "allowed"
            ),
            receipt_requirements=["context_receipt", "policy_provenance"],
            diagnostics=resolution.diagnostics,
        )

    @staticmethod
    def _plan_metadata(
        plan: ExecutionPlan,
        resolution: KernelModeResolution,
    ) -> dict[str, Any]:
        return {
            "mode": plan.mode,
            "executor": plan.executor,
            "selected_model_path": plan.selected_model_path,
            "safety_decision": plan.safety_decision,
            "expected_result_shape": plan.expected_result_shape,
            "receipt_requirements": list(plan.receipt_requirements),
            "reason": resolution.reason,
            "diagnostics": resolution.diagnostics,
        }
