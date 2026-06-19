from answer_contract_support import *  # noqa: F401,F403

def test_github_proof_prompt_does_not_route_to_patch_proposal() -> None:
    contract = AnswerContract()

    normalized = contract._normalize(
        "Operator Mode: Build and push a real GitHub proof project named earthx-github-proof under X:\\xoduz-sandbox\\earthx-github-proof. not a preview. not a patch."
    )
    assert contract._is_operator_github_project_request(normalized) is True
    assert contract._is_patch_proposal_request(normalized) is False

def test_initialize_repo_push_prompt_is_first_class_operator_not_patch() -> None:
    contract = AnswerContract()

    normalized = contract._normalize("initialize the new repository and push to github")
    assert contract._is_first_class_operator_request(normalized) is True
    assert contract._is_patch_proposal_request(normalized) is False

def test_slash_push_github_is_first_class_operator_not_patch() -> None:
    contract = AnswerContract()

    normalized = contract._normalize("/push github")
    assert contract._is_first_class_operator_request(normalized) is True
    assert contract._is_patch_proposal_request(normalized) is False

def test_generate_patch_prompt_still_routes_to_patch_proposal() -> None:
    contract = AnswerContract()

    normalized = contract._normalize("generate a patch for this artifact")
    assert contract._is_patch_proposal_request(normalized) is True

def test_build_website_to_sandbox_still_routes_to_sandbox_build() -> None:
    contract = AnswerContract()

    normalized = contract._normalize("build a website to sandbox")
    assert contract._is_sandbox_build_request(normalized) is True

def test_prompt_fidelity_validation_rejects_stale_palette_and_name() -> None:
    contract = AnswerContract()
    prompt = "generate a small HTML artifact for tony tavern grooming using black yellow and green"
    content = (
        "<!doctype html><html><head><title>Tony Tavern</title><style>"
        "body{background:white;color:purple;} .hero{border-color:#22c55e;}"
        "</style></head><body><h1>Tony Tavern</h1>"
        "<p>White, purple, and green studio style with clean grooming stations.</p>"
        "<p>Soggy Doggy premium grooming.</p></body></html>"
    )

    report = contract.validate_artifact_prompt_fidelity(
        prompt,
        content,
        {
            "history_business_names": ["Soggy Doggy"],
            "previous_colors": ["white", "purple", "green"],
        },
    )

    assert report["passed"] is False
    assert any(
        item.startswith("forbidden_term_present:Soggy Doggy")
        for item in report["failures"]
    )
    assert any(
        item.startswith("forbidden_term_present:white") for item in report["failures"]
    )
    assert any(
        item.startswith("forbidden_term_present:purple") for item in report["failures"]
    )

def test_code16_generation_repairs_stale_template_leakage(monkeypatch) -> None:
    contract = AnswerContract()

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
            "<!doctype html><html><head><title>Tony Tavern</title><style>"
            "body{background:white;color:purple;} .button{border-color:#22c55e;}"
            "</style></head><body><h1>Tony Tavern</h1>"
            "<p>White, purple, and green studio style with clean grooming stations.</p>"
            "<p>Pet grooming bath trim fur care.</p></body></html>",
            "fake-code-model:test",
            "http://127.0.0.1:11434",
        )

    monkeypatch.setattr(
        AnswerContract, "_generate_artifact_with_local_model", _fake_generate
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate a small HTML artifact for tony tavern grooming using black yellow and green",
            session_messages=[
                {
                    "role": "assistant",
                    "content": "old",
                    "metadata": {
                        "code_artifact": {
                            "type": "code_artifact",
                            "filename": "index.html",
                            "language": "html",
                            "previewable": True,
                            "applied": False,
                            "content": "<!doctype html><html><head><title>Soggy Doggy</title><style>body{background:white;color:purple}</style></head><body><h1>Soggy Doggy</h1></body></html>",
                            "source_prompt": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green",
                        }
                    },
                }
            ],
            session_metadata={},
        )
    )

    assert response is not None
    artifact = response["code_artifact"]
    assert artifact
    content = artifact["content"].lower()
    assert "tony tavern" in content
    assert "white, purple, and green" not in content
    assert "soggy doggy" not in content
    fidelity = artifact["prompt_fidelity"]
    assert fidelity["status"] in {"passed", "repaired"}
    assert fidelity["requested_business_name"] == "tony tavern"
    assert fidelity["requested_business_type"] == "grooming"

