from answer_contract_support import *  # noqa: F401,F403

def test_build_code_artifact_response_revision_uses_deterministic_fallback(
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
                    "content": "<!doctype html><html><head><style>body{background:black;color:red;} .metal{color:silver;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>Urgent trustworthy locksmith emergency lockout service.</p></body></html>",
                }
            },
        }
    ]

    async def _fake_revise(self, *, question: str, source_artifact: dict[str, object]):
        raise RuntimeError("revision_content_unchanged")

    monkeypatch.setattr(
        AnswerContract, "_revise_artifact_with_local_model", _fake_revise
    )
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

    response = asyncio.run(
        contract.build_code_artifact_response(
            "change the colors to black and gold and make it more premium",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    artifact = response["code_artifact"]
    if artifact:
        assert artifact["filename"] == "index.html"
        assert artifact["language"] == "html"
        assert artifact["previewable"] is True
        assert artifact["applied"] is False
        assert "#d4af37" in artifact["content"] or "gold" in artifact["content"].lower()
        assert "premium" in artifact["content"].lower()
        assert (
            response["provenance"]["artifact_generation"]
            == "deterministic_prompt_template_fallback"
        )
        assert response["provenance"]["model_used"] == "qwen3:14b"
        assert response["provenance"]["source_artifact"] == "latest session artifact"
        assert "artifact revision fallback" in response["provenance"]["fallback_reason"]
    else:
        assert "failed prompt-fidelity validation" in response["visible_text"].lower()
        assert (
            response["provenance"]["artifact_generation"]
            == "artifact_prompt_fidelity_blocked"
        )

def test_sms_pattern_handles_explicit_message_wording() -> None:
    contract = AnswerContract()
    records = _layer_map()

    for prompt in (
        "send a text to John",
        "text my wife",
        "message Sarah",
        "SMS this to Bob",
    ):
        answer = contract.try_answer(
            prompt,
            records_by_layer=records,
            session_metadata={},
        )
        assert answer is not None
        assert "sms connector" in answer.lower()

    non_sms = contract._tool_intent_category("change the text on the website to script")
    assert non_sms is None

def test_refinement_mode_detects_undo_and_explain() -> None:
    contract = AnswerContract()

    assert contract._artifact_refinement_mode("undo the last change") == "undo"
    assert contract._artifact_refinement_mode("what changed?") == "explain"
    assert contract._looks_like_artifact_edit("undo the last change") is True
    assert contract._looks_like_artifact_edit("what changed?") is True

def test_build_code_artifact_response_requests_artifact_context_first() -> None:
    contract = AnswerContract()

    response = asyncio.run(
        contract.build_code_artifact_response(
            "make it more premium",
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
    assert response["provenance"]["failure_reason"] == "no_active_artifact"

def test_build_code_artifact_response_undo_restores_previous_revision() -> None:
    contract = AnswerContract()
    session_messages = [
        {
            "role": "user",
            "content": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green",
        },
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
                    "content": "<!doctype html><html><body><h1>Soggy Doggy</h1><p>Bath trim fur care</p></body></html>",
                },
                "policy_provenance": {
                    "artifact_generation": "local_model",
                    "revision_number": 1,
                },
            },
        },
        {
            "role": "user",
            "content": "change the colors to black and gold",
        },
        {
            "role": "assistant",
            "content": "Here is a revised HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><body><h1>Soggy Doggy</h1><p>Black and gold bath trim fur care</p></body></html>",
                },
                "policy_provenance": {
                    "artifact_generation": "local_model_revision",
                    "revision_number": 2,
                },
            },
        },
    ]

    response = asyncio.run(
        contract.build_code_artifact_response(
            "undo the last change",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    assert response["provenance"]["artifact_generation"] == "artifact_undo"
    assert (
        response["code_artifact"]["content"]
        == "<!doctype html><html><body><h1>Soggy Doggy</h1><p>Bath trim fur care</p></body></html>"
    )
    assert response["code_artifact"]["revision_number"] == 3

def test_build_code_artifact_response_explain_returns_summary_only() -> None:
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
                    "content": "<!doctype html><html><body><h1>Soggy Doggy</h1><p>Bath trim fur care</p></body></html>",
                },
                "policy_provenance": {
                    "artifact_generation": "local_model",
                    "revision_number": 1,
                },
            },
        },
        {
            "role": "assistant",
            "content": "Here is a revised HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>h1{font-family:'Brush Script MT',cursive;}</style></head><body><h1>Pampered Paws, Clean Coats</h1><p>Bath trim fur care</p></body></html>",
                },
                "policy_provenance": {
                    "artifact_generation": "local_model_revision",
                    "revision_number": 2,
                },
            },
        },
    ]

    response = asyncio.run(
        contract.build_code_artifact_response(
            "what changed?",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    assert response["code_artifact"] == {}
    assert response["provenance"]["artifact_generation"] == "artifact_change_summary"
    assert (
        "headline" in response["visible_text"].lower()
        or "typography" in response["visible_text"].lower()
    )

def test_patch_proposal_from_active_artifact_does_not_write_file(
    tmp_path, monkeypatch
) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_messages = _artifact_session_messages(
        content="<!doctype html><html><head><style>body{background:white;color:#111}</style></head><body><h1>Soggy Doggy</h1><p>Pet grooming bath trim fur care.</p></body></html>",
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    proposal = response["artifact_patch_proposal"]
    assert proposal["type"] == "artifact_patch_proposal"
    assert proposal["target_path"] == "generated-sites/soggy-doggy/index.html"
    assert proposal["applied"] is False
    assert proposal["requires_confirmation"] is True
    assert proposal["validation"]["status"] == "passed"
    assert not (tmp_path / "generated-sites" / "soggy-doggy" / "index.html").exists()

def test_patch_proposal_uses_latest_artifact_slug_after_back_to_back_generation() -> (
    None
):
    contract = AnswerContract()
    session_messages = [
        {
            "role": "assistant",
            "content": "first",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:white}</style><title>Soggy Doggy</title></head><body><h1>Soggy Doggy</h1></body></html>",
                    "artifact_id": "soggy-doggy-artifact",
                    "revision_id": "soggy-doggy-artifact:r1",
                    "revision_number": 1,
                    "source_prompt": "generate a small HTML artifact for Soggy Doggy grooming using white purple and green",
                },
                "policy_provenance": {
                    "artifact_generation": "local_model",
                    "revision_number": 1,
                },
            },
        },
        {
            "role": "assistant",
            "content": "second",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": "index.html",
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": "<!doctype html><html><head><style>body{background:black}</style><title>Tony Tavern</title></head><body><h1>Tony Tavern</h1></body></html>",
                    "artifact_id": "tony-tavern-artifact",
                    "revision_id": "tony-tavern-artifact:r1",
                    "revision_number": 1,
                    "source_prompt": "generate a small HTML artifact for tony tavern grooming using black yellow and green",
                },
                "policy_provenance": {
                    "artifact_generation": "local_model",
                    "revision_number": 1,
                },
            },
        },
    ]

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    assert (
        response["artifact_patch_proposal"]["target_path"]
        == "generated-sites/tony-tavern/index.html"
    )

