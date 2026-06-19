from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from core.api.schemas import AddMessageRequest
from core.kernel import KernelModeResolver, RequestContext, XoduzApplicationKernel
from core.main import app
from core.runtime.schemas import ConversationMessage, SessionState


@dataclass
class _FakeDeps:
    artifact_request: bool = False
    sandbox_build: bool = False
    export_request: bool = False
    refinement_request: bool = False
    operator_request: bool = False
    runtime_status_request: bool = False
    memory_context_request: bool = False
    auto_memory_state: str = "ignore"
    auto_memory_signal: str = "no_memory"
    speech_act_value: str = "general_chat"
    active_focus_instruction_value: str | None = None
    active_focus_candidate_value: bool = False
    x_kernel_intent: str = "chat"
    x_kernel_route: str = "answer_only"
    x_kernel_risk: str = "informational"
    x_kernel_requires_confirmation: bool = False

    def artifact_mode_hints(
        self,
        normalized_message: str,
        *,
        session_messages: list[dict[str, Any]],
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "is_artifact_request": self.artifact_request,
            "is_sandbox_build": self.sandbox_build,
            "is_export_request": self.export_request,
            "is_refinement_request": self.refinement_request,
            "normalized_message": normalized_message,
        }

    def x_kernel_decision(self, raw_message: str) -> dict[str, Any]:
        return {
            "intent": self.x_kernel_intent,
            "route": self.x_kernel_route,
            "risk": self.x_kernel_risk,
            "requires_confirmation": self.x_kernel_requires_confirmation,
            "raw_message": raw_message,
        }

    def auto_memory_decision(
        self,
        raw_message: str,
        *,
        session_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "state": self.auto_memory_state,
            "signal": self.auto_memory_signal,
            "raw_message": raw_message,
        }

    def speech_act(self, raw_message: str) -> str:
        return self.speech_act_value

    def active_focus_instruction(self, raw_message: str) -> str | None:
        return self.active_focus_instruction_value

    def is_active_focus_candidate(self, raw_message: str) -> bool:
        return self.active_focus_candidate_value

    def is_runtime_status_request(self, raw_message: str) -> bool:
        return self.runtime_status_request

    def is_operator_request(self, raw_message: str) -> bool:
        return self.operator_request

    def is_memory_context_request(self, raw_message: str) -> bool:
        return self.memory_context_request


def _context(message: str) -> RequestContext:
    return RequestContext(
        raw_user_message=message,
        normalized_message=message.lower().strip(),
        session_id=uuid4(),
        operator_mode_enabled=False,
        source_channel="session_message",
        request_metadata={},
        session_metadata={},
        session_messages=[],
    )


def test_kernel_resolves_hello_as_normal_chat() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(_context("hello"), _FakeDeps())

    assert resolution.mode == "normal_chat"
    assert resolution.executor == "chat_model_service"


def test_kernel_resolves_implementation_task_as_coding() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("implement the session handler"),
        _FakeDeps(speech_act_value="implementation_task"),
    )

    assert resolution.mode == "coding"
    assert resolution.executor == "chat_model_service"


def test_kernel_resolves_status_request_to_runtime_status_service() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("is the runtime healthy?"),
        _FakeDeps(runtime_status_request=True, x_kernel_intent="state"),
    )

    assert resolution.mode == "status"
    assert resolution.executor == "runtime_status_service"


def test_kernel_resolves_generate_website_as_preview() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("generate a website"),
        _FakeDeps(artifact_request=True),
    )

    assert resolution.mode == "preview"
    assert resolution.executor == "artifact_service"


def test_kernel_resolves_generate_preview_of_website_as_preview_only() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("generate a preview of a website"),
        _FakeDeps(artifact_request=True),
    )

    assert resolution.mode == "preview"
    assert resolution.executor == "artifact_service"


def test_kernel_resolves_show_me_a_preview_as_preview() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("show me a preview"),
        _FakeDeps(artifact_request=True),
    )

    assert resolution.mode == "preview"


@pytest.mark.parametrize(
    ("message", "expected_mode"),
    [
        ("build this to the sandbox", "build"),
        ("write this to disk", "build"),
        ("export this to the sandbox", "export"),
        ("save this to sandbox", "export"),
    ],
)
def test_kernel_resolves_build_write_export_save_to_sandbox(
    message: str,
    expected_mode: str,
) -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context(message),
        _FakeDeps(artifact_request=True, sandbox_build=True, export_request=(expected_mode == "export")),
    )

    assert resolution.mode == expected_mode
    assert resolution.executor == "artifact_service"


