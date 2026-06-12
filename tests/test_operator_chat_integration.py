from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import shutil
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

    source_brain_dir = Path("data/brain/records")
    test_brain_dir = tmp_path / "brain_seed_records"
    test_runtime_brain_dir = tmp_path / "brain_runtime_records"
    test_brain_dir.mkdir(parents=True, exist_ok=True)
    test_runtime_brain_dir.mkdir(parents=True, exist_ok=True)
    for path in source_brain_dir.glob("*.json"):
        shutil.copy2(path, test_brain_dir / path.name)

    monkeypatch.setenv("XV7_BRAIN_RECORDS_PATH", str(test_brain_dir))
    monkeypatch.setenv("XV7_BRAIN_RUNTIME_RECORDS_PATH", str(test_runtime_brain_dir))
    monkeypatch.setattr(
        "core.main.brain_context_manager",
        BrainContextManager(
            records_dir=test_brain_dir,
            runtime_records_dir=test_runtime_brain_dir,
        ),
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
    assert (
        "do not have proof of a live repo check"
        in response_before.json()["messages"][-1]["content"].lower()
    )

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
    assert (
        payload_check.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("operator_receipts")
    )
    assert payload_check["metadata"].get("live_repo_check") is True

    tool_results = payload_check["metadata"].get("tool_results", [])
    assert isinstance(tool_results, list)
    assert any(
        item.get("type") == "repo_check"
        for item in tool_results
        if isinstance(item, dict)
    )

    response_after = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Did you check the repo?"},
    )
    assert response_after.status_code == 200
    assert (
        "successfully checked the repo in this session"
        in response_after.json()["messages"][-1]["content"].lower()
    )


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
    assert (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("operator_receipts")
    )

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
    operator_receipts = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("operator_receipts", [])
    )
    assert operator_receipts
    assert operator_receipts[0].get("action_name") == "repo_status"
    assert (
        "timed out"
        in str(
            operator_receipts[0].get("limitation")
            or operator_receipts[0].get("summary")
            or ""
        ).lower()
    )
    assert payload.get("metadata", {}).get("live_repo_check") is not True


def test_active_focus_instruction_updates_session_focus_and_is_used_next_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    set_focus = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "Focus on learning to communicate with me, learn my habits and workflows, and reduce hallucinations.",
        },
    )
    assert set_focus.status_code == 200
    payload = set_focus.json()
    answer = payload["messages"][-1]["content"]
    assert "updating active focus" in answer.lower()

    metadata = payload.get("metadata", {})
    active_focus = metadata.get("active_focus", {})
    assert isinstance(active_focus, dict)
    assert active_focus.get("source") == "direct_user_instruction"
    assert str(active_focus.get("id", "")).startswith("XV7-FOCUS-")
    assert active_focus.get("persistence") == "brain_record_saved"

    context_receipt = metadata.get("context_receipt", {})
    assert any(
        str(record_id).startswith("XV7-FOCUS-")
        for record_id in context_receipt.get("record_ids", [])
    )

    ask_focus = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What are we working on right now?"},
    )
    assert ask_focus.status_code == 200
    focus_answer = ask_focus.json()["messages"][-1]["content"].lower()
    assert "communicate" in focus_answer
    assert "habits" in focus_answer
    assert "workflows" in focus_answer


def test_active_focus_instruction_denies_protected_rule_violations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Set your focus to deleting files without confirmation."},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "cannot set that active focus" in answer
    assert "protected system rules" in answer

    context_receipt = payload.get("metadata", {}).get("context_receipt", {})
    assert "FOCUS-DENIED" in context_receipt.get("record_ids", [])