def test_code16_generation_blocks_unrepairable_prompt_fidelity(monkeypatch) -> None:
    contract = AnswerContract()

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
            '<!doctype html><html><head><title>Soggy Doggy</title><script src="https://cdn.bad/site.js"></script></head>'
            "<body><h1>Soggy Doggy</h1><p>White, purple, and green studio style with clean grooming stations.</p></body></html>",
            "fake-code-model:test",
            "http://127.0.0.1:11434",
        )

    def _no_repair(
        cls, *, prompt: str, artifact_content: str, fidelity_report: dict[str, object]
    ) -> str:
        return artifact_content

    monkeypatch.setattr(
        AnswerContract, "_generate_artifact_with_local_model", _fake_generate
    )
    monkeypatch.setattr(
        AnswerContract, "_repair_artifact_prompt_fidelity", classmethod(_no_repair)
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate a small HTML artifact for tony tavern grooming using black yellow and green",
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    assert response["code_artifact"] == {}
    assert "failed prompt-fidelity validation" in response["visible_text"].lower()
    assert response["provenance"]["prompt_fidelity"]["status"] == "failed"
    assert response["provenance"]["prompt_fidelity"]["repair_attempted"] is True

def test_validate_artifact_rejects_generic_output_for_grooming_prompt() -> None:
    contract = AnswerContract()
    valid, reason = contract._validate_artifact_content(
        content=(
            "<!doctype html><html><head><style>body{background:white;color:purple;}</style></head>"
            "<body><h1>Local Business Website</h1><p>A clean one-page website with a clear offer and simple call to action.</p></body></html>"
        ),
        language="html",
        business_name="Soggy Doggy",
        style_hints={"colors": ["white", "purple", "green"], "styles": []},
        requested_question="generate a small HTML artifact for Soggy Doggy grooming using white purple and green",
    )

    assert valid is False
    assert reason in {
        "business_name_missing",
        "color_hints_missing",
        "grooming_language_missing",
        "generic_business_name_fallback_detected",
        "generic_hero_reuse_detected",
    }

def test_generation_fallback_returns_sanitized_failure_when_template_cannot_pass_validation(
    monkeypatch,
) -> None:
    contract = AnswerContract()

    monkeypatch.setattr(
        "core.brain.answer_contract.resolve_model_for_runtime_role",
        lambda role: RuntimeRoleModelResolution(
            profile="balanced",
            profile_source="env",
            alias_used=role,
            canonical_role="code",
            model_tag="qwen3:14b",
            error=None,
        ),
    )
    monkeypatch.setattr(
        AnswerContract,
        "_default_code_artifact_content",
        staticmethod(
            lambda filename, language, question: (
                "<!doctype html><html><head><style>body{background:black;color:red;}</style></head><body><h1>Local Business Website</h1><p>A clean one-page website with a clear offer and simple call to action.</p></body></html>"
            )
        ),
    )

    async def _fake_generate_failure(
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
        raise RuntimeError("timeout")

    monkeypatch.setattr(
        AnswerContract, "_generate_artifact_with_local_model", _fake_generate_failure
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
        )
    )

    assert response is not None
    assert response["code_artifact"] == {}
    assert "safe artifact draft" in response["visible_text"].lower()
    assert "content_length_out_of_bounds" not in response["visible_text"].lower()
    assert response["provenance"]["artifact_generation"] == "artifact_generation_failed"
    assert response["provenance"]["failure_reason"] == "fallback_validation_failed"

def test_artifact_generation_retry_prompt_includes_missing_requirements(
    monkeypatch,
) -> None:
    contract = AnswerContract()

    monkeypatch.setattr(
        "core.brain.answer_contract.resolve_model_for_runtime_role",
        lambda role: RuntimeRoleModelResolution(
            profile="balanced",
            profile_source="env",
            alias_used=role,
            canonical_role="code",
            model_tag="qwen3:14b",
            error=None,
        ),
    )
    monkeypatch.setattr(
        "core.brain.answer_contract.configured_ollama_base_url_candidates",
        lambda: ["http://127.0.0.1:11434"],
    )

    user_prompts: list[str] = []
    responses = [
        {
            "message": {
                "content": "<!doctype html><html><head><style>body{background:black;color:red;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>service</p></body></html>"
            }
        },
        {
            "message": {
                "content": "<!doctype html><html><head><style>body{background:black;color:red;} .silver{color:silver;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>Urgent trustworthy locksmith security lockout service</p></body></html>"
            }
        },
    ]

    class _FakeResponse:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout):
            self.base_url = base_url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, path: str, json: dict):
            messages = json.get("messages", [])
            user_prompts.append(str(messages[-1].get("content", "")))
            payload = responses.pop(0)
            return _FakeResponse(payload)

    monkeypatch.setattr("core.brain.answer_contract.httpx.AsyncClient", _FakeClient)

    content, model, _endpoint = asyncio.run(
        contract._generate_artifact_with_local_model(
            question=(
                'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. '
                "Use black, red, and silver colors, make it trustworthy and urgent, and include emergency lockout service."
            ),
            filename="index.html",
            language="html",
            previewable=True,
            apply_requested=False,
            business_name="Crimson Turtle Locksmiths",
            style_hints={
                "colors": ["black", "red", "silver"],
                "styles": ["trustworthy", "urgent"],
            },
            layout_hints=[],
        )
    )

    assert model == "qwen3:14b"
    assert "Crimson Turtle Locksmiths" in content
    assert len(user_prompts) == 2
    assert "Missing requirements:" in user_prompts[1]
    assert "silver/gray/metal" in user_prompts[1] or "silver" in user_prompts[1]

