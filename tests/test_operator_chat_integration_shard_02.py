from operator_chat_integration_support import *  # noqa: F401,F403

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

@pytest.mark.parametrize(
    "prompt,expected_action",
    [
        ("inspect repo branch", "operator_status_report"),
        ("what is the gpu status", "scan_gpu"),
        ("how many drives do I have", "scan_disk"),
    ],
)
def test_live_status_prompts_route_to_operator_not_memory_learning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
    expected_action: str,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)
    runtime_dir = tmp_path / "brain_runtime_records"
    knowledge_before = {path.name for path in runtime_dir.glob("XV7-KNOWLEDGE-*.json")}
    memory_before = {path.name for path in runtime_dir.glob("XV7-MEMORY-*.json")}
    calls: list[str] = []

    def _run_action_status_or_bridge_unavailable(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        assert action_name == expected_action
        calls.append(action_name)
        now = datetime.now(UTC)
        if action_name == "operator_status_report":
            return OperatorActionResult(
                action_id=action_id,
                action_name=action_name,
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
                receipt_label=f"{action_name} {action_id}",
            )
        scan_name = "gpu" if action_name == "scan_gpu" else "disk"
        return OperatorActionResult(
            action_id=action_id,
            action_name=action_name,
            status="failed",
            started_at=now,
            completed_at=now,
            command_or_operation=(
                f"POST http://host.docker.internal:8765/scan/{scan_name}"
            ),
            target=str(repo_root),
            stdout_summary="",
            stderr_summary="Local host scan bridge is not running.",
            exit_code=503,
            data={
                "bridge_available": False,
                "bridge_url": "http://host.docker.internal:8765",
                "limitation": "Local host scan bridge is not running.",
            },
            safety=OperatorSafety(allowed=True),
            receipt_label=f"{action_name} {action_id}",
        )

    monkeypatch.setattr(
        "core.operator.manager.run_action", _run_action_status_or_bridge_unavailable
    )

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]

    assert calls == [expected_action]
    assert "got it" not in answer
    assert "keep that preference" not in answer
    assert "saved that as" not in answer
    assert metadata.get("policy_provenance", {}).get("intent_class") not in {
        "communication_preference",
        "workflow_habit_learning",
    }
    assert not metadata.get("memory_receipts")
    operator_receipts = metadata.get("operator_receipts") or []
    assert operator_receipts
    assert operator_receipts[0].get("action_name") == expected_action
    if expected_action in {"scan_gpu", "scan_disk"}:
        assert "local host scan bridge is not running" in answer
        assert "bridge url: http://host.docker.internal:8765" in answer

    knowledge_after = {path.name for path in runtime_dir.glob("XV7-KNOWLEDGE-*.json")}
    memory_after = {path.name for path in runtime_dir.glob("XV7-MEMORY-*.json")}
    assert knowledge_after == knowledge_before
    assert memory_after == memory_before

@pytest.mark.parametrize(
    "prompt,expected_fragment",
    [
        ("whats your name", "xoduz"),
        ("who is otis duncan", "otis duncan"),
        ("what is XV7", "xv7"),
        ("can you read github repos?", "github"),
    ],
)
def test_basic_policy_prompts_answer_without_model_or_vector_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
    expected_fragment: str,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    async def _fail_vector_memory_round_trip(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("identity policy answer should not persist vector memory")

    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fail_vector_memory_round_trip,
    )

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})

    assert expected_fragment in answer
    assert "failed" not in answer
    assert "timed out" not in answer
    assert "keep that preference" not in answer
    assert not assistant_payload.get("memory_receipts")
    assert payload.get("metadata", {}).get("model_used") == "policy_only"
    assert payload.get("metadata", {}).get("vector_memory", {}).get("status") == (
        "skipped"
    )

