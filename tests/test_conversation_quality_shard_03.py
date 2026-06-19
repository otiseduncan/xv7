from conversation_quality_support import *  # noqa: F401,F403

def test_learning_rule_applies_to_future_answer_and_stays_hidden(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    learn = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "When I ask about CI status, check proof first and do not guess.",
        },
    )
    assert learn.status_code == 200

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What is the GitHub Actions status right now?"},
    )
    assert response.status_code == 200
    payload = response.json()

    answer = payload["messages"][-1]["content"]
    assert "require proof before claiming ci/github status" in answer.lower()
    assert "learned_record_id" not in answer
    assert "source_record_ids" not in answer

    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})
    assert assistant_payload.get("speech_act") == "learned_rule_applied"
    assert assistant_payload.get("learned_record_id")

def test_normal_preference_prompts_still_save_with_unique_memory_ids(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    first = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "I prefer concise updates unless I ask for details."},
    )
    assert first.status_code == 200
    first_payload = first.json().get("metadata", {}).get("last_assistant_payload", {})
    first_id = str(first_payload.get("learned_record_id", ""))
    assert first_id.startswith("XV7-MEMORY-")
    assert first_payload.get("learning_layer") == "memory"
    first_receipts = list(first_payload.get("memory_receipts", []))
    assert len(first_receipts) == len(set(first_receipts))

    second = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "Keep answers direct and short unless I ask for a deep dive."
        },
    )
    assert second.status_code == 200
    second_payload = second.json().get("metadata", {}).get("last_assistant_payload", {})
    second_id = str(second_payload.get("learned_record_id", ""))
    assert second_id.startswith("XV7-MEMORY-")
    assert second_payload.get("learning_layer") == "memory"
    second_receipts = list(second_payload.get("memory_receipts", []))
    assert len(second_receipts) == len(set(second_receipts))

    assert first_id != second_id

def test_patch_proposal_flow_from_active_artifact(monkeypatch, tmp_path: Path) -> None:
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

    patch = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert patch.status_code == 200
    payload = patch.json()
    proposal = payload["messages"][-1]["metadata"].get("artifact_patch_proposal", {})
    assert proposal.get("type") == "artifact_patch_proposal"
    assert proposal.get("target_path") == "generated-sites/soggy-doggy/index.html"
    assert proposal.get("applied") is False
    assert proposal.get("requires_confirmation") is True
    assert proposal.get("validation", {}).get("status") == "passed"
    assert not (tmp_path / "generated-sites" / "soggy-doggy" / "index.html").exists()