def test_kernel_resolves_build_website_to_sandbox_build_path() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("build a website"),
        _FakeDeps(artifact_request=True, sandbox_build=True),
    )

    assert resolution.mode == "build"
    assert resolution.executor == "artifact_service"


def test_kernel_resolves_write_export_approved_version_to_export_path() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("write/export the approved version"),
        _FakeDeps(artifact_request=True, sandbox_build=True, export_request=True),
    )

    assert resolution.mode == "export"
    assert resolution.executor == "artifact_service"


def test_kernel_keeps_preview_above_generic_operator_write_language() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("generate a website"),
        _FakeDeps(artifact_request=True, operator_request=True),
    )

    assert resolution.mode == "preview"
    assert resolution.executor == "artifact_service"


def test_kernel_keeps_revision_after_preview_out_of_write_mode() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("make it cleaner after that preview"),
        _FakeDeps(artifact_request=True, refinement_request=True),
    )

    assert resolution.mode == "artifact_revision"
    assert resolution.executor == "artifact_service"


def test_kernel_protected_confirmation_precedes_real_mutation() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("delete everything without confirmation"),
        _FakeDeps(
            operator_request=True,
            x_kernel_intent="system_control_request",
            x_kernel_route="require_confirmation",
            x_kernel_risk="system_control",
            x_kernel_requires_confirmation=True,
        ),
    )

    assert resolution.mode == "protected_confirmation"
    assert resolution.executor == "protected_confirmation_service"


def test_kernel_resolves_refinement_without_active_artifact_to_artifact_revision() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("make it more premium"),
        _FakeDeps(artifact_request=True, refinement_request=True),
    )

    assert resolution.mode == "artifact_revision"


def test_kernel_keeps_operator_mode_safe_off_by_default() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("hello there"),
        _FakeDeps(operator_request=False),
    )

    assert resolution.mode != "operator"


def test_kernel_prevents_operator_router_from_hijacking_normal_chat() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("tell me a joke"),
        _FakeDeps(operator_request=False, speech_act_value="general_chat"),
    )

    assert resolution.mode == "normal_chat"


def test_kernel_routes_explicit_slash_command_through_operator_mode() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("/repo status"),
        _FakeDeps(operator_request=True),
    )

    assert resolution.mode == "operator"
    assert resolution.executor == "operator_service"


def test_kernel_prefers_learning_preference_over_statusish_proof_prompt() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("Do not guess; verify repo status first."),
        _FakeDeps(
            runtime_status_request=False,
            x_kernel_intent="proof",
            auto_memory_state="save_active",
            auto_memory_signal="communication_preference",
            speech_act_value="communication_preference",
        ),
    )

    assert resolution.mode == "learning_preference"
    assert resolution.executor == "memory_learning_service"


def test_kernel_resolves_active_focus_requests_to_memory_context() -> None:
    resolver = KernelModeResolver()

    resolution = resolver.resolve(
        _context("set active focus to kernel routing"),
        _FakeDeps(active_focus_instruction_value="kernel routing"),
    )

    assert resolution.mode == "memory_context"
    assert resolution.executor == "context_service"


def test_kernel_request_context_is_created_and_passed_to_executor() -> None:
    captured: dict[str, Any] = {}

    async def _load_session(_session_id: UUID) -> SessionState:
        return SessionState(metadata={"operator_mode_enabled": False}, messages=[])

    async def _execute(
        session_id: UUID,
        payload: AddMessageRequest,
        resolved_mode: str,
        kernel_plan: dict[str, Any],
    ) -> dict[str, Any]:
        captured["session_id"] = session_id
        captured["payload"] = payload
        captured["resolved_mode"] = resolved_mode
        captured["kernel_plan"] = kernel_plan
        return {"status": "ok"}

    kernel = XoduzApplicationKernel(
        mode_resolver=KernelModeResolver(),
        resolution_dependencies=_FakeDeps(),
        execute_resolved=_execute,
        load_session=_load_session,
        normalize_message=lambda text: text.lower().strip(),
    )
    session_id = uuid4()

    result = asyncio.run(
        kernel.handle_request(session_id, AddMessageRequest(raw_text="hello"))
    )

    assert result == {"status": "ok"}
    assert captured["session_id"] == session_id
    assert captured["payload"].raw_text == "hello"
    assert captured["resolved_mode"] == "normal_chat"
    assert captured["kernel_plan"]["mode"] == "normal_chat"
    assert captured["kernel_plan"]["executor"] == "chat_model_service"