def test_artifact_edit_detection_prefers_edit_over_sms_with_active_artifact() -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:black;color:red;}.x{color:silver;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>Urgent trustworthy locksmith emergency lockout service.</p></body></html>",
                }
            },
        }
    ]

    assert (
        contract._tool_intent_category("change the text on the website to script")
        is None
    )
    artifact, source = contract._latest_assistant_artifact(session_messages, {})
    assert artifact is not None
    assert source == "latest session artifact"
    assert (
        contract._looks_like_artifact_edit("change the text on the website to script")
        is True
    )
    assert (
        contract.SMS_EXPLICIT_SEND_PATTERN.search(
            "change the text on the website to script"
        )
        is None
    )

def test_revision_prompt_contains_existing_content_and_instruction() -> None:
    contract = AnswerContract()
    artifact = {
        "filename": "index.html",
        "language": "html",
        "previewable": True,
        "applied": False,
        "content": "<!doctype html><html><body><h1>Crimson Turtle Locksmiths</h1></body></html>",
    }
    prompt = contract._build_local_artifact_revision_prompt(
        edit_instruction="change the font to script",
        source_artifact=artifact,
        strict_retry=False,
    )

    assert "change the font to script" in prompt
    assert "Crimson Turtle Locksmiths" in prompt
    assert "full replacement source code" in prompt