def test_generate_patch_without_artifact_returns_clear_message(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert (
        answer
        == "I do not have an active code artifact to turn into a patch yet. Generate or paste an artifact first."
    )

def test_apply_patch_requires_pending_proposal_in_session(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert response.status_code == 200
    assert (
        response.json()["messages"][-1]["content"]
        == "I do not have a pending patch proposal to apply."
    )

def test_apply_patch_writes_file_after_explicit_approval(
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

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert proposal_resp.status_code == 200
    proposal = proposal_resp.json()["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]
    target = tmp_path / str(proposal.get("target_path"))
    assert not target.exists()

    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200
    apply_payload = apply_resp.json()
    answer = apply_payload["messages"][-1]["content"].lower()
    assert "file written locally" in answer
    assert "no commit was created" in answer
    assert "no push was performed" in answer
    assert target.exists()
    assert target.read_text(encoding="utf-8") == proposal.get("content")

def test_failed_patch_validation_is_not_applied(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    def _fake_failed_proposal(_cls, *, artifact: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "artifact_patch_proposal",
            "proposal_id": "patch-failed-1",
            "source_artifact_id": str(artifact.get("revision_id") or "artifact:r1"),
            "filename": "index.html",
            "target_path": "generated-sites/soggy-doggy/index.html",
            "operation": "create",
            "language": "html",
            "applied": False,
            "requires_confirmation": True,
            "content": "<html><body>invalid</body></html>",
            "diff": "--- /dev/null\n+++ b/generated-sites/soggy-doggy/index.html\n",
            "validation": {
                "status": "failed",
                "checks": [
                    {
                        "name": "html_inline_css",
                        "status": "failed",
                        "detail": "missing inline css",
                    }
                ],
                "failures": ["html_inline_css: missing inline css"],
            },
        }

    monkeypatch.setattr(
        "core.brain.answer_contract.AnswerContract._build_patch_proposal_from_artifact",
        classmethod(_fake_failed_proposal),
    )

    gen = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert gen.status_code == 200

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert proposal_resp.status_code == 200
    proposal = proposal_resp.json()["messages"][-1]["metadata"][
        "artifact_patch_proposal"
    ]
    assert proposal.get("validation", {}).get("status") == "failed"

    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200
    answer = apply_resp.json()["messages"][-1]["content"].lower()
    assert "cannot apply this patch because validation failed" in answer
    assert not (tmp_path / "generated-sites" / "soggy-doggy" / "index.html").exists()

def test_verify_it_without_applied_patch_returns_clear_message(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "verify it"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert "do not have an applied patch to verify in this session" in answer

def test_post_apply_targeted_validation_flow_reports_success(
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

    proposal_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert proposal_resp.status_code == 200

    apply_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )
    assert apply_resp.status_code == 200

    verify_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "run validation"},
    )
    assert verify_resp.status_code == 200
    verify_payload = verify_resp.json()
    answer = verify_payload["messages"][-1]["content"].lower()
    assert "targeted validation passed" in answer
    proposal = verify_payload["messages"][-1]["metadata"].get(
        "artifact_patch_proposal", {}
    )
    assert proposal.get("targeted_validation", {}).get("status") == "passed"

def test_post_apply_verify_and_preview_prompts_route_to_artifact_lane(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
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
    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )

    verify_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "verify it"},
    )
    assert verify_resp.status_code == 200
    verify_payload = verify_resp.json()
    verify_answer = verify_payload["messages"][-1]["content"].lower()
    assert "post-apply verification passed" in verify_answer
    verify_proposal = verify_payload["messages"][-1]["metadata"].get(
        "artifact_patch_proposal", {}
    )
    assert verify_proposal.get("post_apply_verification", {}).get("status") == "passed"

    preview_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "preview it"},
    )
    assert preview_resp.status_code == 200
    preview_payload = preview_resp.json()
    preview_answer = preview_payload["messages"][-1]["content"].lower()
    assert "/generated-sites/soggy-doggy/index.html" in preview_answer
    assert (
        preview_payload["messages"][-1]["metadata"]
        .get("artifact_patch_proposal", {})
        .get("preview_path")
        == "/generated-sites/soggy-doggy/index.html"
    )

def test_post_apply_full_test_prompt_returns_guard_message(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    _use_fake_local_model(monkeypatch)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
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
    _ = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "apply patch"},
    )

    full_test_resp = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "run full tests"},
    )
    assert full_test_resp.status_code == 200
    payload = full_test_resp.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "did not run full tests automatically" in answer
    provenance = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("policy_provenance", {})
    )
    assert provenance.get("artifact_patch") == "full_test_guard"

def test_explicit_create_html_artifact_prompt_routes_to_artifact_generation(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)

    async def _fake_generate(
        self,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
    ) -> tuple[str, str, str]:
        return (
            AnswerContract._default_code_artifact_content(filename, language, question),
            "fake-code-model:test",
            "http://127.0.0.1:11434",
        )

    monkeypatch.setattr(
        "core.brain.answer_contract.AnswerContract._generate_artifact_with_local_model",
        _fake_generate,
    )

    session_id = _new_session(client)
    prompt = "create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors"
    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )
    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"])
    metadata = message["metadata"]
    artifact = metadata.get("code_artifact", {})
    content = str(artifact.get("content", "")).lower()
    provenance = metadata.get("policy_provenance", {})
    compact = str(metadata.get("context_receipt", {}).get("compact", ""))

    assert "build task" not in answer.lower()
    assert provenance.get("brain_answer_source") != "implementation_task_guard"
    assert "code-artifact-draft" in compact
    assert artifact.get("type") == "code_artifact"
    assert artifact.get("applied") is False
    assert "tony's tavern" in content
    assert "biker" in content and "bar" in content
    assert "black" in content or "#0" in content
    assert "orange" in content or "#f59e0b" in content or "#ea580c" in content
    assert "yellow" in content or "#facc15" in content or "#eab308" in content
    assert "soggy doggy" not in content
    assert "groom" not in content
    assert "white" not in content
    assert "purple" not in content
    assert "green" not in content
    assert not (tmp_path / "generated-sites").exists()

