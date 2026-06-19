from conversation_quality_support import *  # noqa: F401,F403

def test_commit_proposal_on_clean_repo_returns_clear_message(
    monkeypatch, tmp_path: Path
) -> None:
    # No applied patch in session: falls back to generic git status scan
    _init_git_repo(tmp_path)
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "prepare commit"},
    )
    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "did not find any safe changes" in answer
    proposal = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("commit_proposal", {})
    )
    assert proposal.get("type") == "commit_proposal"
    assert proposal.get("included_files") == []
    assert proposal.get("committed") is False

def test_commit_proposal_with_applied_patch_includes_untracked_target(
    monkeypatch, tmp_path: Path
) -> None:
    # Applied patch exists in session → commit proposal includes the patch target directly
    _init_git_repo(tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    gen = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert gen.status_code == 200

    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200
    apply_payload = apply_resp.json()
    applied_target = apply_payload["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]["target_path"]
    assert (tmp_path / applied_target).exists()

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "prepare commit"},
    )
    assert proposal_resp.status_code == 200
    proposal_payload = proposal_resp.json()
    answer = proposal_payload["messages"][-1]["content"].lower()
    assert "commit proposal" in answer or "prepared" in answer
    proposal = proposal_payload["messages"][-1]["metadata"]["commit_proposal"]
    assert proposal.get("type") == "commit_proposal"
    assert applied_target in proposal.get("included_files", []), (
        f"expected {applied_target!r} in included_files; got {proposal.get('included_files')}"
    )
    assert proposal.get("committed") is False
    assert proposal.get("push_performed") is False

def test_commit_proposal_applied_patch_no_diff_returns_no_diff_message(
    monkeypatch, tmp_path: Path
) -> None:
    # Applied patch target exists and is already committed → git shows no diff
    _init_git_repo(tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    gen = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert gen.status_code == 200
    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200
    applied_target = apply_resp.json()["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]["target_path"]
    target_abs = tmp_path / applied_target

    # Commit the file so git shows no diff
    subprocess.run(
        ["git", "add", str(target_abs)], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "pre-test commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "prepare commit"},
    )
    assert proposal_resp.status_code == 200
    answer = proposal_resp.json()["messages"][-1]["content"].lower()
    assert "does not show a diff" in answer or "nothing to commit" in answer

def test_commit_proposal_ignored_path_returns_ignored_diagnostic(
    monkeypatch, tmp_path: Path
) -> None:
    # Applied patch target is gitignored → clear diagnostic returned
    _init_git_repo(tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))

    # Add a .gitignore that ignores generated-sites
    (tmp_path / ".gitignore").write_text("generated-sites/\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "add gitignore"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    gen = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert gen.status_code == 200
    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "prepare commit"},
    )
    assert proposal_resp.status_code == 200
    answer = proposal_resp.json()["messages"][-1]["content"].lower()
    assert "excluded by .gitignore" in answer or "ignored" in answer

def test_push_it_is_refused(monkeypatch, tmp_path: Path) -> None:
    # "push it" must hit the follow-up guard regardless of session state
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "push it"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert (
        "no commit or push occurred" in answer or "not verified as successful" in answer
    )

def test_commit_proposal_and_approval_with_applied_patch(
    monkeypatch, tmp_path: Path
) -> None:
    # Full flow: apply patch → prepare commit → commit it
    _init_git_repo(tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    gen = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert gen.status_code == 200
    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200
    applied_target = apply_resp.json()["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]["target_path"]

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "prepare commit"},
    )
    assert proposal_resp.status_code == 200
    proposal = proposal_resp.json()["messages"][-1]["metadata"]["commit_proposal"]
    assert applied_target in proposal.get("included_files", [])
    assert proposal.get("committed") is False

    commit_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "commit it"},
    )
    assert commit_resp.status_code == 200
    commit_answer = commit_resp.json()["messages"][-1]["content"].lower()
    assert "no push was performed" in commit_answer
    committed = commit_resp.json()["messages"][-1]["metadata"]["commit_proposal"]
    assert committed.get("committed") is True
    assert committed.get("push_performed") is False
    assert committed.get("commit_sha")

    # Applied file should be tracked now
    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert log == committed.get("proposed_commit_message")

def test_commit_proposal_excludes_blocked_paths_and_commits_only_safe_files(
    monkeypatch, tmp_path: Path
) -> None:
    _init_git_repo(tmp_path)
    (tmp_path / "notes.txt").write_text("local notes\n", encoding="utf-8")
    blocked_log = tmp_path / "runtime" / "logs" / "debug.log"
    blocked_log.parent.mkdir(parents=True, exist_ok=True)
    blocked_log.write_text("do not commit\n", encoding="utf-8")

    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "prepare commit"},
    )
    assert proposal_resp.status_code == 200
    proposal_payload = proposal_resp.json()
    proposal = proposal_payload["messages"][-1]["metadata"]["commit_proposal"]
    assert proposal.get("type") == "commit_proposal"
    assert proposal.get("included_files") == ["notes.txt"]
    assert "runtime/logs/debug.log" in proposal.get("excluded_files", [])

    commit_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "commit it"},
    )
    assert commit_resp.status_code == 200
    commit_payload = commit_resp.json()
    commit_answer = commit_payload["messages"][-1]["content"].lower()
    assert "no push was performed" in commit_answer
    committed = commit_payload["messages"][-1]["metadata"]["commit_proposal"]
    assert committed.get("committed") is True
    assert committed.get("push_performed") is False
    assert committed.get("commit_sha")

    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "?? runtime/logs/debug.log" in status.stdout
    assert "?? notes.txt" not in status.stdout
    log_message = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert log_message == committed.get("proposed_commit_message")

def test_commit_approval_without_pending_proposal_is_refused(
    monkeypatch, tmp_path: Path
) -> None:
    _init_git_repo(tmp_path)
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "commit it"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert "do not have a pending commit proposal" in answer

def test_refinement_still_works_after_patch_proposal(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    gen = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert gen.status_code == 200

    first_patch = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert first_patch.status_code == 200
    first_content = first_patch.json()["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]["content"]

    refine = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "change the colors to black and gold and make it more premium"
        },
    )
    assert refine.status_code == 200

    second_patch = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert second_patch.status_code == 200
    second_content = second_patch.json()["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]["content"]
    assert second_content != first_content

def test_sms_refusal_still_preserved_with_patch_lane(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    _use_fake_local_model(monkeypatch)
    session_id = _new_session(client)

    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )

    sms = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "send a text to John"},
    )
    assert sms.status_code == 200
    answer = sms.json()["messages"][-1]["content"].lower()
    assert "sms connector" in answer