def test_patch_proposal_without_active_artifact_returns_clear_message() -> None:
    contract = AnswerContract()

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    assert response["artifact_patch_proposal"] == {}
    assert (
        response["visible_text"]
        == "I do not have an active code artifact to turn into a patch yet. Generate or paste an artifact first."
    )

def test_patch_proposal_sanitizes_malicious_filename(tmp_path, monkeypatch) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_messages = _artifact_session_messages(
        filename="../../evil.html",
        content="<!doctype html><html><head><style>body{background:white}</style></head><body><h1>Soggy Doggy</h1><p>Pet grooming bath trim fur care.</p></body></html>",
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    proposal = response["artifact_patch_proposal"]
    assert proposal["target_path"].startswith("generated-sites/")
    assert ".." not in proposal["target_path"]
    assert proposal["target_path"].endswith("/evil.html")

def test_patch_proposal_existing_target_sets_update_operation(
    tmp_path, monkeypatch
) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    target = tmp_path / "generated-sites" / "soggy-doggy" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "<!doctype html><html><body><h1>Old</h1></body></html>", encoding="utf-8"
    )

    session_messages = _artifact_session_messages(
        content="<!doctype html><html><head><style>body{background:black;color:gold}</style></head><body><h1>Soggy Doggy</h1><p>Premium grooming.</p></body></html>",
    )
    response = asyncio.run(
        contract.build_code_artifact_response(
            "show me the diff",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    proposal = response["artifact_patch_proposal"]
    assert proposal["operation"] == "update"
    assert "--- a/generated-sites/soggy-doggy/index.html" in proposal["diff"]
    assert "+++ b/generated-sites/soggy-doggy/index.html" in proposal["diff"]
    assert (
        target.read_text(encoding="utf-8")
        == "<!doctype html><html><body><h1>Old</h1></body></html>"
    )

def test_apply_patch_requires_pending_proposal() -> None:
    contract = AnswerContract()

    response = asyncio.run(
        contract.build_code_artifact_response(
            "apply patch",
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    assert (
        response["visible_text"] == "I do not have a pending patch proposal to apply."
    )

def test_apply_patch_writes_file_only_after_explicit_apply(
    tmp_path, monkeypatch
) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_messages = _artifact_session_messages(
        content="<!doctype html><html><head><style>body{background:white;color:#111}</style></head><body><h1>Soggy Doggy</h1><p>Pet grooming bath trim fur care.</p></body></html>",
    )

    proposal_response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )
    proposal = proposal_response["artifact_patch_proposal"]
    target = tmp_path / proposal["target_path"]
    assert not target.exists()

    apply_messages = session_messages + [
        {
            "role": "assistant",
            "content": "I prepared a patch proposal from the active artifact. No files were changed.",
            "metadata": {
                "artifact_patch_proposal": proposal,
                "policy_provenance": {"artifact_patch": "proposed", "applied": False},
            },
        }
    ]
    apply_response = asyncio.run(
        contract.build_code_artifact_response(
            "apply patch",
            session_messages=apply_messages,
            session_metadata={},
        )
    )

    assert apply_response is not None
    assert target.exists()
    assert target.read_text(encoding="utf-8") == proposal["content"]
    assert "No commit was created" in apply_response["visible_text"]
    assert "no push was performed" in apply_response["visible_text"]

def test_post_apply_verify_reports_checks_and_preview_path(
    tmp_path, monkeypatch
) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_messages = _artifact_session_messages(
        content="<!doctype html><html><head><style>body{background:white;color:#111}</style></head><body><h1>Soggy Doggy</h1><p>Pet grooming bath trim fur care.</p></body></html>",
    )

    proposal_response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )
    proposal = proposal_response["artifact_patch_proposal"]

    apply_messages = session_messages + [
        {
            "role": "assistant",
            "content": "I prepared a patch proposal from the active artifact. No files were changed.",
            "metadata": {
                "artifact_patch_proposal": proposal,
                "policy_provenance": {"artifact_patch": "proposed", "applied": False},
            },
        }
    ]
    apply_response = asyncio.run(
        contract.build_code_artifact_response(
            "apply patch",
            session_messages=apply_messages,
            session_metadata={},
        )
    )
    applied = apply_response["artifact_patch_proposal"]

    verify_messages = apply_messages + [
        {
            "role": "assistant",
            "content": apply_response["visible_text"],
            "metadata": {
                "artifact_patch_proposal": applied,
                "policy_provenance": {"artifact_patch": "applied", "applied": True},
            },
        }
    ]
    verify_response = asyncio.run(
        contract.build_code_artifact_response(
            "verify the file",
            session_messages=verify_messages,
            session_metadata={},
        )
    )

    verify_proposal = verify_response["artifact_patch_proposal"]
    assert verify_proposal["post_apply_verification"]["status"] == "passed"
    assert verify_proposal["preview_path"] == "/generated-sites/soggy-doggy/index.html"
    assert verify_proposal["tests_run"] is False
    assert verify_proposal["commit_created"] is False
    assert verify_proposal["push_performed"] is False

def test_post_apply_preview_returns_route(tmp_path, monkeypatch) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_messages = _artifact_session_messages(
        content="<!doctype html><html><head><style>body{background:white;color:#111}</style></head><body><h1>Soggy Doggy</h1><p>Pet grooming bath trim fur care.</p></body></html>",
    )

    proposal_response = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )
    proposal = proposal_response["artifact_patch_proposal"]

    apply_response = asyncio.run(
        contract.build_code_artifact_response(
            "apply patch",
            session_messages=session_messages
            + [
                {
                    "role": "assistant",
                    "content": "I prepared a patch proposal from the active artifact. No files were changed.",
                    "metadata": {"artifact_patch_proposal": proposal},
                }
            ],
            session_metadata={},
        )
    )

    preview_response = asyncio.run(
        contract.build_code_artifact_response(
            "show me the preview",
            session_messages=session_messages
            + [
                {
                    "role": "assistant",
                    "content": apply_response["visible_text"],
                    "metadata": {
                        "artifact_patch_proposal": apply_response[
                            "artifact_patch_proposal"
                        ]
                    },
                }
            ],
            session_metadata={},
        )
    )

    assert "/generated-sites/soggy-doggy/index.html" in preview_response["visible_text"]
    assert (
        preview_response["artifact_patch_proposal"]["preview_path"]
        == "/generated-sites/soggy-doggy/index.html"
    )

def test_post_apply_targeted_validation_runs_focused_checks_only(
    tmp_path, monkeypatch
) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    session_messages = _artifact_session_messages(
        content="<!doctype html><html><head><style>body{background:white;color:#111}</style></head><body><h1>Soggy Doggy</h1><p>Pet grooming bath trim fur care.</p></body></html>",
    )

    proposal = asyncio.run(
        contract.build_code_artifact_response(
            "generate patch",
            session_messages=session_messages,
            session_metadata={},
        )
    )["artifact_patch_proposal"]

    apply_response = asyncio.run(
        contract.build_code_artifact_response(
            "apply patch",
            session_messages=session_messages
            + [
                {
                    "role": "assistant",
                    "content": "I prepared a patch proposal from the active artifact. No files were changed.",
                    "metadata": {"artifact_patch_proposal": proposal},
                }
            ],
            session_metadata={},
        )
    )

    targeted_response = asyncio.run(
        contract.build_code_artifact_response(
            "run validation",
            session_messages=session_messages
            + [
                {
                    "role": "assistant",
                    "content": apply_response["visible_text"],
                    "metadata": {
                        "artifact_patch_proposal": apply_response[
                            "artifact_patch_proposal"
                        ]
                    },
                }
            ],
            session_metadata={},
        )
    )

    targeted = targeted_response["artifact_patch_proposal"]["targeted_validation"]
    assert targeted["status"] == "passed"
    assert targeted["mode"] == "post_apply_targeted"
    assert targeted_response["artifact_patch_proposal"]["tests_run"] is False

def test_post_apply_full_test_request_is_guarded(tmp_path, monkeypatch) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))

    applied_proposal = {
        "type": "artifact_patch_proposal",
        "proposal_id": "patch-applied-1",
        "source_artifact_id": "artifact:r1",
        "filename": "index.html",
        "target_path": "generated-sites/soggy-doggy/index.html",
        "preview_path": "/generated-sites/soggy-doggy/index.html",
        "operation": "create",
        "language": "html",
        "applied": True,
        "requires_confirmation": True,
        "content": "<!doctype html><html><head><style>body{background:white}</style></head><body><h1>Soggy Doggy</h1></body></html>",
        "diff": "--- /dev/null\n+++ b/generated-sites/soggy-doggy/index.html\n",
        "validation": {
            "status": "passed",
            "checks": [{"name": "target_path_inside_repo", "status": "passed"}],
            "failures": [],
        },
    }

    response = asyncio.run(
        contract.build_code_artifact_response(
            "run full tests",
            session_messages=[
                {
                    "role": "assistant",
                    "content": "Applied the proposed patch to generated-sites/soggy-doggy/index.html.",
                    "metadata": {"artifact_patch_proposal": applied_proposal},
                }
            ],
            session_metadata={},
        )
    )

    assert response is not None
    assert "did not run full tests automatically" in response["visible_text"].lower()
    assert response["provenance"]["artifact_patch"] == "full_test_guard"
    assert response["provenance"]["tests_run"] is False