def test_build_wording_with_explicit_artifact_routes_to_artifact_generation(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)

    async def _fake_generate(
        self,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
    ) -> tuple[str, str, str]:
        return (
            AnswerContract._default_code_artifact_content(filename, language, question),
            "fake-code-model:test",
            "http://127.0.0.1:11434",
        )

    monkeypatch.setattr(
        "core.brain.answer_contract.AnswerContract._generate_artifact_with_local_model",
        _fake_generate,
    )

    session_id = _new_session(client)
    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "build an HTML artifact for Tony's Tavern biker bar using black orange and yellow"
        },
    )
    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]
    compact = str(metadata.get("context_receipt", {}).get("compact", ""))

    assert "build task" not in answer
    assert (
        metadata.get("policy_provenance", {}).get("brain_answer_source")
        != "implementation_task_guard"
    )
    assert metadata.get("code_artifact", {}).get("type") == "code_artifact"
    assert "code-artifact-draft" in compact
    assert not (tmp_path / "generated-sites").exists()

def test_natural_language_website_build_writes_to_sandbox(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path / "sandbox"))
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "build me a website for another business"},
    )
    assert response.status_code == 200
    payload = response.json()
    message = payload["messages"][-1]
    answer = str(message["content"]).lower()
    metadata = message["metadata"]
    assert "build task" not in answer
    assert (
        metadata.get("policy_provenance", {}).get("brain_answer_source")
        != "implementation_task_guard"
    )
    site_bundle = metadata.get("site_bundle", {})
    assert isinstance(site_bundle, dict)
    assert site_bundle.get("artifact_type") == "site_bundle"
    assert "sandbox_written_paths" in site_bundle
    assert (tmp_path / "sandbox").exists()

@pytest.mark.parametrize(
    "prompt",
    [
        "What makes a good website preview?",
        "How should a website preview be evaluated?",
        "Why are my generated websites looking like templates?",
        "What should we improve in the website builder?",
    ],
)
def test_conceptual_website_questions_do_not_generate_artifacts(
    monkeypatch, tmp_path: Path, prompt: str
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
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

    assert "website preview" in answer or "preview" in answer
    assert metadata.get("code_artifact", {}) == {}
    assert metadata.get("site_bundle", {}) == {}
    assert not (tmp_path / "generated-sites").exists()

@pytest.mark.parametrize(
    "prompt",
    [
        "generate a preview of a modern one-page website for Harrys Hot Dog Cart",
        "generate a website for Harrys Hot Dog Cart",
        "generate a website preview for Harrys Hot Dog Cart",
    ],
)
def test_website_preview_requests_create_visible_bundle_without_writing_files(
    monkeypatch, tmp_path: Path, prompt: str
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    metadata = response.json()["messages"][-1]["metadata"]
    site_bundle = metadata.get("site_bundle", {})
    assert isinstance(site_bundle, dict)
    assert site_bundle.get("artifact_type") == "site_bundle"
    assert site_bundle.get("artifact_id")
    assert site_bundle.get("entry") == "index.html"
    bundle_payload = site_bundle.get("site_bundle", {})
    assert isinstance(bundle_payload, dict)
    files = bundle_payload.get("files", [])
    assert isinstance(files, list)
    assert files
    html_files = [item for item in files if str(item.get("path", "")).endswith(".html")]
    css_files = [item for item in files if str(item.get("path", "")).endswith(".css")]
    assert html_files
    assert css_files
    assert all(str(item.get("content", "")).strip() for item in html_files)
    assert all(str(item.get("content", "")).strip() for item in css_files)
    assert metadata.get("code_artifact", {}) == {}
    assert not (tmp_path / "generated-sites").exists()

@pytest.mark.parametrize(
    "export_prompt",
    [
        "write this to the sandbox",
        "export this to the sandbox",
        "save this to the sandbox",
    ],
)
def test_explicit_site_bundle_export_phrases_write_only_to_temp_sandbox(
    monkeypatch, tmp_path: Path, export_prompt: str
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    build_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate a website for Harrys Hot Dog Cart"},
    )
    assert build_response.status_code == 200
    assert not (tmp_path / "generated-sites").exists()

    export_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": export_prompt},
    )

    assert export_response.status_code == 200
    export_answer = str(export_response.json()["messages"][-1]["content"]).lower()
    assert "applied" in export_answer
    assert "generated-sites/" in export_answer
    assert list((tmp_path / "generated-sites").rglob("*.html"))

def test_site_bundle_refine_then_export_to_sandbox(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    build_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate a website for Tony's Tavern biker bar"},
    )
    assert build_response.status_code == 200
    build_message = build_response.json()["messages"][-1]
    assert "build task" not in str(build_message["content"]).lower()
    build_bundle = build_message["metadata"].get("site_bundle", {})
    assert isinstance(build_bundle, dict)
    assert build_bundle.get("artifact_type") == "site_bundle"

    refine_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "change the website to a cleaner black and gold style"},
    )
    assert refine_response.status_code == 200
    refine_message = refine_response.json()["messages"][-1]
    refine_answer = str(refine_message["content"]).lower()
    assert "do not have a current code artifact" not in refine_answer
    assert "no active site bundle" not in refine_answer
    refine_bundle = refine_message["metadata"].get("site_bundle", {})
    assert isinstance(refine_bundle, dict)
    assert refine_bundle.get("artifact_type") == "site_bundle"

    export_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "write this to the sandbox"},
    )
    assert export_response.status_code == 200
    export_message = export_response.json()["messages"][-1]
    export_answer = str(export_message["content"]).lower()
    assert "applied" in export_answer
    assert "generated-sites/" in export_answer

    html_files = list((tmp_path / "generated-sites").rglob("*.html"))
    assert len(html_files) >= 2

