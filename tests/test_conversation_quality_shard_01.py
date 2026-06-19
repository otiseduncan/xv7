from conversation_quality_support import *  # noqa: F401,F403

def test_missing_memory_answer_is_honest(monkeypatch, tmp_path: Path) -> None:
    records_dir = tmp_path / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "XV7-SYSTEM-0001.json",
        "XV7-FOCUS-0001.json",
        "XV7-KNOWLEDGE-0001.json",
        "XV7-VERIFIED-0001.json",
    ):
        source = Path("data/brain/records") / name
        (records_dir / name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    monkeypatch.setenv("XV7_BRAIN_RECORDS_PATH", str(records_dir))
    manager = BrainContextManager(records_dir=records_dir)
    answer = manager.answer_from_records("What do you remember?", session_metadata={})
    assert answer == "Missing required record: memory."

def test_verified_facts_answer_uses_verified_status_only(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What do you know is verified?"},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"]
    assert "Verified facts:" in answer
    assert "Context receipt:" not in answer
    assert "System Prompt" not in answer
    assert (
        payload.get("metadata", {}).get("context_receipt", {}).get("context_receipts")
    )

def test_every_contract_answer_has_compact_receipt(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompts = [
        "Are we beta ready?",
        "Did you check the repo?",
        "What failed?",
        "What do you remember?",
        "Make a guess about what is next.",
        "What model are you using?",
    ]

    for prompt in prompts:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        payload = response.json()
        answer = payload["messages"][-1]["content"]
        assert "Context receipt:" not in answer
        assistant_payload = payload.get("metadata", {}).get(
            "last_assistant_payload", {}
        )
        assert isinstance(assistant_payload, dict)
        has_receipt_metadata = bool(assistant_payload.get("context_receipt")) or bool(
            assistant_payload.get("memory_receipts")
        )
        assert has_receipt_metadata

def test_model_question_requires_proof_in_chat_path(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What model are you using?"},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"]
    assert "Context receipt:" not in answer
    assert "brain/policy layer" in answer
    assert "xv7-brain-records" not in answer

    metadata = payload.get("metadata", {})
    provenance = metadata.get("answer_provenance", {})
    assert provenance.get("answer_source") == "brain_policy"
    assert provenance.get("policy_source") == "answer_contract"
    assert provenance.get("runtime_model_inference_proven") is False

def test_memory_recall_uses_memory_records_only(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What do you remember?"},
    )

    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "Remembered items (Memory records only):" in answer
    assert "Verified facts:" not in answer
    assert "Knowledge facts:" not in answer
    assert "Context receipt:" not in answer

def test_verified_vs_remembered_separation_in_chat_path(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    remember = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "What do you remember about XV7?"},
    )
    assert remember.status_code == 200

    separation = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Is that verified or just remembered?"},
    )
    assert separation.status_code == 200
    answer = separation.json()["messages"][-1]["content"]
    assert "not verified status" in answer
    assert "Context receipt:" not in answer

def test_forget_that_is_ambiguous_does_not_delete(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    created_a = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Remember this: Otis wants receipts to stay compact."},
    )
    created_b = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Remember this: Otis wants receipt memory to include ids."},
    )
    assert created_a.status_code == 200
    assert created_b.status_code == 200

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Forget that receipt memory."},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"]
    assert "matches multiple memories" in answer

