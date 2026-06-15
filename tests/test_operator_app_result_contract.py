from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from core.brain.manager import BrainContextManager
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
        raise AssertionError("operator app proof prompts should not hit the model")

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
    monkeypatch.setattr(
        "core.main.brain_context_manager",
        BrainContextManager(records_dir=tmp_path / "brain_records"),
    )
    return TestClient(app)


def _new_session(client: TestClient) -> str:
    response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert response.status_code == 201
    return str(response.json()["session_id"])


def _operator_result(payload: dict[str, Any]) -> dict[str, Any]:
    assistant_payload = payload["metadata"]["last_assistant_payload"]
    result = assistant_payload.get("operator_result", {})
    assert isinstance(result, dict)
    return result


def _receipt(payload: dict[str, Any]) -> dict[str, Any]:
    receipts = payload["metadata"]["last_assistant_payload"].get(
        "operator_receipts", []
    )
    assert isinstance(receipts, list)
    assert receipts
    receipt = receipts[0]
    assert isinstance(receipt, dict)
    return receipt


def _result(
    *,
    action_name: str,
    action_id: str,
    repo_root: Path,
    status: str = "success",
    data: dict[str, Any] | None = None,
    stderr: str = "",
    read_only: bool = True,
    requires_approval: bool = False,
) -> OperatorActionResult:
    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        mode="read_only" if read_only else "operator",
        status=status,  # type: ignore[arg-type]
        started_at=now,
        completed_at=now,
        command_or_operation=f"fake {action_name}",
        target=str(repo_root),
        stdout_summary="fake summary",
        stderr_summary=stderr,
        exit_code=0 if status == "success" else 1,
        data=(data or {}) | {"commit_created": False, "push_performed": False},
        safety=OperatorSafety(
            allowed=status != "denied",
            read_only=read_only,
            mutates_files=not read_only,
            requires_approval=requires_approval,
            denial_reason=stderr if status == "denied" else None,
        ),
        receipt_label=f"{action_name} {action_id}",
    )


def test_check_repo_api_returns_operator_status_result_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "operator_status_report"
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            data={
                "branch": "code22/split-answer-contract",
                "clean": False,
                "sync": "in_sync",
                "local_only_files": [
                    "docker-compose.yml",
                    "docker-compose.local.diff",
                ],
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "check the repo"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = _operator_result(payload)
    receipt = _receipt(payload)
    assert result["action_name"] == "operator_status_report"
    assert result["status"] == "passed"
    assert result["commit_push_state"]["commit_created"] is False
    assert result["commit_push_state"]["push_performed"] is False
    assert "docker-compose.yml" in result["local_only_files_warning"]
    assert receipt["operator_result"] == result
    assert marker.read_text(encoding="utf-8") == "unchanged\n"


def test_run_validation_api_returns_allowlisted_command_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "operator_validation_report"
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            data={
                "passed": True,
                "selected_commands": [
                    "python -m ruff format --check core tests scripts",
                    "python -m ruff check core tests scripts",
                ],
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "run validation"},
    )

    assert response.status_code == 200
    result = _operator_result(response.json())
    assert result["action_name"] == "operator_validation_report"
    assert result["status"] == "passed"
    assert result["validation_commands_run"] == [
        "python -m ruff format --check core tests scripts",
        "python -m ruff check core tests scripts",
    ]
    assert result["commit_push_state"]["push_performed"] is False


def test_fix_it_api_without_patch_returns_needs_patch_not_fake_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "operator_repair_report"
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="failed",
            stderr="First validation failure: python -m pytest",
            data={
                "patch_required": True,
                "first_failure_command": "python -m pytest",
                "validation_commands_run": ["python -m pytest"],
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "fix it"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = _operator_result(payload)
    answer = payload["messages"][-1]["content"].lower()
    assert result["action_name"] == "operator_repair_report"
    assert result["status"] == "needs_patch"
    assert result["first_failure"] == "python -m pytest"
    assert "concrete approved patch is required" in answer
    assert result["commit_push_state"]["commit_created"] is False


def test_patch_apply_without_approval_api_returns_needs_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    patch = {"changes": [{"path": "core/demo.py", "content": "VALUE = 2\n"}]}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "operator_patch_report"
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="denied",
            stderr="Patch apply denied: repo mutation approval is required.",
            data={"changed_files": []},
            read_only=False,
            requires_approval=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": f"apply this patch {json.dumps(patch)}"},
    )

    assert response.status_code == 200
    result = _operator_result(response.json())
    assert result["action_name"] == "operator_patch_report"
    assert result["status"] == "needs_approval"
    assert result["changed_files"] == []
    assert "Repo mutation requires explicit approval." in result["safety_notes"]
    assert result["commit_push_state"]["push_performed"] is False


def test_website_prompt_api_stays_out_of_operator_lane(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path / "sandbox"))
    session_id = _new_session(client)

    def _run_action(*_args: Any, **_kwargs: Any) -> OperatorActionResult:
        raise AssertionError("website prompt should not route to operator action")

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Build me a multi-page website for Harry's Hot Dog Cart."},
    )

    assert response.status_code == 200
    assistant_payload = response.json()["metadata"]["last_assistant_payload"]
    assert assistant_payload.get("operator_receipts") == []
    assert assistant_payload.get("operator_result") == {}
    site_bundle = assistant_payload.get("site_bundle", {})
    assert site_bundle.get("artifact_type") == "site_bundle"
    assert site_bundle.get("sandbox_written_paths")
    assert (tmp_path / "sandbox").exists()


def test_commit_request_api_returns_operator_commit_result_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == "operator_commit_report"
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="denied",
            stderr="Commit approval is required before mutation.",
            data={
                "mode": "apply",
                "candidate_files": ["core/main.py"],
                "committed_files": [],
                "skipped_files": ["docker-compose.yml", ".env"],
                "commit_sha": "",
                "pushed": False,
                "local_only_files": ["docker-compose.yml", "docker-compose.local.diff"],
            },
            read_only=False,
            requires_approval=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "commit these changes"},
    )

    assert response.status_code == 200
    result = _operator_result(response.json())
    assert result["action_name"] == "operator_commit_report"
    assert result["status"] == "needs_approval"
    assert result["candidate_files"] == ["core/main.py"]
    assert result["committed_files"] == []
    assert "docker-compose.yml" in result["skipped_files"]
    assert result["commit_sha"] == ""
    assert result["pushed"] is False
    assert "docker-compose.yml" in result["local_only_files_warning"]