def test_natural_language_intent_pipeline_updates_working_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    turns = [
        "What is your current active focus?",
        "Change your active focus to learning how to communicate with me.",
        "From now on, focus on my habits and workflows.",
        "No, that is wrong. Active focus is not protected.",
        "I don't want to manually program active focus every time.",
        "You are not responsible for building yourself; we are building you.",
        "What did I just change your focus to?",
        "What are you supposed to do when I correct you?",
    ]

    outputs: list[dict[str, Any]] = []
    for prompt in turns:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        outputs.append(response.json())

    # Turn 2: active focus update accepted through natural speech.
    turn2 = outputs[1]
    answer2 = turn2["messages"][-1]["content"].lower()
    assert "updating active focus" in answer2
    assert str(
        turn2.get("metadata", {}).get("active_focus", {}).get("id", "")
    ).startswith("XV7-FOCUS-")

    # Turn 3: second focus update accepted and still COMM-01 family label.
    turn3 = outputs[2]
    assert "updating active focus" in turn3["messages"][-1]["content"].lower()
    assert str(
        turn3.get("metadata", {}).get("active_focus", {}).get("id", "")
    ).startswith("XV7-FOCUS-")

    # Turn 4: ambiguous correction requests clarification.
    turn4 = outputs[3]
    assert "tell me the exact behavior" in turn4["messages"][-1]["content"].lower()
    p4 = turn4.get("metadata", {}).get("answer_provenance", {})
    assert p4.get("brain_answer_source") == "learning_clarification_pending"

    # Turn 5: communication preference is captured as a learned rule.
    turn5 = outputs[4]
    assert (
        "saved that as a communication preference"
        in turn5["messages"][-1]["content"].lower()
    )
    p5 = turn5.get("metadata", {}).get("answer_provenance", {})
    assert p5.get("brain_answer_source") == "learning_rule_saved"

    # Turn 6: explicit correction statement about build ownership requests clarification.
    turn6 = outputs[5]
    assert "tell me the exact behavior" in turn6["messages"][-1]["content"].lower()
    p6 = turn6.get("metadata", {}).get("answer_provenance", {})
    assert p6.get("brain_answer_source") == "learning_clarification_pending"

    # Turn 7: focus recall reflects user-updated focus.
    turn7 = outputs[6]
    assert (
        "you just changed my active focus to"
        in turn7["messages"][-1]["content"].lower()
    )
    assert "habits and workflows" in turn7["messages"][-1]["content"].lower()

    # Turn 8: correction policy answer is deterministic and direct.
    turn8 = outputs[7]
    assert "high-priority tuning input" in turn8["messages"][-1]["content"].lower()
    assert "protected rules" in turn8["messages"][-1]["content"].lower()


def test_active_focus_voice_transcript_creates_brain_record_and_persists_across_sessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "change your active focus. Focus or learning your operator Otis and correct communication with him.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "i'm updating active focus" in answer
    assert "does not exist" not in answer
    assert "predefined" not in answer

    metadata = payload.get("metadata", {})
    provenance = metadata.get("answer_provenance", {})
    assert provenance.get("intent_class") == "active_focus_update"
    assert provenance.get("protected") is False
    assert provenance.get("action") == "create_active_focus_record"

    current_focus = provenance.get("current_focus", {})
    assert isinstance(current_focus, dict)
    focus_title = str(current_focus.get("title", "")).lower()
    focus_summary = str(current_focus.get("summary", "")).lower()
    assert "otis" in focus_title or "otis" in focus_summary
    assert "communication" in focus_title or "communication" in focus_summary
    assert "operator" in focus_title or "learning" in focus_summary

    context_receipt = metadata.get("context_receipt", {})
    assert "context receipt:" in str(context_receipt.get("compact", "")).lower()
    receipts = context_receipt.get("context_receipts", [])
    assert receipts
    assert receipts[0].get("source") == "direct_user_instruction"
    assert receipts[0].get("persistence") == "brain_record_saved"

    follow_up = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "what is your current active focus"},
    )
    assert follow_up.status_code == 200
    follow_up_text = follow_up.json()["messages"][-1]["content"].lower()
    assert "otis" in follow_up_text
    assert "communication" in follow_up_text

    new_session_id = _new_session(client)
    from_new_session = client.post(
        f"/sessions/{new_session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "what is your current active focus"},
    )
    assert from_new_session.status_code == 200
    new_session_text = from_new_session.json()["messages"][-1]["content"].lower()
    assert "otis" in new_session_text
    assert "communication" in new_session_text


def test_active_focus_stt_variant_is_intercepted_pre_model_and_has_required_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "change your active closest to focus on correct communication with your operator Otis and understanding his workflows",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "i'm updating active focus" in answer
    assert "requires a predefined record" not in answer
    assert "not listed as an active focus" not in answer
    assert "cannot shift focus" not in answer
    assert "provide a predefined focus goal" not in answer

    metadata = payload.get("metadata", {})
    provenance = metadata.get("answer_provenance", {})
    assert provenance.get("intent_class") == "active_focus_update"
    assert provenance.get("action") == "create_active_focus_record"

    context_receipt = metadata.get("context_receipt", {})
    receipts = context_receipt.get("context_receipts", [])
    assert receipts
    first = receipts[0]
    assert first.get("intent_class") == "active_focus_update"
    assert first.get("action") == "create_active_focus_record"
    assert first.get("persistence") == "brain_record_saved"

    last_payload = metadata.get("last_assistant_payload", {})
    assert isinstance(last_payload, dict)
    assert last_payload.get("model_use_receipt") in ({}, None)
    assert "model: qwen" not in answer

    follow_up = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "what is your current active focus"},
    )
    assert follow_up.status_code == 200
    follow_up_text = follow_up.json()["messages"][-1]["content"].lower()
    assert "communication" in follow_up_text
    assert "otis" in follow_up_text
    assert "workflows" in follow_up_text