@pytest.mark.parametrize(
    "prompt",
    [
        "build a website Smokey Joe's CBD and vape using red grey and black colors",
        "generate a artifact Smokey Joe's CBD and vape using red grey and black colors",
    ],
)
def test_fresh_artifact_generation_prompts_do_not_require_active_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
) -> None:
    monkeypatch.setenv("XV7_SANDBOX_ROOT_WRITE", str(tmp_path / "sandbox"))
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]
    provenance = metadata.get("policy_provenance", {})

    assert "active artifact to refine" not in answer
    assert "generate or provide an artifact first" not in answer
    assert provenance.get("artifact_generation") != "artifact_refinement_unavailable"
    assert metadata.get("site_bundle") or metadata.get("code_artifact")

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
        assert action_name == "operator_status_report"
        now = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="operator_status_report",
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
            receipt_label=f"operator_status_report {action_id}",
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
    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})
    answer_source = assistant_payload.get("policy_provenance", {}).get(
        "brain_answer_source"
    )
    assert answer_source in {"implementation_task_guard", "operator_action"}

    if answer_source == "implementation_task_guard":
        assert "protected location" in answer
        assert "operator mode" in answer
        assert "no files were changed" in answer
        assert "no tests were run" in answer
        assert "no commit or push occurred" in answer
        assert assistant_payload.get("operator_receipts", []) == []
    else:
        assert "commit/push request requires explicit approval" in answer
        assert assistant_payload.get("operator_receipts", [])

    assert not assistant_payload.get("memory_receipts")
    assert "learned_record_id" not in assistant_payload

    knowledge_after = {path.name for path in runtime_dir.glob("XV7-KNOWLEDGE-*.json")}
    memory_after = {path.name for path in runtime_dir.glob("XV7-MEMORY-*.json")}
    assert knowledge_after == knowledge_before
    assert memory_after == memory_before

def test_build_task_stage_returns_plan_and_does_not_save_learning_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    runtime_dir = tmp_path / "brain_runtime_records"
    knowledge_before = {path.name for path in runtime_dir.glob("XV7-KNOWLEDGE-*.json")}
    memory_before = {path.name for path in runtime_dir.glob("XV7-MEMORY-*.json")}

    staged = client.post(
        "/operator/stage",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "session_id": session_id,
            "command_text": "/build-task Build a Code 9 endpoint with tests and validation steps",
            "operator_mode": True,
        },
    )
    assert staged.status_code == 200
    payload = staged.json()
    assert payload.get("executed") is True
    assert payload.get("pending_action") is None
    assert payload.get("receipt", {}).get("status") == "success"
    assert payload.get("receipt", {}).get("read_only") is True

    answer = str(payload.get("answer", "")).lower()
    assert "build plan" in answer
    assert "task summary:" in answer
    assert (
        "no files were changed. no tests were run. no commit or push occurred."
        in answer
    )
    assert "next valid operator step:" in answer

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

    assistant_payload = follow_payload.get("metadata", {}).get(
        "last_assistant_payload", {}
    )
    assert assistant_payload.get("policy_provenance", {}).get(
        "brain_answer_source"
    ) == ("operator_follow_up_guard")
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
    # "commit it" is now routed to the commit lane first; when there is no pending
    # commit proposal it returns a safe refusal rather than the generic operator guard
    # message, but no commit or push occurs either way.
    safe_refusals = (
        "not verified as successful",
        "protected location",
        "implementation/repo mutation task",
        "do not have a pending commit proposal",
    )
    assert any(phrase in answer for phrase in safe_refusals), (
        f"unexpected answer: {answer!r}"
    )
    if follow_up_prompt != "commit it":
        assert "no files were changed" in answer
        assert "no tests were run" in answer
        assert "no commit or push occurred" in answer
    else:
        # commit lane refusal does not include the generic guard boilerplate but
        # ensures nothing was committed or pushed by checking the proposal metadata.
        committed_proposal = (
            payload.get("metadata", {})
            .get("last_assistant_payload", {})
            .get("commit_proposal", {})
        )
        assert committed_proposal.get("committed", False) is False
        assert committed_proposal.get("push_performed", False) is False

    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})
    source = assistant_payload.get("policy_provenance", {}).get("brain_answer_source")
    if follow_up_prompt != "commit it":
        assert source in {
            "operator_follow_up_guard",
            "implementation_task_guard",
            "operator_action",
        }
    else:
        assert source in {
            "operator_follow_up_guard",
            "implementation_task_guard",
            "operator_action",
            "commit_proposal_request",
        }

def test_vitest_generated_results_are_ignored_by_repo_policy() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "node_modules/.vite/vitest/results.json" in gitignore