def test_site_bundle_export_phrase_with_slashes_is_handled(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    build_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate a website for Tony's Tavern biker bar"},
    )
    assert build_response.status_code == 200

    export_response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Write/export/save it to the sandbox."},
    )
    assert export_response.status_code == 200
    export_message = export_response.json()["messages"][-1]
    export_answer = str(export_message["content"]).lower()
    assert "applied" in export_answer
    assert "generated-sites/" in export_answer

def test_build_guard_still_wins_when_commit_words_are_present(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "build me a website for Soggy Doggy and commit it"},
    )
    assert response.status_code == 200
    message = response.json()["messages"][-1]
    answer = message["content"].lower()
    assert "build task" in answer
    assert (
        message["metadata"].get("policy_provenance", {}).get("brain_answer_source")
        == "implementation_task_guard"
    )
    assert message["metadata"].get("code_artifact", {}) == {}
    assert not (tmp_path / "generated-sites").exists()

def test_repo_mutation_wording_still_hits_build_guard(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "create a website in the repo and commit it"},
    )
    assert response.status_code == 200
    message = response.json()["messages"][-1]
    answer = str(message["content"]).lower()
    assert "build task" in answer
    assert (
        message["metadata"].get("policy_provenance", {}).get("brain_answer_source")
        == "implementation_task_guard"
    )
    assert message["metadata"].get("code_artifact", {}) == {}
    assert not (tmp_path / "generated-sites").exists()

def test_back_to_back_create_artifact_preserves_code16_fidelity(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)

    async def _fake_generate(
        self,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
    ) -> tuple[str, str, str]:
        return (
            AnswerContract._default_code_artifact_content(filename, language, question),
            "fake-code-model:test",
            "http://127.0.0.1:11434",
        )

    monkeypatch.setattr(
        "core.brain.answer_contract.AnswerContract._generate_artifact_with_local_model",
        _fake_generate,
    )

    session_id = _new_session(client)
    soggy = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert soggy.status_code == 200

    tony = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors"
        },
    )
    assert tony.status_code == 200
    payload = tony.json()
    artifact = payload["messages"][-1]["metadata"]["code_artifact"]
    content = str(artifact.get("content", "")).lower()

    assert "tony's tavern" in content
    assert "biker" in content and "bar" in content
    assert "black" in content or "#0" in content
    assert "orange" in content or "#f59e0b" in content or "#ea580c" in content
    assert "yellow" in content or "#facc15" in content or "#eab308" in content
    assert "soggy doggy" not in content
    assert "groom" not in content
    assert "white" not in content
    assert "purple" not in content
    assert "green" not in content