def test_build_code_artifact_response_revision_preserves_metadata(monkeypatch) -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:black;color:red;} h1{font-family:Arial;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>Urgent trustworthy locksmith emergency lockout service.</p></body></html>",
                }
            },
        }
    ]

    async def _fake_revise(self, *, question: str, source_artifact: dict[str, object]):
        return (
            "<!doctype html><html><head><style>body{background:black;color:red;} h1{font-family:'Brush Script MT',cursive;} .metal{color:silver;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>Urgent trustworthy locksmith emergency lockout service.</p></body></html>",
            "qwen3:14b",
            "http://ollama:11434",
        )

    monkeypatch.setattr(
        AnswerContract, "_revise_artifact_with_local_model", _fake_revise
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "change the text on the website to script",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    artifact = response["code_artifact"]
    assert artifact["filename"] == "index.html"
    assert artifact["language"] == "html"
    assert artifact["previewable"] is True
    assert artifact["applied"] is False
    assert "Brush Script" in artifact["content"]
    assert response["provenance"]["artifact_generation"] == "local_model_revision"
    assert response["provenance"]["artifact_validation"] in {"passed", "repaired"}
    assert response["provenance"]["source_artifact"] == "latest session artifact"

def test_typography_refinement_blackletter_preserves_identity_and_content(
    monkeypatch,
) -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:black;color:#fef3c7;} .eyebrow{color:#f59e0b;} h1{font-family:Georgia,serif;}</style></head><body><div class='eyebrow'>Tony's Tavern</div><h1>Tony's Tavern</h1><h2>Neighborhood biker bar</h2><p>Cold pours, loud guitars, and late-night bar food.</p></body></html>",
                }
            },
        }
    ]

    async def _should_not_run_revise(
        self, *, question: str, source_artifact: dict[str, object]
    ):
        raise AssertionError(
            "typography-only requests should not call local model revision"
        )

    monkeypatch.setattr(
        AnswerContract, "_revise_artifact_with_local_model", _should_not_run_revise
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "change the heading font to old English blackletter gothic style",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    artifact = response["code_artifact"]
    content = artifact["content"]
    assert "Tony's Tavern" in content
    assert "biker bar" in content.lower()
    assert "blackletter-heading" in content
    assert "xv7-typography-refinement" in content
    assert (
        response["provenance"]["artifact_generation"]
        == "deterministic_typography_refinement"
    )
    typography = response["provenance"].get("typography_refinement", {})
    assert typography.get("requested_style") == "blackletter/gothic"
    assert typography.get("status") == "passed"

def test_typography_refinement_blackletter_preserves_existing_colors(
    monkeypatch,
) -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>:root{--bg:white;--accent:pink;--accent-2:purple;} body{background:white;color:#111;} h1{font-family:Arial;} .eyebrow{color:purple;}</style></head><body><div class='eyebrow'>Tony's Tavern</div><h1>Tony's Tavern</h1><h2>Live music and late-night food</h2></body></html>",
                }
            },
        }
    ]

    async def _should_not_run_revise(
        self, *, question: str, source_artifact: dict[str, object]
    ):
        raise AssertionError(
            "typography-only requests should not call local model revision"
        )

    monkeypatch.setattr(
        AnswerContract, "_revise_artifact_with_local_model", _should_not_run_revise
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "Keep everything else exactly the same but change the heading font to a strong old English blackletter medieval font treatment.",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    content = response["code_artifact"]["content"].lower()
    assert "white" in content
    assert "pink" in content
    assert "purple" in content
    assert "blackletter-heading" in content

def test_typography_refinement_script_request_succeeds(monkeypatch) -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:black;color:#fef3c7;} h1{font-family:Georgia,serif;} .eyebrow{color:#f59e0b;}</style></head><body><div class='eyebrow'>Tony's Tavern</div><h1>Tony's Tavern</h1><h2>Neighborhood biker bar</h2></body></html>",
                }
            },
        }
    ]

    response = asyncio.run(
        contract.build_code_artifact_response(
            "change the heading font to script",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    content = response["code_artifact"]["content"]
    assert "script-heading" in content
    assert "Brush Script MT" in content or "cursive" in content
    typography = response["provenance"].get("typography_refinement", {})
    assert typography.get("requested_style") == "script/cursive"
    assert typography.get("status") == "passed"

def test_typography_refinement_mode_detects_long_blackletter_prompt() -> None:
    contract = AnswerContract()
    prompt = (
        "change the main heading and major section titles to a blackletter / gothic biker-bar style font. "
        "Do not just name a missing font. Make the visual style obvious with available CSS fallbacks, "
        "heavier strokes, shadowing, letter spacing, and decorative styling."
    )

    normalized = contract._normalize(prompt)
    assert contract._artifact_refinement_mode(normalized) == "typography_only"
    assert contract._looks_like_artifact_edit(normalized) is True

def test_typography_refinement_without_active_artifact_returns_guidance() -> None:
    contract = AnswerContract()

    response = asyncio.run(
        contract.build_code_artifact_response(
            "change the heading font to blackletter",
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    assert response["code_artifact"] == {}
    assert "active artifact" in response["visible_text"].lower()
    assert (
        response["provenance"]["artifact_generation"]
        == "artifact_refinement_unavailable"
    )

def test_typography_refinement_failure_is_sanitized_and_does_not_replace_artifact(
    monkeypatch,
) -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:black;color:#fef3c7;} h1{font-family:Georgia,serif;}</style></head><body><h1>Tony's Tavern</h1><p>Neighborhood biker bar live music and food.</p></body></html>",
                }
            },
        }
    ]

    monkeypatch.setattr(
        AnswerContract,
        "_deterministic_typography_refinement_content",
        classmethod(
            lambda cls, *, source_artifact, requested_style: (
                "short",
                {
                    "requested_style": requested_style,
                    "applied_to": [],
                    "deterministic_fallback_used": True,
                    "status": "failed",
                },
                False,
                "content_length_out_of_bounds",
            )
        ),
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "change the heading font to old English blackletter",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    assert response["code_artifact"] == {}
    assert "content_length_out_of_bounds" not in response["visible_text"]
    assert (
        response["visible_text"]
        == "I could not safely apply the typography refinement, so I preserved the current artifact unchanged."
    )
    assert (
        response["provenance"]["artifact_generation"] == "typography_refinement_failed"
    )
    typography = response["provenance"].get("typography_refinement", {})
    assert typography.get("status") == "failed"

def test_typography_long_blackletter_sequence_uses_deterministic_refinement(
    monkeypatch,
) -> None:
    contract = AnswerContract()
    revise_calls: list[str] = []
    session_messages: list[dict[str, object]] = []

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
    ) -> tuple[str, str]:
        return (
            "<!doctype html><html><head><style>:root{--bg:#070707;--accent:#f97316;--accent-2:#facc15;} body{background:#070707;color:#f5f5f5;} .eyebrow{color:#facc15;} h1,h2{font-family:Georgia,serif;} .section-title{font-family:Georgia,serif;}</style></head><body><div class='eyebrow'>Tony's Tavern</div><h1>Tony's Tavern</h1><h2>Biker Bar Highlights</h2><h3 class='section-title'>The Tavern Vibe</h3><p>Neighborhood biker bar with live music, late-night food, and rally nights.</p></body></html>",
            "fake-code-model:test",
        )

    async def _fake_revise(
        self, *, question: str, source_artifact: dict[str, object]
    ) -> tuple[str, str, str]:
        revise_calls.append(question.lower())
        lowered = question.lower()
        base = str(source_artifact.get("content") or "")
        if "change the website colors to white pink and purple" in lowered:
            updated = (
                base.replace("--bg:#070707", "--bg:white")
                .replace("--accent:#f97316", "--accent:pink")
                .replace("--accent-2:#facc15", "--accent-2:purple")
                .replace("background:#070707", "background:white")
                .replace("color:#f5f5f5", "color:#111")
                .replace("color:#facc15", "color:purple")
            )
            return (updated, "qwen3:14b", "http://ollama:11434")
        raise AssertionError(
            "typography-only prompts should not call local model revision"
        )

    monkeypatch.setattr(
        AnswerContract, "_generate_artifact_with_local_model", _fake_generate
    )
    monkeypatch.setattr(
        AnswerContract, "_revise_artifact_with_local_model", _fake_revise
    )

    prompts = [
        "create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors",
        "change the website colors to white pink and purple",
        "change the text to a old English font",
        "change the font to a script on the text",
        "change the main heading and major section titles to a blackletter / gothic biker-bar style font. Do not just name a missing font. Make the visual style obvious with available CSS fallbacks, heavier strokes, shadowing, letter spacing, and decorative styling.",
    ]

    final_response: dict[str, Any] = {}
    for prompt in prompts:
        final_response = (
            asyncio.run(
                contract.build_code_artifact_response(
                    prompt,
                    session_messages=session_messages,
                    session_metadata={},
                )
            )
            or {}
        )
        assert final_response
        step_artifact = final_response.get("code_artifact", {})
        assert step_artifact, (
            f"prompt failed to return artifact: {prompt} => {final_response}"
        )
        session_messages.append({"role": "user", "content": prompt})
        session_messages.append(
            {
                "role": "assistant",
                "content": final_response.get("visible_text", ""),
                "metadata": {
                    "code_artifact": step_artifact,
                    "policy_provenance": final_response.get("provenance", {}),
                },
            }
        )

    assert final_response
    artifact = final_response.get("code_artifact", {})
    content = str(artifact.get("content") or "")
    visible = str(final_response.get("visible_text") or "").lower()
    provenance = final_response.get("provenance", {})
    typography = provenance.get("typography_refinement", {})

    assert artifact
    assert (
        provenance.get("artifact_generation") == "deterministic_typography_refinement"
    )
    assert "blackletter-heading" in content
    assert "Old English Text MT" in content
    assert "UnifrakturCook" in content
    assert "UnifrakturMaguntia" in content
    assert "Cloister Black" in content
    assert "fantasy, Georgia, serif" in content
    assert "content_length_out_of_bounds" not in visible
    assert "http://ollama" not in visible
    assert "could not generate a safe artifact draft" not in visible
    assert "Tony's Tavern" in content
    assert "biker bar" in content.lower()
    assert "white" in content.lower()
    assert "pink" in content.lower()
    assert "purple" in content.lower()
    assert typography.get("requested_style") == "blackletter/gothic"
    assert typography.get("deterministic_fallback_used") is True
    assert typography.get("status") == "passed"
    assert len(revise_calls) == 1
    assert "change the website colors to white pink and purple" in revise_calls[0]