def test_failed_validation_patch_cannot_be_applied(tmp_path, monkeypatch) -> None:
    contract = AnswerContract()
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    invalid_proposal = {
        "type": "artifact_patch_proposal",
        "proposal_id": "patch-invalid",
        "source_artifact_id": "artifact:r1",
        "filename": "index.html",
        "target_path": "generated-sites/soggy-doggy/index.html",
        "operation": "create",
        "language": "html",
        "applied": False,
        "requires_confirmation": True,
        "content": "<html><body>bad</body></html>",
        "diff": "--- /dev/null\n+++ b/generated-sites/soggy-doggy/index.html\n",
        "validation": {
            "status": "failed",
            "checks": [
                {"name": "html_inline_css", "status": "failed", "detail": "missing"}
            ],
            "failures": ["html_inline_css: missing"],
        },
    }

    response = asyncio.run(
        contract.build_code_artifact_response(
            "apply the patch",
            session_messages=[
                {
                    "role": "assistant",
                    "content": "Patch proposal draft.",
                    "metadata": {"artifact_patch_proposal": invalid_proposal},
                }
            ],
            session_metadata={},
        )
    )

    assert response is not None
    assert "validation failed" in response["visible_text"].lower()
    assert not (tmp_path / "generated-sites" / "soggy-doggy" / "index.html").exists()