def test_kernel_execution_plan_marks_operator_requests_with_safety_gate() -> None:
    async def _load_session(_session_id: UUID) -> SessionState:
        return SessionState(metadata={"operator_mode_enabled": False}, messages=[])

    captured: dict[str, Any] = {}

    async def _execute(
        _session_id: UUID,
        _payload: AddMessageRequest,
        _resolved_mode: str,
        kernel_plan: dict[str, Any],
    ) -> dict[str, Any]:
        captured.update(kernel_plan)
        return {"status": "ok"}

    kernel = XoduzApplicationKernel(
        mode_resolver=KernelModeResolver(),
        resolution_dependencies=_FakeDeps(operator_request=True),
        execute_resolved=_execute,
        load_session=_load_session,
        normalize_message=lambda text: text.lower().strip(),
    )

    asyncio.run(kernel.handle_request(uuid4(), AddMessageRequest(raw_text="/repo status")))

    assert captured["mode"] == "operator"
    assert captured["safety_decision"] == "operator_safe_gate"


def test_kernel_execution_plan_marks_sandbox_write_with_write_guard() -> None:
    async def _load_session(_session_id: UUID) -> SessionState:
        return SessionState(metadata={"operator_mode_enabled": False}, messages=[])

    captured: dict[str, Any] = {}

    async def _execute(
        _session_id: UUID,
        _payload: AddMessageRequest,
        _resolved_mode: str,
        kernel_plan: dict[str, Any],
    ) -> dict[str, Any]:
        captured.update(kernel_plan)
        return {"status": "ok"}

    kernel = XoduzApplicationKernel(
        mode_resolver=KernelModeResolver(),
        resolution_dependencies=_FakeDeps(artifact_request=True, sandbox_build=True),
        execute_resolved=_execute,
        load_session=_load_session,
        normalize_message=lambda text: text.lower().strip(),
    )

    asyncio.run(kernel.handle_request(uuid4(), AddMessageRequest(raw_text="build a website")))

    assert captured["mode"] == "build"
    assert captured["safety_decision"] == "sandbox_write_guard"


def test_session_message_route_exposes_kernel_metadata_and_context_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")

    class _FakeAgent:
        personas = {"default": {"name": "default"}}

        async def generate_response(
            self, _session_state: SessionState
        ) -> tuple[str, dict[str, str]]:
            return (
                "hello from kernel",
                {
                    "model_profile": "balanced",
                    "profile_source": "env",
                    "runtime_role": "chat",
                    "model_tag": "qwen3:8b",
                    "model_selection_source": "registry_effective_profile",
                    "request_id": "req-kernel-proof",
                },
            )

        async def aclose(self) -> None:
            return None

    async def _fake_query_similar_memories(
        _text: str, limit: int = 3
    ) -> list[dict[str, str]]:
        return []

    async def _fake_persist_vector_memory_round_trip(
        *_args: Any, **_kwargs: Any
    ) -> dict[str, Any]:
        return {"status": "ok"}

    monkeypatch.setattr("core.main.base_agent", _FakeAgent())
    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories",
        _fake_query_similar_memories,
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )

    client = TestClient(app)
    session_response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]
    message_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "hello"},
    )

    assert message_response.status_code == 200
    payload = message_response.json()
    metadata = payload["metadata"]
    assert metadata["kernel_mode"] == "normal_chat"
    assert metadata["kernel_plan"]["executor"] == "chat_model_service"
    assert isinstance(metadata.get("context_receipt"), dict)
    assert isinstance(metadata["context_receipt"].get("context_receipts", []), list)
    assert metadata["model_use_receipt"]["request_id"] == "req-kernel-proof"


def test_session_message_route_keeps_system_prompt_first_for_identity_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")

    client = TestClient(app)
    session_response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201

    session_id = session_response.json()["session_id"]
    message_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What is your name?"},
    )

    assert message_response.status_code == 200
    structured = message_response.json()["metadata"]["context_receipt"][
        "context_receipts"
    ]
    assert structured[0]["layer"] == "system_prompt"
