from operator_chat_integration_support import *  # noqa: F401,F403

@pytest.mark.parametrize(
    "prompt",
    [
        "Set active focus to testing website generation quality.",
        "Change active focus to website preview QA.",
        "Update your active focus: chat routing fixes.",
        "Make the active focus browser validation.",
        "Our focus right now is website generation quality.",
    ],
)
def test_natural_active_focus_updates_do_not_route_to_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    message = response.json()["messages"][-1]
    session_metadata = response.json()["metadata"]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]

    assert "updating active focus" in answer
    assert "artifact" not in answer
    assert metadata.get("policy_provenance", {}).get("intent_class") == (
        "active_focus_update"
    )
    assert (
        session_metadata.get("active_focus", {}).get("id", "").startswith("XV7-FOCUS-")
    )
    assert metadata.get("code_artifact", {}) == {}
    assert metadata.get("site_bundle", {}) == {}

@pytest.mark.parametrize(
    "prompt,expected_intent",
    [
        (
            "Correction: when I say generate a website, I mean preview only.",
            "user_correction",
        ),
        (
            "No, that is not what I meant. Treat generate as preview, not build.",
            "user_correction",
        ),
        (
            "Remember this workflow correction for website previews.",
            "workflow_habit_learning",
        ),
        (
            "Going forward, preview first, write files only when I say build or export.",
            "communication_preference",
        ),
    ],
)
def test_website_preview_corrections_save_as_learning_not_mutation_tasks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
    expected_intent: str,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    message = response.json()["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]

    assert "saved that as" in answer
    assert "implementation/repo mutation task" not in answer
    assert metadata.get("policy_provenance", {}).get("intent_class") == expected_intent
    assert metadata.get("policy_provenance", {}).get("brain_answer_source") == (
        "learning_rule_saved"
    )
    assert metadata.get("code_artifact", {}) == {}
    assert metadata.get("site_bundle", {}) == {}

def test_operator_mode_github_proof_prompt_with_mode_off_routes_to_operator_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
        assert action_name == "operator_github_proof_project"
        return _result(
            action_name=action_name,
            status="success",
            action_id=action_id,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": (
                "Operator Mode: Build and push a real GitHub proof project named earthx-github-proof under "
                "X:\\xoduz-sandbox\\earthx-github-proof. not a preview. not a patch."
            ),
            "operator_mode": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]

    assert "sandbox project workflow completed" in answer
    assert metadata.get("artifact_patch_proposal", {}) == {}
    assert (
        "artifact-patch-proposal"
        not in str(metadata.get("context_receipt", {})).lower()
    )

def test_operator_mode_github_proof_prompt_with_mode_on_routes_to_operator_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
        assert action_name == "operator_github_proof_project"
        return _result(
            action_name=action_name,
            status="success",
            action_id=action_id,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": (
                "Operator Mode: create a new repository on GitHub for this and push "
                "for real GitHub proof project earthx-github-proof"
            ),
            "operator_mode": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]

    assert "need one confirmation first" in answer
    assert "sandbox project path" in answer
    assert "github repo creation/push safely" in answer
    assert metadata.get("artifact_patch_proposal", {}) == {}
    receipts = metadata.get("operator_receipts") or []
    assert isinstance(receipts, list)
    assert receipts

def test_initialize_repo_and_push_routes_to_operator_not_learning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
        assert action_name == "operator_github_proof_project"
        return _result(
            action_name=action_name,
            status="pending",
            action_id=action_id,
            stderr_summary="I need the sandbox project path to continue safely.",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "initialize the new repository and push to github"},
    )

    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    metadata = message["metadata"]

    assert "saved that as" not in str(message["content"]).lower()
    assert metadata.get("policy_provenance", {}).get("intent_class") not in {
        "communication_preference",
        "workflow_habit_learning",
    }
    receipts = metadata.get("operator_receipts") or []
    assert isinstance(receipts, list)
    assert receipts

def test_slash_push_github_routes_to_operator_not_patch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
        assert action_name == "operator_github_proof_project"
        return _result(
            action_name=action_name,
            status="pending",
            action_id=action_id,
            stderr_summary="I need the sandbox project path to continue safely.",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "/push github"},
    )

    assert response.status_code == 200
    message = response.json()["messages"][-1]
    metadata = message["metadata"]
    assert metadata.get("artifact_patch_proposal", {}) == {}
    receipts = metadata.get("operator_receipts") or []
    assert receipts

def test_slash_export_sandbox_routes_to_build_flow_not_learning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _setup_client(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "/export sandbox"},
    )

    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    metadata = message["metadata"]
    answer = str(message["content"]).lower()

    assert "operator mode is currently off" not in answer
    assert metadata.get("policy_provenance", {}).get("intent_class") not in {
        "communication_preference",
        "workflow_habit_learning",
    }

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
        assert action_name == "operator_status_report"
        return _result(
            action_name="operator_status_report",
            status="success",
            action_id=action_id,
        )

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
        assert action_name == "operator_status_report"
        return _result(
            action_name="operator_status_report",
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
        assert action_name == "operator_status_report"
        return _result(
            action_name="operator_status_report",
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
    assert operator_receipts[0].get("action_name") == "operator_status_report"
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