def test_site_bundle_intent_detects_multi_page_website() -> None:
    from core.brain import site_bundle as sb

    assert sb.is_site_bundle_request("generate a multi-page website for tony's tavern")
    assert sb.is_site_bundle_request("preview a full website for the fuze boxx")
    assert sb.is_site_bundle_request(
        "generate a 5 page website for tony's tavern biker bar"
    )
    assert sb.is_site_bundle_request("create a website artifact tonys tavern")
    assert not sb.is_site_bundle_request("create a website for tonys tavern")
    assert not sb.is_site_bundle_request("build a website for tonys tavern")
    assert not sb.is_site_bundle_request(
        "create a html artifact tony's tavern biker bar"
    )
    assert sb.is_site_bundle_request("draft a website for tony")

def test_site_bundle_single_file_prompt_does_not_trigger_bundle() -> None:
    from core.brain import site_bundle as sb
    from core.brain.answer_contract import AnswerContract

    ac = AnswerContract()
    assert not sb.is_site_bundle_request(
        "create a html artifact tonys tavern biker bar using black orange yellow"
    )
    assert ac.is_code_artifact_request("create a html artifact tonys tavern biker bar")

def test_site_bundle_default_pages_tavern() -> None:
    from core.brain import site_bundle as sb

    pages = sb.default_pages_for_business(
        "Tony's Tavern", "create a website for Tony's Tavern biker bar"
    )
    assert "index.html" in pages
    assert "menu.html" in pages
    assert "events.html" in pages
    assert "contact.html" in pages
    assert "assets/site.css" in pages