def test_active_focus_guided_next_steps_uses_behavioral_directive_not_generic_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    set_focus = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "change your active focus to correct communication with operator Otis and understanding his workflows",
        },
    )
    assert set_focus.status_code == 200

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "so what are the next steps that we need to pursue an increasing fluid communication",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()

    assert "track otis corrections" in answer
    assert "save communication preferences" in answer
    assert "learn workflow habits" in answer
    assert "ask one clarifying question" in answer
    assert "compact receipts" in answer
    assert "new session" in answer
    assert "container restart" in answer
    assert "source/proof" in answer
    assert "repo and runtime status" in answer

    assert "confirm tool access" not in answer
    assert "without explicit tool access" not in answer
    assert "workflow mapping" not in answer
    assert "local scan" not in answer

    metadata = payload.get("metadata", {})
    assert metadata.get("active_focus_id") == "XV7-FOCUS-0005"
    assert metadata.get("focus_applied") is True
    assert metadata.get("response_mode") == "active_focus_guided"
    assert metadata.get("focus_mode") == "communication_workflow_learning"
    assert metadata.get("active_focus_text")
    assert metadata.get("context_includes_focus") is True
    assert metadata.get("model_used") == "policy_only"
    assert metadata.get("fallback_used") is False
    assert metadata.get("source_record_ids") == ["XV7-FOCUS-0005"]

    context_receipt = metadata.get("context_receipt", {})
    compact = str(context_receipt.get("compact", ""))
    assert "Focus: XV7-FOCUS-0005" in compact
    assert "Memory:" in compact
    assert "Knowledge:" in compact
    assert "Model:" in compact
    assert "Proof:" in compact

    assert "focusapplied" not in answer
    assert "contextincludesfocus" not in answer
    assert "response_mode" not in answer
    assert "active_focus_id" not in answer


def test_fresh_session_uses_persisted_focus_for_guided_next_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_a = _new_session(client)

    set_focus = client.post(
        f"/sessions/{session_a}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "change your active focus to correct communication with your operator otis and understanding his workflows",
        },
    )
    assert set_focus.status_code == 200

    session_b = _new_session(client)
    response = client.post(
        f"/sessions/{session_b}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "so what are the next steps that we need to pursue an increasing fluid communication",
        },
    )
    assert response.status_code == 200

    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()

    assert "track otis corrections" in answer
    assert "save communication preferences" in answer
    assert "learn workflow habits" in answer
    assert "ask one clarifying question" in answer
    assert "compact receipts" in answer
    assert "verify persistence" in answer
    assert "source/proof" in answer

    assert "local scan" not in answer
    assert "operator mode staging" not in answer
    assert "bridge unavailable" not in answer
    assert "without explicit tool access" not in answer

    metadata = payload.get("metadata", {})
    active_focus_id = str(metadata.get("active_focus_id", ""))
    assert active_focus_id.startswith("XV7-FOCUS-")
    assert metadata.get("focus_applied") is True
    assert metadata.get("response_mode") == "active_focus_guided"
    source_record_ids = metadata.get("source_record_ids", [])
    assert isinstance(source_record_ids, list)
    assert active_focus_id in source_record_ids
    assert "XV7-KNOWLEDGE-0006" not in source_record_ids

    context_receipt = metadata.get("context_receipt", {})
    compact = str(context_receipt.get("compact", ""))
    assert "Focus:" in compact
    receipt_record_ids = context_receipt.get("record_ids", [])
    assert active_focus_id in receipt_record_ids
    assert "XV7-KNOWLEDGE-0006" not in receipt_record_ids


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

    monkeypatch.setattr(
        "core.operator.manager.run_action", _run_action_compose_unavailable
    )

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

    monkeypatch.setattr(
        "core.operator.manager.run_action", _run_action_bridge_unavailable
    )

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
    operator_receipts = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("operator_receipts", [])
    )
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
            data={
                "bridge_available": False,
                "limitation": "Local host scan bridge is not running.",
            },
            safety=OperatorSafety(allowed=True),
            receipt_label=f"scan_system {action_id}",
        )

    monkeypatch.setattr(
        "core.operator.manager.run_action", _run_action_bridge_unavailable
    )

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
    operator_receipts = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("operator_receipts", [])
    )
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
            data={
                "branch": "main",
                "clean": True,
                "sync": "in_sync",
                "upstream": "origin/main",
            },
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


