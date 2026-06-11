from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from core.main import app
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore
from core.operator.schema import OperatorActionResult, OperatorSafety
from core.runtime.schemas import SessionState


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError("B7 prompts should not hit model inference in these tests")

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


def _result(
    *, action_name: str, status: str, action_id: str, stderr_summary: str = ""
) -> OperatorActionResult:
    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        status=status,
        started_at=now,
        completed_at=now,
        command_or_operation="test operation",
        target="X:/XV7/xv7",
        stdout_summary="",
        stderr_summary=stderr_summary,
        exit_code=0 if status == "success" else 1,
        data={"branch": "main", "clean": True},
        safety=OperatorSafety(allowed=status != "denied"),
        receipt_label=f"{action_name} {action_id}",
    )


def _setup_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setattr("core.main.base_agent", _FailingAgent())

    memory_store = MemoryStore(records_dir=tmp_path / "memory_records")
    memory_manager = PersistentMemoryManager(store=memory_store)
    memory_manager.bootstrap_seed_records()
    monkeypatch.setattr("core.main.persistent_memory_manager", memory_manager)

    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories",
        _fake_query_similar_memories,
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )

    return TestClient(app)


def _new_session(client: TestClient) -> str:
    response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def test_repo_check_claim_requires_live_proof_and_flips_after_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response_before = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Did you check the repo?"},
    )
    assert response_before.status_code == 200
    assert "do not have proof of a live repo check" in response_before.json()["messages"][-1][
        "content"
    ].lower()

    def _run_action_success(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "repo_status"
        return _result(action_name="repo_status", status="success", action_id=action_id)

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_success)

    response_check = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )
    assert response_check.status_code == 200
    payload_check = response_check.json()
    answer_check = payload_check["messages"][-1]["content"]
    assert "Operator receipt:" not in answer_check
    assert payload_check.get("metadata", {}).get("last_assistant_payload", {}).get("operator_receipts")
    assert payload_check["metadata"].get("live_repo_check") is True

    tool_results = payload_check["metadata"].get("tool_results", [])
    assert isinstance(tool_results, list)
    assert any(item.get("type") == "repo_check" for item in tool_results if isinstance(item, dict))

    response_after = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Did you check the repo?"},
    )
    assert response_after.status_code == 200
    assert "successfully checked the repo in this session" in response_after.json()["messages"][-1][
        "content"
    ].lower()