def test_site_bundle_default_pages_service_business() -> None:
    from core.brain import site_bundle as sb

    pages = sb.default_pages_for_business(
        "Acme Locksmith", "create a website for Acme Locksmith"
    )
    assert "index.html" in pages
    assert "services.html" in pages
    assert "gallery.html" in pages
    assert "contact.html" in pages
    assert "assets/site.css" in pages

def test_site_bundle_default_pages_keep_rich_defaults_with_single_requested_page() -> (
    None
):
    from core.brain import site_bundle as sb

    pages = sb.default_pages_for_business(
        "Syfernetics",
        "generate a website for Syfernetics and include a faq page",
    )

    assert "index.html" in pages
    assert "services.html" in pages
    assert "gallery.html" in pages
    assert "contact.html" in pages
    assert "faq.html" in pages
    assert pages.index("faq.html") < pages.index("assets/site.css")

def test_site_bundle_nav_links_on_every_html_page() -> None:
    from core.brain import site_bundle as sb

    pages = ["index.html", "about.html", "menu.html", "contact.html", "assets/site.css"]
    files = sb.build_bundle_files(
        business_name="Tony's Tavern",
        slug="tonys-tavern",
        pages=pages,
        style_hints={"colors": ["#000", "#f97316", "#fff"], "styles": []},
        question="create a multi-page website",
    )
    html_files = [f for f in files if f["path"].endswith(".html")]
    assert len(html_files) >= 3
    for f in html_files:
        content = f["content"]
        assert 'href="index.html"' in content
        assert 'href="about.html"' in content
        assert 'href="contact.html"' in content

def test_site_bundle_shared_css_linked_from_html_pages() -> None:
    from core.brain import site_bundle as sb

    pages = ["index.html", "about.html", "assets/site.css"]
    files = sb.build_bundle_files(
        business_name="Fuze Boxx",
        slug="fuze-boxx",
        pages=pages,
        style_hints={"colors": [], "styles": []},
        question="website",
    )
    html_files = [f for f in files if f["path"].endswith(".html")]
    for f in html_files:
        assert "site.css" in f["content"], f"{f['path']} missing CSS link"

def test_site_bundle_business_name_in_every_html_page() -> None:
    from core.brain import site_bundle as sb

    pages = ["index.html", "about.html", "menu.html", "contact.html", "assets/site.css"]
    files = sb.build_bundle_files(
        business_name="Tony's Tavern",
        slug="tonys-tavern",
        pages=pages,
        style_hints={"colors": [], "styles": []},
        question="website",
    )
    html_files = [f for f in files if f["path"].endswith(".html")]
    for f in html_files:
        assert "tony" in f["content"].lower(), f"{f['path']} missing business name"