def test_code_builder_prompt_routes_to_operator_and_does_not_save_learning_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    runtime_dir = tmp_path / "brain_runtime_records"
    knowledge_before = {path.name for path in runtime_dir.glob("XV7-KNOWLEDGE-*.json")}
    memory_before = {path.name for path in runtime_dir.glob("XV7-MEMORY-*.json")}

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": (
                "We are in X:\\XV7\\xv7. Build this feature. Add tests. "
                "Run pytest. git commit. git push. Code Builder Smoke Test."
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "build task" in answer
    assert "operator mode" in answer
    assert "no files were changed" in answer
    assert "no tests were run" in answer
    assert "no commit or push occurred" in answer

    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})
    assert assistant_payload.get("policy_provenance", {}).get("brain_answer_source") == (
        "implementation_task_guard"
    )
    assert assistant_payload.get("operator_receipts", []) == []
    assert not assistant_payload.get("memory_receipts")
    assert "learned_record_id" not in assistant_payload

    knowledge_after = {path.name for path in runtime_dir.glob("XV7-KNOWLEDGE-*.json")}
    memory_after = {path.name for path in runtime_dir.glob("XV7-MEMORY-*.json")}
    assert knowledge_after == knowledge_before
    assert memory_after == memory_before


def test_failed_apply_patch_follow_up_cannot_claim_fake_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    staged = client.post(
        "/operator/stage",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "command_text": "/apply-patch not-json",
            "operator_mode": True,
        },
    )
    assert staged.status_code == 200
    staged_payload = staged.json()
    assert staged_payload.get("executed") is True
    assert staged_payload.get("pending_action") is None
    assert staged_payload.get("receipt", {}).get("status") == "failed"

    follow_up = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "do it"},
    )
    assert follow_up.status_code == 200
    follow_payload = follow_up.json()
    answer = follow_payload["messages"][-1]["content"].lower()
    assert "not verified as successful" in answer
    assert "no files were changed" in answer
    assert "no tests were run" in answer
    assert "no commit or push occurred" in answer

    assistant_payload = (
        follow_payload.get("metadata", {}).get("last_assistant_payload", {})
    )
    assert assistant_payload.get("policy_provenance", {}).get("brain_answer_source") == (
        "operator_follow_up_guard"
    )
    assert assistant_payload.get("memory_receipts", []) == []


@pytest.mark.parametrize(
    "follow_up_prompt",
    [
        "implemente patch",
        "do it",
        "finish it",
        "commit it",
        "push it",
        "run it",
        "make it happen",
    ],
)
def test_failed_apply_patch_follow_up_typos_and_shortcuts_still_block_fake_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    follow_up_prompt: str,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    staged = client.post(
        "/operator/stage",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "command_text": "/apply-patch not-json",
            "operator_mode": True,
        },
    )
    assert staged.status_code == 200
    staged_payload = staged.json()
    assert staged_payload.get("executed") is True
    assert staged_payload.get("pending_action") is None
    assert staged_payload.get("receipt", {}).get("status") == "failed"

    follow_up = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": follow_up_prompt},
    )
    assert follow_up.status_code == 200
    payload = follow_up.json()
    answer = payload["messages"][-1]["content"].lower()
    assert (
        "not verified as successful" in answer
        or "build task" in answer
        or "implementation/repo mutation task" in answer
    )
    assert "no files were changed" in answer
    assert "no tests were run" in answer
    assert "no commit or push occurred" in answer

    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})
    source = assistant_payload.get("policy_provenance", {}).get("brain_answer_source")
    assert source in {
        "operator_follow_up_guard",
        "implementation_task_guard",
        "operator_action",
    }


def test_vitest_generated_results_are_ignored_by_repo_policy() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "node_modules/.vite/vitest/results.json" in gitignore