def test_structured_context_receipt_has_layer_by_prompt(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    cases = [
        ("What is my name?", "memory"),
        ("What are we working on right now?", "active_focus"),
        ("Can you help write implementation prompts for VS Code/Copilot?", "knowledge"),
        ("What do you know is verified?", "verified_status"),
        ("What is your name?", "system_prompt"),
    ]

    for prompt, expected_layer in cases:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200

        metadata = response.json().get("metadata", {})
        context_receipt = metadata.get("context_receipt", {})
        structured = context_receipt.get("context_receipts", [])
        assert isinstance(structured, list)
        assert len(structured) >= 1
        assert structured[0].get("layer") == expected_layer

def test_identity_creator_purpose_prompts_are_deterministic(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    cases = {
        "what is your name": "My name is Xoduz.",
        "how do you pronounce your name": "Xoduz is pronounced Exodus.",
        "how do you spell your name": "X-O-D-U-Z.",
        "is your name spelled exodus": "No. My name is spelled X-O-D-U-Z. It is pronounced Exodus.",
        "is your name spelled e-x-o-d-u-s": "No. That is the standard spelling of the word Exodus, but my name is Xoduz, spelled X-O-D-U-Z, and pronounced Exodus.",
        "who created you": "I was created by Otis Duncan for the XV7 project under Syfernetics.",
    }

    for prompt, expected in cases.items():
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        payload = response.json()
        answer = payload["messages"][-1]["content"]
        assert answer == expected
        lowered = answer.lower()
        assert "context does not specify" not in lowered
        assert "context receipt:" not in lowered
        assert "operator receipt:" not in lowered
        assert (
            payload.get("metadata", {})
            .get("last_assistant_payload", {})
            .get("context_receipt")
        )

    who = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "who are you"},
    )
    assert who.status_code == 200
    who_answer = who.json()["messages"][-1]["content"]
    assert "personal ai assistant" in who_answer.lower()
    assert "technical co-pilot" in who_answer.lower()
    assert "companion" not in who_answer.lower()

    for prompt in (
        "are you female",
        "are you my companion",
        "what is your relationship to me",
    ):
        resp = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert resp.status_code == 200
        a = resp.json()["messages"][-1]["content"]
        assert a, f"Empty answer for: {prompt}"
        if (
            "why were you built" not in prompt
            and "purpose" not in prompt
            and "become" not in prompt
        ):
            # Relationship boundary prompts must never contain 'companion' EXCEPT in the
            # deliberate denial answer ("not a romantic or sexual companion").
            if "are you my companion" not in prompt:
                assert "companion" not in a.lower(), (
                    f"Unexpected 'companion' in answer to '{prompt}': {a!r}"
                )