def test_failed_operator_action_is_honest_and_includes_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_failed(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "repo_status"
        return _result(
            action_name="repo_status",
            status="failed",
            action_id=action_id,
            stderr_summary="git not available",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_failed)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"]
    assert "failed" in answer.lower()
    assert "git not available" in answer.lower()
    assert "Operator receipt:" not in answer
    assert payload.get("metadata", {}).get("last_assistant_payload", {}).get("operator_receipts")

    metadata = payload.get("metadata", {})
    assert metadata.get("live_repo_check") is not True


def test_timed_out_repo_check_returns_honest_failure_receipt_without_hanging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_timeout(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "repo_status"
        return _result(
            action_name="repo_status",
            status="failed",
            action_id=action_id,
            stderr_summary="limitation: repo status check timed out after 8s",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_timeout)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Check the repo."},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "failed" in answer
    assert "timed out" in answer
    operator_receipts = payload.get("metadata", {}).get("last_assistant_payload", {}).get("operator_receipts", [])
    assert operator_receipts
    assert operator_receipts[0].get("action_name") == "repo_status"
    assert "timed out" in str(operator_receipts[0].get("limitation") or operator_receipts[0].get("summary") or "").lower()
    assert payload.get("metadata", {}).get("live_repo_check") is not True


def test_are_containers_running_does_not_fake_proof_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_compose_unavailable(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "scan_docker"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="scan_docker",
            status="failed",
            started_at=now,
            completed_at=now,
            command_or_operation="POST http://host.docker.internal:8765/scan/docker",
            target=str(repo_root),
            stdout_summary="",
            stderr_summary=(
                "Local host scan bridge is not running or unreachable. "
                "Start the local bridge service to enable host-level scans."
            ),
            exit_code=503,
            data={
                "bridge_available": False,
                "limitation": "Local host scan bridge is not running.",
            },
            safety=OperatorSafety(allowed=True),
            receipt_label=f"scan_docker {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_compose_unavailable)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Are containers running?"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "local host scan bridge" in answer.lower()
    assert "not running yet" in answer.lower()
    assert "Operator receipt:" not in answer


def test_processor_prompt_routes_to_scan_cpu_and_reports_bridge_unavailable_with_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_bridge_unavailable(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "scan_cpu"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="scan_cpu",
            status="failed",
            started_at=now,
            completed_at=now,
            command_or_operation="POST http://host.docker.internal:8765/scan/cpu",
            target=str(repo_root),
            stdout_summary="",
            stderr_summary=(
                "Local host scan bridge is not running or unreachable. "
                "Start the local bridge service to enable host-level scans."
            ),
            exit_code=503,
            data={
                "bridge_available": False,
                "limitation": "Local host scan bridge is not running.",
            },
            safety=OperatorSafety(allowed=True),
            receipt_label=f"scan_cpu {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_bridge_unavailable)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "what processor am i running"},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "local host scan bridge" in answer
    assert "not running yet" in answer
    assert "context required" not in answer
    assert "Operator receipt:" not in answer
    operator_receipts = payload.get("metadata", {}).get("last_assistant_payload", {}).get("operator_receipts", [])
    assert operator_receipts
    assert operator_receipts[0].get("action_name") == "scan_cpu"
    assert operator_receipts[0].get("status") == "failed"


def test_can_you_scan_my_system_routes_to_scan_system_and_not_context_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_bridge_unavailable(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "scan_system"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="scan_system",
            status="failed",
            started_at=now,
            completed_at=now,
            command_or_operation="POST http://host.docker.internal:8765/scan/system",
            target=str(repo_root),
            stdout_summary="",
            stderr_summary="Local host scan bridge is not running.",
            exit_code=503,
            data={"bridge_available": False, "limitation": "Local host scan bridge is not running."},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"scan_system {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_bridge_unavailable)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "can you scan my system"},
    )
    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "local host scan bridge" in answer
    assert "context required" not in answer
    operator_receipts = payload.get("metadata", {}).get("last_assistant_payload", {}).get("operator_receipts", [])
    assert operator_receipts
    assert operator_receipts[0].get("action_name") == "scan_system"


def test_operator_tools_available_includes_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_environment(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "operator_environment"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_environment",
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="operator environment diagnostics (read-only)",
            target=str(repo_root),
            stdout_summary="ok",
            stderr_summary="",
            exit_code=None,
            data={
                "repo_root": str(repo_root),
                "git_available": True,
                "docker_cli_available": False,
                "docker_socket_available": False,
                "service_url_config": {},
                "memory_store_path": "data/memory/records",
                "read_only_mode": True,
            },
            safety=OperatorSafety(allowed=True),
            receipt_label=f"operator_environment {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_environment)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What operator tools are available?"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "operator environment" in answer.lower()
    assert "Operator receipt:" not in answer


def test_working_tree_clean_prompt_routes_to_repo_status_not_mutation_deny(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action_repo_status(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "repo_status"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="repo_status",
            status="success",
            started_at=now,
            completed_at=now,
            command_or_operation="git status",
            target=str(repo_root),
            stdout_summary="ok",
            stderr_summary="",
            exit_code=0,
            data={"branch": "main", "clean": True, "sync": "in_sync", "upstream": "origin/main"},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"repo_status {action_id}",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action_repo_status)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Is the working tree clean?"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "denied" not in answer.lower()
    assert "Operator receipt:" not in answer