def test_why_built_and_purpose_answers_are_present(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    for prompt in ("why were you built", "what is your purpose"):
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        answer = response.json()["messages"][-1]["content"]
        lowered = answer.lower()
        assert "otis" in lowered
        assert "context does not specify" not in lowered
        assert "personal" in lowered or "technical" in lowered

def test_missing_tool_prompts_are_deterministic_and_keep_knowledge_receipts(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompts = {
        "set me a reminder for tomorrow at 5:00 p.m. to take out the trash": (
            "can't create live reminders yet",
            "reminder tool wired in",
            "personal-assistant roadmap",
        ),
        "what's the weather forecast today for Milledgeville Georgia": (
            "can't fetch live weather yet",
            "weather connector",
            "everyday-assistant roadmap",
        ),
        "check my email": (
            "can't check email yet",
            "authorized email connector",
            "personal-assistant roadmap",
        ),
        "can you text someone for me": (
            "can't send texts yet",
            "sms connector",
            "explicit approval",
        ),
        "do you know my family": (
            "explicitly added to memory",
            "private",
        ),
        "do you know my medical history": (
            "explicitly approve",
            "private tagging",
        ),
    }

    for prompt, expected_parts in prompts.items():
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        payload = response.json()
        answer = payload["messages"][-1]["content"]
        lowered = answer.lower()
        for part in expected_parts:
            assert part in lowered
        assert "context does not specify" not in lowered
        assert "use a calendar app" not in lowered
        assert "my focus is app development" not in lowered
        assert "operator receipt:" not in lowered
        context_receipt = payload.get("metadata", {}).get("context_receipt", {})
        structured = context_receipt.get("context_receipts", [])
        assert isinstance(structured, list)
        assert len(structured) >= 1
        assert structured[0].get("layer") == "knowledge"

def test_code_artifact_generation_prompt_emits_code_artifact_payload(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)
    memory_dir = tmp_path / "memory_records"
    before_files = sorted(path.name for path in memory_dir.glob("XV7-MEMORY-*.json"))

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": (
                'Generate a small HTML code artifact for a one-page "Harry\'s Hot Dog Cart" website. '
                "Return it as a code artifact with filename index.html, language html, previewable true, "
                "and do not apply it to the repo."
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"]
    assert answer == "Here is a draft HTML artifact for index.html."
    assert "cannot execute live web searches" not in answer.lower()
    assert "browser tool" not in answer.lower()
    assert "web lookup connector" not in answer.lower()

    metadata = payload["messages"][-1].get("metadata", {})
    artifact = metadata.get("code_artifact", {})
    assert artifact.get("type") == "code_artifact"
    assert artifact.get("filename") == "index.html"
    assert artifact.get("language") == "html"
    assert artifact.get("previewable") is True
    assert artifact.get("applied") is False
    content = artifact.get("content", "")
    assert content.lstrip().startswith("<!doctype html>")
    assert "Harry's Hot Dog Cart" in content
    assert "<script" not in content.lower()
    assert "http://" not in content.lower()
    assert "https://" not in content.lower()

    assistant_payload = payload.get("metadata", {}).get("last_assistant_payload", {})
    assert assistant_payload.get("code_artifact", {}).get("filename") == "index.html"
    assert (
        assistant_payload.get("policy_provenance", {}).get("artifact_generation")
        == "local_model"
    )
    assert (
        assistant_payload.get("policy_provenance", {}).get("model_used")
        == "fake-code-model:test"
    )
    assert (
        assistant_payload.get("policy_provenance", {}).get("artifact_validation")
        == "passed"
    )
    assert assistant_payload.get("memory_receipts") == []
    assert assistant_payload.get("operator_receipts") == []
    assert assistant_payload.get("learned_record_id") is None

    after_files = sorted(path.name for path in memory_dir.glob("XV7-MEMORY-*.json"))
    assert after_files == before_files

def test_code_artifact_generation_is_prompt_aware(monkeypatch, tmp_path: Path) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    cases = [
        (
            'Generate a small HTML code artifact for a one-page "Flow Flowers" website. Use soft pink, cream, and gold colors with an elegant script-style heading. Return it as a code artifact with filename index.html, language html, previewable true, and do not apply it to the repo.',
            ["Flow Flowers", "pink", "cream", "gold", "elegant"],
        ),
        (
            'Generate a small HTML code artifact for a one-page "Rico\'s Mobile Detailing" website. Make it black, silver, and electric blue with a bold automotive feel. Return it as a code artifact with filename index.html, language html, previewable true, and do not apply it to the repo.',
            ["Rico's Mobile Detailing", "black", "silver", "blue", "bold"],
        ),
        (
            'Generate a small HTML code artifact for a one-page "Neon Byte Arcade" website. Use bright purple and cyan colors, a retro arcade feel, and a bold futuristic font style. Return it as a code artifact with filename index.html, language html, previewable true, and do not apply it to the repo.',
            ["Neon Byte Arcade", "purple", "cyan", "futuristic"],
        ),
        (
            'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. Use black, red, and silver colors, make it trustworthy and urgent, and include emergency lockout service. Return it as a code artifact with filename index.html, language html, previewable true, and do not apply it to the repo.',
            ["Crimson Turtle Locksmiths", "black", "red", "silver", "trustworthy"],
        ),
    ]

    seen_contents: list[str] = []
    for prompt, required_fragments in cases:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        content = response.json()["messages"][-1]["metadata"]["code_artifact"][
            "content"
        ]
        seen_contents.append(content)
        for fragment in required_fragments:
            assert fragment in content
        if "Harry's Hot Dog Cart" not in prompt:
            assert "Harry's Hot Dog Cart" not in content

    assert len(set(seen_contents)) == len(cases)

def test_code_artifact_generation_has_no_cross_category_leakage(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    cases = [
        (
            'Generate a small HTML code artifact for a one-page "Flow Flowers" website.',
            ["flow flowers", "one-page website"],
            [
                "harry",
                "hot dog",
                "loaded chili dog",
                "chicago-style dog",
                "detailing",
                "arcade",
            ],
        ),
        (
            'Generate a small HTML code artifact for a one-page "Rico\'s Mobile Detailing" website.',
            ["rico's mobile detailing", "one-page website"],
            ["harry", "hot dog", "flow flowers", "bouquet", "arcade", "neon byte"],
        ),
        (
            'Generate a small HTML code artifact for a one-page "Neon Byte Arcade" website with purple and cyan futuristic styling.',
            ["neon byte arcade", "futuristic"],
            ["harry", "hot dog", "flow flowers", "bouquet", "detailing", "rico"],
        ),
    ]

    for prompt, must_have, must_not_have in cases:
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        payload = response.json()
        content = payload["messages"][-1]["metadata"]["code_artifact"][
            "content"
        ].lower()
        for token in must_have:
            assert token in content
        for token in must_not_have:
            assert token not in content
        assert (
            payload.get("metadata", {})
            .get("last_assistant_payload", {})
            .get("policy_provenance", {})
            .get("artifact_generation")
            == "local_model"
        )

def test_code_artifact_generation_sentinel_business_name(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompt = (
        'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. '
        "Use black, red, and silver colors. Return it as a code artifact with filename index.html, "
        "language html, previewable true, and do not apply it to the repo."
    )

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    payload = response.json()
    artifact = payload["messages"][-1]["metadata"]["code_artifact"]
    content = str(artifact.get("content", ""))
    lowered = content.lower()

    assert artifact.get("filename") == "index.html"
    assert artifact.get("language") == "html"
    assert artifact.get("previewable") is True
    assert artifact.get("applied") is False
    assert "Crimson Turtle Locksmiths" in content

    # If locksmith-specific semantics are unsupported, generic-business template text is acceptable.
    assert (
        "locksmith" in lowered
        or "security" in lowered
        or "key" in lowered
        or "one-page business website" in lowered
    )

    for forbidden in (
        "harry",
        "hot dog",
        "flow flowers",
        "rico",
        "detailing",
        "neon byte",
        "arcade",
        "bouquet",
    ):
        assert forbidden not in lowered

    assert (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("policy_provenance", {})
        .get("artifact_generation")
        == "local_model"
    )

def test_code_artifact_generation_fallback_is_honest(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch, should_fail=True, reason="timeout")
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": (
                'Generate a small HTML code artifact for a one-page "Flow Flowers" website. '
                "Return it as a code artifact with filename index.html, language html, previewable true, "
                "and do not apply it to the repo."
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    provenance = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("policy_provenance", {})
    )
    assert (
        provenance.get("artifact_generation")
        == "deterministic_prompt_template_fallback"
    )
    assert provenance.get("fallback_reason")

def test_lookup_prompt_still_uses_lookup_refusal_path(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "Look up the official website for Harry's Hot Dog Cart."},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["messages"][-1]["content"].lower()
    assert "cannot execute live web searches" in answer
    assert "browser tool" in answer
    assert (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("code_artifact")
        == {}
    )

def test_runtime_artifact_connectivity_endpoint(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "core.main.brain_context_manager.code_artifact_connectivity_diagnostic",
        _fake_artifact_connectivity,
    )

    response = client.get("/runtime/models/artifact-connectivity")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("resolved_model_tag") == "qwen3:14b"
    assert payload.get("reachable") is True
    assert payload.get("reachable_endpoint") == "http://127.0.0.1:11434"
    checks = payload.get("checks", [])
    assert isinstance(checks, list)
    assert len(checks) == 2

def test_become_prompt_is_personal_assistant_first(monkeypatch, tmp_path: Path) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "what are you supposed to become"},
    )
    assert response.status_code == 200
    answer = response.json()["messages"][-1]["content"].lower()
    assert "personal ai assistant" in answer
    assert "best-friend" in answer
    assert "technical co-pilot" in answer
    assert "female companion" not in answer
    assert "companion" not in answer

def test_local_capability_prompts_are_honest_and_current(
    monkeypatch, tmp_path: Path
) -> None:
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompts = {
        "what are we working on right now": (
            "b9.8",
            "local host scan bridge",
            "operator mode",
        ),
        "what can you do locally": (
            "read-only scans can run in normal mode",
            "mutation requires operator mode",
        ),
        "can you run powershell": (
            "not as an unrestricted shell",
            "powershell/cmd-backed scan actions",
        ),
    }

    for prompt, expected_parts in prompts.items():
        response = client.post(
            f"/sessions/{session_id}/messages",
            headers={"X-XV7-API-Key": "test-secret"},
            json={"raw_text": prompt},
        )
        assert response.status_code == 200
        answer = response.json()["messages"][-1]["content"].lower()
        for part in expected_parts:
            assert part in answer
        assert "context required" not in answer

def test_crimson_fidelity_contains_locksmith_language_and_visual_cues(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    prompt = (
        'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. '
        "Use black, red, and silver colors, make it trustworthy and urgent, and include emergency lockout service. "
        "Return it as a code artifact with filename index.html, language html, previewable true, and do not apply it to the repo."
    )

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": prompt},
    )

    assert response.status_code == 200
    payload = response.json()
    content = payload["messages"][-1]["metadata"]["code_artifact"]["content"].lower()
    assert "crimson turtle locksmiths" in content
    assert any(
        token in content
        for token in ("locksmith", "security", "key", "lock", "emergency", "lockout")
    )
    assert "black" in content
    assert "red" in content
    assert "silver" in content or "gray" in content or "grey" in content
    assert "clean one-page website with a clear offer" not in content

def test_unquoted_soggy_doggy_prompt_is_prompt_aware(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )

    assert response.status_code == 200
    payload = response.json()
    artifact = payload["messages"][-1]["metadata"]["code_artifact"]
    content = str(artifact.get("content", ""))
    lowered = content.lower()
    provenance = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("policy_provenance", {})
    )

    assert artifact.get("filename") == "index.html"
    assert "Soggy Doggy" in content
    assert any(
        token in lowered
        for token in ("groom", "pet", "dog", "bath", "trim", "fur", "paw")
    )
    assert any(token in lowered for token in ("white", "#ffffff"))
    assert any(token in lowered for token in ("purple", "#7c3aed", "#a855f7"))
    assert any(token in lowered for token in ("green", "#22c55e"))
    assert "local business website" not in lowered
    assert (
        "a clean one-page website with a clear offer and simple call to action."
        not in content
    )
    for forbidden in ("harry", "flow", "rico", "neon", "crimson"):
        assert forbidden not in lowered
    assert provenance.get("artifact_generation") in {
        "local_model",
        "deterministic_prompt_template_fallback",
    }

def test_code16_tony_tavern_fidelity_gate_blocks_stale_palette(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    response = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for tony tavern grooming using black yellow and green"
        },
    )

    assert response.status_code == 200
    payload = response.json()
    artifact = payload["messages"][-1]["metadata"]["code_artifact"]
    content = str(artifact.get("content", "")).lower()
    fidelity = artifact.get("prompt_fidelity", {})
    provenance = (
        payload.get("metadata", {})
        .get("last_assistant_payload", {})
        .get("policy_provenance", {})
    )

    assert "tony tavern" in content
    assert "groom" in content
    assert "black" in content or "#070707" in content
    assert "yellow" in content or "#facc15" in content or "#fbbf24" in content
    assert "green" in content or "#22c55e" in content
    assert "soggy doggy" not in content
    assert "white, purple, and green" not in content
    assert fidelity.get("status") in {"passed", "repaired"}
    assert fidelity.get("requested_business_name", "").lower() == "tony tavern"
    assert fidelity.get("requested_business_type") == "grooming"
    assert provenance.get("prompt_fidelity", {}).get("status") in {"passed", "repaired"}

def test_code16_soggy_then_tony_back_to_back_prevents_leakage_and_patch_targets_latest(
    monkeypatch, tmp_path: Path
) -> None:
    _use_fake_local_model(monkeypatch)
    client = _setup_contract_only(monkeypatch, tmp_path)
    session_id = _new_session(client)

    soggy = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        },
    )
    assert soggy.status_code == 200
    soggy_content = soggy.json()["messages"][-1]["metadata"]["code_artifact"][
        "content"
    ].lower()
    assert "soggy doggy" in soggy_content
    assert "tony tavern" not in soggy_content

    tony = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={
            "raw_text": "generate a small HTML artifact for tony tavern grooming using black yellow and green"
        },
    )
    assert tony.status_code == 200
    tony_content = tony.json()["messages"][-1]["metadata"]["code_artifact"][
        "content"
    ].lower()
    assert "tony tavern" in tony_content
    assert "soggy doggy" not in tony_content
    assert "white, purple, and green" not in tony_content

    patch = client.post(
        f"/sessions/{session_id}/messages",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"raw_text": "generate patch"},
    )
    assert patch.status_code == 200
    proposal = patch.json()["messages"][-1]["metadata"]["artifact_patch_proposal"]
    assert proposal.get("target_path") == "generated-sites/tony-tavern/index.html"
