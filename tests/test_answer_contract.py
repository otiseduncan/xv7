from __future__ import annotations

import asyncio
from typing import Any

from core.brain import site_bundle as sb
from core.brain.answer_contract import AnswerContract
from core.brain.manager import BrainContextManager
from core.brain.schema import BrainLayer
from core.runtime.model_registry import RuntimeRoleModelResolution


def _layer_map() -> dict[BrainLayer, object]:
    manager = BrainContextManager()
    records = manager.loader.load_active_records()
    return manager._highest_priority_by_layer(records)


def test_beta_readiness_answer_does_not_overclaim() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "Are we beta ready?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert "do not have proof" in answer.lower()
    assert "unverified" in answer.lower()


def test_repo_check_question_requires_live_proof() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "Did you check the repo?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert "do not have proof of a live repo check" in answer.lower()


def test_model_question_requires_receipt_proof() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "What model are you using?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert "brain/policy layer" in answer


def test_model_question_uses_receipt_when_present() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "What model are you using?",
        records_by_layer=_layer_map(),
        session_metadata={"model_use_receipt": {"model_tag": "qwen3:14b"}},
    )

    assert answer is not None
    assert "model tag is qwen3:14b" in answer


def test_guess_is_labeled_unverified() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "Make a guess about what is next.",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert answer.startswith("Guess (unverified):")


def test_active_focus_answer_uses_b51_transition_focus() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "What are we working on right now?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert "B9.8" in answer
    assert "local host scan bridge" in answer.lower()


def test_user_name_answer_comes_from_memory() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "What is my name?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer == "Your name is Otis Duncan."


def test_vs_code_prompt_help_is_allowed_not_denied() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "Can you help write implementation prompts for VS Code/Copilot?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert "implementation prompts" in answer.lower()
    assert "denied" not in answer.lower()


def test_ui_self_knowledge_answers_are_direct() -> None:
    contract = AnswerContract()

    mic = contract.try_answer(
        "Do you have a microphone button?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )
    autosend = contract.try_answer(
        "Does the mic auto-send?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )
    theme = contract.try_answer(
        "What color theme are we using?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert mic is not None and "yes" in mic.lower()
    assert autosend is not None and "does not auto-send" in autosend.lower()
    assert theme is not None and "neon-blue" in theme.lower()


def test_operator_readiness_model_proof_answer_is_cautious() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "What model was proven during operator readiness?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    assert "qwen3:14b" in answer
    assert "not necessarily this exact response" in answer


def test_identity_answers_are_deterministic_and_pronunciation_safe() -> None:
    contract = AnswerContract()
    records = _layer_map()

    name = contract.try_answer(
        "What is your name?",
        records_by_layer=records,
        session_metadata={},
    )
    pronounce = contract.try_answer(
        "How do you pronounce your name?",
        records_by_layer=records,
        session_metadata={},
    )
    spell = contract.try_answer(
        "How do you spell your name?",
        records_by_layer=records,
        session_metadata={},
    )
    who = contract.try_answer(
        "Who are you?",
        records_by_layer=records,
        session_metadata={},
    )

    assert name == "My name is Xoduz."
    assert "pronounced" not in name.lower()
    assert pronounce == "Xoduz is pronounced Exodus."
    assert spell == "X-O-D-U-Z."
    assert "I am Xoduz" in who
    assert "personal ai assistant" in who.lower()
    assert "technical co-pilot" in who.lower()


def test_spelling_correction_prompts_are_deterministic() -> None:
    contract = AnswerContract()
    records = _layer_map()

    plain = contract.try_answer(
        "Is your name spelled Exodus",
        records_by_layer=records,
        session_metadata={},
    )
    explicit = contract.try_answer(
        "Is your name spelled E-X-O-D-U-S",
        records_by_layer=records,
        session_metadata={},
    )

    assert plain == "No. My name is spelled X-O-D-U-Z. It is pronounced Exodus."
    assert explicit == (
        "No. That is the standard spelling of the word Exodus, but my name is Xoduz, "
        "spelled X-O-D-U-Z, and pronounced Exodus."
    )


def test_creator_and_purpose_answers_are_deterministic() -> None:
    contract = AnswerContract()
    records = _layer_map()

    creator = contract.try_answer(
        "Who created you?",
        records_by_layer=records,
        session_metadata={},
    )
    built = contract.try_answer(
        "Why were you built?",
        records_by_layer=records,
        session_metadata={},
    )
    purpose = contract.try_answer(
        "What is your purpose?",
        records_by_layer=records,
        session_metadata={},
    )
    who_is_otis = contract.try_answer(
        "Who is Otis?",
        records_by_layer=records,
        session_metadata={},
    )

    assert (
        creator == "I was created by Otis Duncan for the XV7 project under Syfernetics."
    )
    assert "Otis Duncan" in built
    assert "personal ai assistant" in built.lower()
    assert "technical co-pilot" in built.lower()
    assert "everyday life and technical work" in purpose.lower()
    assert (
        who_is_otis == "Otis Duncan is my creator/operator and the human directing XV7."
    )


def test_become_family_medical_and_sms_answers_follow_personal_assistant_identity() -> (
    None
):
    contract = AnswerContract()
    records = _layer_map()

    become = contract.try_answer(
        "What are you supposed to become?",
        records_by_layer=records,
        session_metadata={},
    )
    sms = contract.try_answer(
        "Can you text someone for me?",
        records_by_layer=records,
        session_metadata={},
    )
    family = contract.try_answer(
        "Do you know my family?",
        records_by_layer=records,
        session_metadata={},
    )
    medical = contract.try_answer(
        "Do you know my medical history?",
        records_by_layer=records,
        session_metadata={},
    )

    assert become is not None
    assert "personal ai assistant" in become.lower()
    assert "best-friend" in become.lower()
    assert "technical co-pilot" in become.lower()
    assert "female companion" not in become.lower()
    assert "companion" not in become.lower()

    assert sms is not None
    assert "can't send texts yet" in sms.lower()
    assert "sms connector" in sms.lower()
    assert "explicit approval" in sms.lower()

    assert family is not None
    assert "explicitly added to memory" in family.lower()
    assert "private" in family.lower()

    assert medical is not None
    assert "explicitly approve" in medical.lower()
    assert "sensitive" in medical.lower()
    assert "private tagging" in medical.lower()


def test_missing_tool_answers_are_honest_and_useful() -> None:
    contract = AnswerContract()
    records = _layer_map()

    reminder = contract.try_answer(
        "Set me a reminder for tomorrow at 5:00 p.m. to take out the trash",
        records_by_layer=records,
        session_metadata={},
    )
    weather = contract.try_answer(
        "What's the weather forecast today for Milledgeville Georgia?",
        records_by_layer=records,
        session_metadata={},
    )
    email = contract.try_answer(
        "Check my email",
        records_by_layer=records,
        session_metadata={},
    )

    assert reminder is not None
    assert "can't create live reminders yet" in reminder.lower()
    assert "reminder tool wired in" in reminder.lower()
    assert "personal-assistant roadmap" in reminder.lower()
    assert "reminders module" in reminder.lower()
    assert "tomorrow at 5:00" in reminder.lower()
    assert "use a calendar app" not in reminder.lower()
    assert "was set" not in reminder.lower()

    assert weather is not None
    assert "can't fetch live weather" in weather.lower()
    assert "weather connector" in weather.lower()
    assert "everyday-assistant roadmap" in weather.lower()
    assert "milledgeville" not in weather.lower() or "forecast" in weather.lower()

    assert email is not None
    assert "can't check email yet" in email.lower()
    assert "authorized email connector" in email.lower()
    assert "personal-assistant roadmap" in email.lower()
    assert "read-only inbox access" in email.lower()


def test_missing_tool_answers_do_not_fall_back_to_context_or_external_apps() -> None:
    contract = AnswerContract()
    records = _layer_map()

    for prompt in (
        "Set me a reminder for tomorrow at 5:00 p.m. to take out the trash",
        "What's the weather forecast today for Milledgeville Georgia?",
        "Check my email",
        "Can you text someone for me?",
        "Do you know my family?",
        "Do you know my medical history?",
    ):
        answer = contract.try_answer(
            prompt,
            records_by_layer=records,
            session_metadata={},
        )
        assert answer is not None
        lowered = answer.lower()
        assert "context does not specify" not in lowered
        assert "use a calendar app" not in lowered
        assert "use another app" not in lowered
        assert "my focus is app development" not in lowered
        assert "i already" not in lowered
        assert "i checked" not in lowered


def test_hardware_temperature_prompt_is_not_misrouted_to_weather() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "Scan CPU temperature and usage right now",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    # Should defer to operator routing rather than emitting weather fallback text.
    assert answer is None


def test_gpu_temperature_prompt_is_not_misrouted_to_weather() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "Check GPU temperature",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is None


def test_identity_contract_answers_do_not_include_receipt_text() -> None:
    contract = AnswerContract()
    records = _layer_map()

    for prompt in (
        "What is your name?",
        "Who are you?",
        "How do you pronounce your name?",
        "How do you spell your name?",
        "Is your name spelled Exodus?",
        "Is your name spelled E-X-O-D-U-S?",
        "Who created you?",
        "Why were you built?",
        "What is your purpose?",
    ):
        answer = contract.try_answer(
            prompt,
            records_by_layer=records,
            session_metadata={},
        )
        assert answer is not None
        lowered = answer.lower()
        assert "context receipt:" not in lowered
        assert "operator receipt:" not in lowered


def test_no_identity_answer_contains_companion() -> None:
    """Companion must never appear in normal identity/purpose answers."""
    contract = AnswerContract()
    records = _layer_map()

    for prompt in (
        "What is your name?",
        "Who are you?",
        "Why were you built?",
        "What is your purpose?",
        "What are you supposed to become?",
        "Who is Otis?",
    ):
        answer = contract.try_answer(
            prompt,
            records_by_layer=records,
            session_metadata={},
        )
        assert answer is not None, f"No answer returned for: {prompt}"
        assert "companion" not in answer.lower(), (
            f"'companion' found in answer to '{prompt}': {answer!r}"
        )


def test_relationship_and_gender_answers_are_deterministic() -> None:
    contract = AnswerContract()
    records = _layer_map()

    female = contract.try_answer(
        "Are you female?", records_by_layer=records, session_metadata={}
    )
    companion_q = contract.try_answer(
        "Are you my companion?", records_by_layer=records, session_metadata={}
    )
    relationship = contract.try_answer(
        "What is your relationship to me?",
        records_by_layer=records,
        session_metadata={},
    )

    assert female is not None
    assert "yes" in female.lower()
    assert "female" in female.lower()

    assert companion_q is not None
    assert "personal ai assistant" in companion_q.lower()
    assert "best-friend" in companion_q.lower()
    assert "not a romantic" in companion_q.lower()
    assert "companion" in companion_q.lower()  # allowed only in this denial context
    assert "romantic" in companion_q.lower()  # explains what it is NOT

    assert relationship is not None
    assert "personal ai assistant" in relationship.lower()
    assert "best-friend" in relationship.lower()
    assert "technical co-pilot" in relationship.lower()
    assert "operator partner" in relationship.lower()
    assert "companion" not in relationship.lower()


def test_local_capability_prompts_are_phase_accurate() -> None:
    contract = AnswerContract()
    records = _layer_map()

    local_caps = contract.try_answer(
        "what can you do locally",
        records_by_layer=records,
        session_metadata={},
    )
    scan_system = contract.try_answer(
        "can you scan my system",
        records_by_layer=records,
        session_metadata={},
    )
    run_ps = contract.try_answer(
        "can you run powershell",
        records_by_layer=records,
        session_metadata={},
    )

    assert local_caps is not None
    assert "read-only scans can run in normal mode" in local_caps.lower()
    assert "mutation requires operator mode" in local_caps.lower()

    assert scan_system is not None
    assert "local scan bridge" in scan_system.lower()
    assert "local host scan bridge" in scan_system.lower()

    assert run_ps is not None
    assert "not as an unrestricted shell" in run_ps.lower()
    assert "powershell/cmd-backed scan actions" in run_ps.lower()


def test_code_artifact_generation_uses_local_model_path(monkeypatch) -> None:
    contract = AnswerContract()
    prompt = (
        'Generate a small HTML code artifact for a one-page "Flow Flowers" website. '
        "Use soft pink, cream, and gold colors with an elegant script-style heading. "
        "Return it as a code artifact with filename index.html, language html, previewable true, "
        "and do not apply it to the repo."
    )

    called: dict[str, bool] = {"value": False}

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
        called["value"] = True
        return (
            "<!doctype html><html><head><style>body{background:pink;color:gold;}</style></head>"
            "<body><h1>Flow Flowers</h1><p>elegant floral service</p></body></html>",
            "fake-code-model:test",
        )

    monkeypatch.setattr(
        AnswerContract,
        "_generate_artifact_with_local_model",
        _fake_generate,
    )

    response = asyncio.run(contract.build_code_artifact_response(prompt))
    assert response is not None
    assert called["value"] is True
    assert response["code_artifact"]["content"].startswith("<!doctype html>")
    assert response["code_artifact"]["filename"] == "index.html"
    assert response["code_artifact"]["language"] == "html"
    assert response["provenance"]["artifact_generation"] == "local_model"
    assert response["provenance"]["model_used"] == "fake-code-model:test"
    assert response["provenance"]["artifact_validation"] in {"passed", "repaired"}


def test_code_artifact_generation_falls_back_when_model_invalid(monkeypatch) -> None:
    contract = AnswerContract()
    prompt = (
        'Generate a small HTML code artifact for a one-page "Rico\'s Mobile Detailing" website. '
        "Return it as a code artifact with filename index.html, language html, previewable true, "
        "and do not apply it to the repo."
    )

    async def _failing_generate(
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
        raise RuntimeError("html_shell_missing")

    monkeypatch.setattr(
        AnswerContract,
        "_generate_artifact_with_local_model",
        _failing_generate,
    )

    response = asyncio.run(contract.build_code_artifact_response(prompt))
    assert response is not None
    assert (
        response["provenance"]["artifact_generation"]
        == "deterministic_prompt_template_fallback"
    )
    assert response["provenance"]["fallback_reason"] == "html_shell_missing"
    assert "Rico's Mobile Detailing" in response["code_artifact"]["content"]


def test_code_artifact_generation_falls_back_on_timeout(monkeypatch) -> None:
    contract = AnswerContract()
    prompt = (
        'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. '
        "Return it as a code artifact with filename index.html, language html, previewable true, "
        "and do not apply it to the repo."
    )

    async def _timeout_generate(
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
        raise TimeoutError("Timed out while calling local model")

    monkeypatch.setattr(
        AnswerContract,
        "_generate_artifact_with_local_model",
        _timeout_generate,
    )

    response = asyncio.run(contract.build_code_artifact_response(prompt))
    assert response is not None
    assert (
        response["provenance"]["artifact_generation"]
        == "deterministic_prompt_template_fallback"
    )
    assert "timed out" in response["provenance"]["fallback_reason"].lower()


def test_artifact_validation_blocks_stale_business_leakage() -> None:
    contract = AnswerContract()
    content = (
        "<!doctype html><html><head><style>body{background:black;color:red;}</style></head>"
        "<body><h1>Crimson Turtle Locksmiths</h1><p>Flow Flowers special deal</p></body></html>"
    )
    valid, reason = contract._validate_artifact_content(
        content=content,
        language="html",
        business_name="Crimson Turtle Locksmiths",
        style_hints={"colors": ["black", "red"], "styles": []},
        requested_question="Generate one-page site for Crimson Turtle Locksmiths.",
    )
    assert valid is False
    assert reason == "stale_business_leak_detected"


def test_local_model_generation_tries_secondary_endpoint(monkeypatch) -> None:
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
        lambda: ["http://ollama:11434", "http://127.0.0.1:11434"],
    )

    calls: list[str] = []

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
            calls.append(self.base_url)
            if self.base_url.startswith("http://ollama"):
                import httpx

                raise httpx.ConnectError(
                    "[Errno 11001] getaddrinfo failed",
                    request=httpx.Request("POST", f"{self.base_url}{path}"),
                )
            return _FakeResponse(
                {
                    "message": {
                        "content": "<!doctype html><html><head><style>body{background:black;color:red;} .metal{color:silver;}</style></head><body><h1>Crimson Turtle Locksmiths</h1><p>trustworthy urgent locksmith service</p></body></html>"
                    }
                }
            )

    monkeypatch.setattr("core.brain.answer_contract.httpx.AsyncClient", _FakeClient)

    content, model, endpoint = asyncio.run(
        contract._generate_artifact_with_local_model(
            question=(
                'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. '
                "Use black, red, and silver colors, make it trustworthy and urgent."
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
    assert endpoint == "http://127.0.0.1:11434"
    assert "Crimson Turtle Locksmiths" in content
    assert calls[0] == "http://ollama:11434"
    assert "http://127.0.0.1:11434" in calls


def test_artifact_model_connectivity_diagnostic_reports_checks(monkeypatch) -> None:
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
        lambda: ["http://ollama:11434", "http://127.0.0.1:11434"],
    )

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

        async def get(self, path: str):
            if self.base_url.startswith("http://ollama"):
                import httpx

                raise httpx.ConnectError(
                    "[Errno 11001] getaddrinfo failed",
                    request=httpx.Request("GET", f"{self.base_url}{path}"),
                )
            return _FakeResponse({"models": [{"name": "qwen3:14b"}]})

    monkeypatch.setattr("core.brain.answer_contract.httpx.AsyncClient", _FakeClient)

    payload = asyncio.run(contract.artifact_model_connectivity_diagnostic())
    assert payload["configured_endpoint"] == "http://ollama:11434"
    assert payload["resolved_model_tag"] == "qwen3:14b"
    assert payload["reachable"] is True
    assert payload["reachable_endpoint"] == "http://127.0.0.1:11434"
    assert len(payload["checks"]) == 2
    assert payload["checks"][0]["reachable"] is False
    assert payload["checks"][1]["reachable"] is True


def test_crimson_template_is_locksmith_specific_and_visual() -> None:
    contract = AnswerContract()
    content = contract._default_code_artifact_content(
        "index.html",
        "html",
        (
            'Generate a small HTML code artifact for a one-page "Crimson Turtle Locksmiths" website. '
            "Use black, red, and silver colors, make it trustworthy and urgent, and include emergency lockout service."
        ),
    )
    lowered = content.lower()

    assert "Crimson Turtle Locksmiths" in content
    assert any(
        token in lowered
        for token in ("locksmith", "security", "key", "lock", "emergency", "lockout")
    )
    assert any(token in lowered for token in ("black", "dark", "#000", "#111"))
    assert "red" in lowered or "#dc2626" in lowered
    assert any(
        token in lowered
        for token in ("silver", "gray", "grey", "metal", "#9ca3af", "#c0c0c0")
    )
    assert "trust" in lowered and "urgent" in lowered
    assert "a clean one-page website with a clear offer" not in lowered


def test_unquoted_soggy_doggy_name_and_grooming_template() -> None:
    contract = AnswerContract()
    prompt = "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"

    assert contract._extract_artifact_name(prompt) == "Soggy Doggy"
    assert contract._artifact_business_category(prompt, "Soggy Doggy") == "grooming"

    content = contract._default_code_artifact_content("index.html", "html", prompt)
    lowered = content.lower()
    assert "Soggy Doggy" in content
    assert any(
        token in lowered
        for token in ("groom", "pet", "dog", "bath", "wash", "trim", "fur", "paw")
    )
    assert "white" in lowered or "#ffffff" in lowered
    assert "purple" in lowered or "#7c3aed" in lowered or "#a855f7" in lowered
    assert "green" in lowered or "#22c55e" in lowered
    assert "local business website" not in lowered
    assert (
        "a clean one-page website with a clear offer and simple call to action."
        not in content
    )
    for forbidden in ("harry", "flow flowers", "rico", "neon byte", "crimson turtle"):
        assert forbidden not in lowered


def test_prompt_fidelity_contract_extracts_tony_tavern_prompt() -> None:
    contract = AnswerContract()
    prompt = "generate a small HTML artifact for tony tavern grooming using black yellow and green"

    payload = contract._extract_prompt_fidelity_contract(prompt)

    assert payload["requested_business_name"] == "tony tavern"
    assert payload["requested_business_type"] == "grooming"
    assert payload["requested_colors"] == ["black", "green", "yellow"]
    assert payload["artifact_intent"] == "small HTML artifact"
    assert payload["source_prompt"] == prompt


def test_explicit_artifact_intent_prioritizes_artifact_over_build_guard() -> None:
    contract = AnswerContract()

    normalized = contract._normalize(
        "create a HTML artifact Tony's Tavern and biker bar using black orange and yellow as the colors"
    )
    assert contract._has_explicit_artifact_intent(normalized) is True
    assert contract._is_repo_mutation_build_prompt(normalized) is False
    assert contract._prioritize_artifact_over_build_guard(normalized) is True


def test_site_bundle_intent_prioritizes_artifact_over_build_guard() -> None:
    contract = AnswerContract()

    normalized = contract._normalize(
        "create a 5 page website for Tony's Tavern biker bar using black orange and yellow"
    )
    assert contract._is_repo_mutation_build_prompt(normalized) is False
    assert contract._prioritize_artifact_over_build_guard(normalized) is True


def test_sandbox_build_phrases_bypass_build_guard_but_repo_mutation_does_not() -> None:
    contract = AnswerContract()

    # Plain website build prompt: classified as code_artifact, NOT sandbox_build.
    # sandbox_build only fires for explicit write/export-to-sandbox intent.
    sandbox_case = contract._normalize("build me a website for another business")
    assert contract._prioritize_artifact_over_build_guard(sandbox_case) is True
    # Code-artifact classification takes priority; sandbox build should NOT fire here.
    assert contract.is_code_artifact_request(sandbox_case) is True
    assert contract._is_sandbox_build_request(sandbox_case) is False

    protected_case = contract._normalize("create a website in the repo and commit it")
    assert contract._prioritize_artifact_over_build_guard(protected_case) is False


def test_site_bundle_requested_pages_force_index_and_preserve_common_pages() -> None:
    prompt = (
        "Create a multi-page website for Riverbend Kayak & Paddle Co. "
        "Include Menu, Specials, Catering, Locations, About, and Contact."
    )

    pages = sb.default_pages_for_business("Riverbend Kayak & Paddle Co", prompt)

    assert pages[:7] == [
        "index.html",
        "menu.html",
        "specials.html",
        "catering.html",
        "locations.html",
        "about.html",
        "contact.html",
    ]
    assert pages[-2:] == ["assets/site.css", "assets/site.js"]


def test_site_bundle_uses_relative_asset_paths() -> None:
    pages = ["index.html", "menu.html", "assets/site.css", "assets/site.js"]

    files = sb.build_bundle_files(
        business_name="Riverbend Kayak & Paddle Co",
        slug="riverbend-kayak-paddle-co",
        pages=pages,
        style_hints={"colors": [], "styles": []},
        question="Generate a website preview.",
    )
    index_html = next(item["content"] for item in files if item["path"] == "index.html")

    assert 'href="assets/site.css"' in index_html
    assert 'src="assets/site.js"' in index_html
    assert 'href="/assets/site.css"' not in index_html
    assert 'src="/assets/site.js"' not in index_html


def test_sandbox_target_resolution_uses_safe_path_containment(tmp_path) -> None:
    root = tmp_path / "sandbox"

    target, error = AnswerContract._resolve_safe_sandbox_target(
        root=root,
        target_path="demo/index.html",
    )
    assert error is None
    assert target == (root / "demo/index.html").resolve()

    escaped, error = AnswerContract._resolve_safe_sandbox_target(
        root=root,
        target_path="../sandbox-evil/index.html",
    )
    assert escaped is None
    assert error == "target path is unsafe"


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


def _artifact_session_messages(
    *, filename: str = "index.html", content: str
) -> list[dict[str, object]]:
    return [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": filename,
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": content,
                    "artifact_id": "soggy-doggy-artifact",
                    "revision_id": "soggy-doggy-artifact:r1",
                    "revision_number": 1,
                },
                "policy_provenance": {
                    "artifact_generation": "local_model",
                    "revision_number": 1,
                },
            },
        }
    ]


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


# ─── Code 21: site_bundle tests ────────────────────────────────────────────────


def test_site_bundle_intent_detects_multi_page_website() -> None:
    from core.brain import site_bundle as sb

    assert sb.is_site_bundle_request("create a multi-page website for tony's tavern")
    assert sb.is_site_bundle_request("build a full website for the fuze boxx")
    assert sb.is_site_bundle_request(
        "create a 5 page website for tony's tavern biker bar"
    )
    assert sb.is_site_bundle_request("create a website artifact tonys tavern")
    assert not sb.is_site_bundle_request(
        "create a html artifact tony's tavern biker bar"
    )
    assert not sb.is_site_bundle_request(
        "make a website for tony"
    )  # no multi-page hint without page count


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


def test_site_bundle_requested_colors_appear_in_css() -> None:
    from core.brain import site_bundle as sb

    pages = ["index.html", "assets/site.css"]
    files = sb.build_bundle_files(
        business_name="Fuze Boxx",
        slug="fuze-boxx",
        pages=pages,
        style_hints={"colors": ["#1a1a2e", "#e94560", "#f0f0f0"], "styles": []},
        question="website",
    )
    css_file = next(f for f in files if f["path"].endswith(".css"))
    assert "#1a1a2e" in css_file["content"]
    assert "#e94560" in css_file["content"]


def test_site_bundle_unsafe_paths_rejected() -> None:
    from core.brain import site_bundle as sb

    assert not sb.is_safe_bundle_path("../../../etc/passwd")
    assert not sb.is_safe_bundle_path("/absolute/path.html")
    assert not sb.is_safe_bundle_path("C:\\windows\\path.html")
    assert not sb.is_safe_bundle_path("page;rm -rf /.html")
    assert sb.is_safe_bundle_path("index.html")
    assert sb.is_safe_bundle_path("assets/site.css")


def test_site_bundle_validate_requires_entry_file() -> None:
    from core.brain import site_bundle as sb

    files = [
        {
            "path": "about.html",
            "language": "html",
            "content": "<html><body>about</body></html>",
        },
        {
            "path": "menu.html",
            "language": "html",
            "content": "<html><body>menu</body></html>",
        },
    ]
    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="",
        style_hints={},
    )
    assert not passed
    assert any("entry file" in f for f in failures)


def test_site_bundle_validate_requires_two_html_pages() -> None:
    from core.brain import site_bundle as sb

    files = [
        {
            "path": "index.html",
            "language": "html",
            "content": "<html><body>home</body></html>",
        }
    ]
    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="",
        style_hints={},
    )
    assert not passed
    assert any("2" in f or "html pages" in f.lower() for f in failures)


def test_site_bundle_generation_returns_bundle_payload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    response = asyncio.run(
        contract.build_code_artifact_response(
            "create a 5 page website for Tony's Tavern biker bar using black orange and yellow",
            session_messages=[],
            session_metadata={},
        )
    )
    assert response is not None
    site_bundle_data = response.get("site_bundle")
    assert isinstance(site_bundle_data, dict), (
        f"expected site_bundle, got: {list(response.keys())}"
    )
    assert site_bundle_data.get("artifact_type") == "site_bundle"
    assert "tony" in site_bundle_data.get("title", "").lower()
    bundle_files = (site_bundle_data.get("site_bundle") or {}).get("files", [])
    assert len(bundle_files) >= 5
    paths = [f["path"] for f in bundle_files]
    assert "index.html" in paths
    assert "menu.html" in paths or "services.html" in paths
    assert "contact.html" in paths
    assert any(p.endswith(".css") for p in paths)
    assert not response.get("code_artifact")


def test_simple_website_prompt_returns_renderable_code_artifact_payload() -> None:
    contract = AnswerContract()
    prompt = (
        "Build a website for Harry's Hot Dog Cart. "
        "Use red, yellow, white, and black. "
        "Make it fun and professional."
    )

    response = asyncio.run(
        contract.build_code_artifact_response(
            prompt,
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    artifact = response.get("code_artifact")
    assert isinstance(artifact, dict) and artifact, response
    assert artifact.get("type") == "code_artifact"
    assert artifact.get("filename") == "index.html"
    assert artifact.get("language") == "html"
    assert artifact.get("previewable") is True
    content = str(artifact.get("content") or "")
    assert "<!doctype html>" in content.lower()
    assert "harry" in content.lower()

    visible_text = str(response.get("visible_text") or "").lower()
    assert "site-bundle-draft" not in visible_text
    assert "generate a patch for this site" not in visible_text
    assert response.get("site_bundle", {}) == {}


def test_delegated_website_artifact_path_plans_without_sandbox_write(
    monkeypatch, tmp_path
) -> None:
    sandbox_root = tmp_path / "sandbox"
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(sandbox_root))

    contract = AnswerContract()
    response = asyncio.run(
        contract.build_code_artifact_response(
            (
                "Build a full multi-page website for Harry's Hot Dog Cart "
                "with menu, specials, hours, and contact. "
                "Use black, gold, and white. "
                "Include email harry@example.com. "
                "Add SEO keywords: hot dogs, catering."
            ),
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    assert response.get("code_artifact") == {}
    site_bundle_data = response.get("site_bundle")
    assert isinstance(site_bundle_data, dict), "expected site bundle payload"
    assert site_bundle_data.get("artifact_type") == "site_bundle"
    assert site_bundle_data.get("delivery_mode") is None
    assert response.get("provenance", {}).get("delivery_mode") == "chat_artifact"
    assert not sandbox_root.exists()

    project_plan = site_bundle_data.get("project_plan")
    assert isinstance(project_plan, dict)
    assert project_plan.get("slug") == "harrys-hot-dog-cart"

    content_block_plan = site_bundle_data.get("content_block_plan")
    assert isinstance(content_block_plan, dict)
    assert content_block_plan.get("profile") == "food"
    blocks = content_block_plan.get("blocks")
    assert isinstance(blocks, list)
    assert [block.get("kind") for block in blocks] == [
        "hero",
        "menu",
        "specials",
        "hours",
        "contact",
    ]

    style_plan = site_bundle_data.get("style_plan")
    assert isinstance(style_plan, dict)
    assert style_plan.get("colors") == ["black", "gold", "white"]

    build_plan = site_bundle_data.get("build_plan")
    assert isinstance(build_plan, dict)
    assert build_plan.get("ready") is True
    assert build_plan.get("business_type") == "food"
    assert build_plan.get("project") == {
        "name": "Harry's Hot Dog Cart",
        "slug": "harrys-hot-dog-cart",
    }
    assert build_plan.get("style", {}).get("colors") == [
        "black",
        "gold",
        "white",
    ]
    assert build_plan.get("contact", {}).get("email") == "harry@example.com"
    assert "catering" in build_plan.get("seo", {}).get("keywords", [])

    bundle_plan = site_bundle_data.get("bundle_plan")
    assert isinstance(bundle_plan, dict)
    assert bundle_plan.get("entrypoint") == "index.html"
    assert "pages/menu.html" in bundle_plan.get("html_files", [])

    visible_response_plan = site_bundle_data.get("visible_response_plan")
    assert isinstance(visible_response_plan, dict)
    assert visible_response_plan.get("ready_for_user") is True
    assert "index.html" in visible_response_plan.get("created_files", [])

    follow_up = asyncio.run(
        contract.build_code_artifact_response(
            "Write it to the sandbox",
            session_messages=[
                {
                    "role": "assistant",
                    "content": response.get("visible_text", ""),
                    "metadata": {"site_bundle": site_bundle_data},
                }
            ],
            session_metadata={},
        )
    )

    assert follow_up is not None
    follow_up_bundle = follow_up.get("site_bundle")
    assert isinstance(follow_up_bundle, dict)
    assert follow_up_bundle.get("delivery_mode") == "sandbox_write"
    assert follow_up.get("provenance", {}).get("delivery_mode") == "sandbox_write"
    written_paths = follow_up_bundle.get("sandbox_written_paths")
    assert isinstance(written_paths, list) and written_paths
    assert sandbox_root.exists()
    assert (sandbox_root / "harrys-hot-dog-cart" / "index.html").exists()


def test_site_bundle_generation_preserves_requested_products_and_faq_pages(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    response = asyncio.run(
        contract.build_code_artifact_response(
            (
                "Build a multi-page website for Smoky Joe's Vape and CBD. "
                "Include Home, Products, About, FAQ, and Contact pages. "
                "Use a dark premium design with green accents. "
                "Make it look like a real local retail business."
            ),
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    site_bundle_data = response.get("site_bundle")
    assert isinstance(site_bundle_data, dict), "expected site_bundle payload"
    assert site_bundle_data.get("artifact_type") == "site_bundle"
    assert site_bundle_data.get("render_mode") == "code_editor_preview"
    assert site_bundle_data.get("active_file") == "index.html"
    assert site_bundle_data.get("preview_entrypoint") == "index.html"

    files = site_bundle_data.get("files")
    assert isinstance(files, list) and files, "expected top-level files list"
    file_paths = [
        str(item.get("path") or "") for item in files if isinstance(item, dict)
    ]
    assert "index.html" in file_paths
    assert "products.html" in file_paths
    assert "about.html" in file_paths
    assert "faq.html" in file_paths
    assert "contact.html" in file_paths
    assert "services.html" not in file_paths
    assert "gallery.html" not in file_paths

    route_manifest = site_bundle_data.get("route_manifest")
    assert isinstance(route_manifest, list) and route_manifest
    route_paths = [
        str(item.get("path") or "") for item in route_manifest if isinstance(item, dict)
    ]
    assert "products.html" in route_paths
    assert "faq.html" in route_paths
    assert "services.html" not in route_paths
    assert "gallery.html" not in route_paths

    code_artifacts = response.get("code_artifacts")
    assert isinstance(code_artifacts, list) and code_artifacts
    artifact_files = [
        str(item.get("filename") or "")
        for item in code_artifacts
        if isinstance(item, dict)
    ]
    assert "index.html" in artifact_files
    assert "products.html" in artifact_files
    assert "faq.html" in artifact_files


def test_site_bundle_patch_proposal_covers_all_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    bundle_artifact = {
        "artifact_type": "site_bundle",
        "artifact_id": "tonys-tavern-bundle",
        "revision_id": "tonys-tavern-bundle:r1",
        "revision_number": 1,
        "title": "Tony's Tavern",
        "slug": "tonys-tavern",
        "entry": "index.html",
        "source_prompt": "create a website",
        "site_bundle": {
            "files": [
                {
                    "path": "index.html",
                    "language": "html",
                    "content": "<!doctype html><html><body>Tony's Tavern</body></html>",
                },
                {
                    "path": "menu.html",
                    "language": "html",
                    "content": "<!doctype html><html><body>Tony's Tavern Menu</body></html>",
                },
                {
                    "path": "assets/site.css",
                    "language": "css",
                    "content": "body { background: #000; }",
                },
            ]
        },
    }
    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate a patch for this site",
            session_messages=[
                {
                    "role": "user",
                    "content": "create a website for Tony's Tavern",
                    "metadata": {},
                },
                {
                    "role": "assistant",
                    "content": "Here is the bundle.",
                    "metadata": {"site_bundle": bundle_artifact},
                },
            ],
            session_metadata={},
        )
    )
    assert response is not None
    proposals = response.get("site_bundle_patch_proposals")
    assert isinstance(proposals, list), "expected site_bundle_patch_proposals"
    assert len(proposals) == 3
    target_paths = [p["target_path"] for p in proposals]
    assert "generated-sites/tonys-tavern/index.html" in target_paths
    assert "generated-sites/tonys-tavern/menu.html" in target_paths
    assert "generated-sites/tonys-tavern/assets/site.css" in target_paths
    assert not (tmp_path / "generated-sites" / "tonys-tavern" / "index.html").exists()


def test_site_bundle_apply_writes_all_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    bundle_artifact = {
        "artifact_type": "site_bundle",
        "slug": "tonys-tavern",
        "entry": "index.html",
    }
    proposals = [
        {
            "type": "artifact_patch_proposal",
            "proposal_id": "patch-aaa",
            "target_path": "generated-sites/tonys-tavern/index.html",
            "operation": "create",
            "language": "html",
            "applied": False,
            "requires_confirmation": True,
            "content": "<!doctype html><html><body>Tony's Tavern</body></html>",
            "diff": "",
            "validation": {"status": "passed", "checks": [], "failures": []},
        },
        {
            "type": "artifact_patch_proposal",
            "proposal_id": "patch-bbb",
            "target_path": "generated-sites/tonys-tavern/assets/site.css",
            "operation": "create",
            "language": "css",
            "applied": False,
            "requires_confirmation": True,
            "content": "body { background: #000; }",
            "diff": "",
            "validation": {"status": "passed", "checks": [], "failures": []},
        },
    ]
    response = asyncio.run(
        contract.build_code_artifact_response(
            "apply the patch",
            session_messages=[
                {"role": "user", "content": "generate a patch", "metadata": {}},
                {
                    "role": "assistant",
                    "content": "Patch proposals ready.",
                    "metadata": {
                        "site_bundle": bundle_artifact,
                        "site_bundle_patch_proposals": proposals,
                    },
                },
            ],
            session_metadata={},
        )
    )
    assert response is not None
    provenance = response.get("provenance", {})
    assert provenance.get("artifact_patch") == "bundle_applied"
    assert (tmp_path / "generated-sites" / "tonys-tavern" / "index.html").exists()
    assert (
        tmp_path / "generated-sites" / "tonys-tavern" / "assets" / "site.css"
    ).exists()


def test_site_bundle_unsafe_apply_is_blocked(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    from core.brain import site_bundle as sb

    bad_proposals = [
        {
            "target_path": "../../../evil.html",
            "operation": "create",
            "language": "html",
            "applied": False,
            "content": "<html>evil</html>",
            "validation": {"status": "passed", "checks": [], "failures": []},
        },
    ]
    written, errors = sb.apply_proposals(
        proposals=bad_proposals,
        root=tmp_path,
        resolve_fn=AnswerContract._resolve_safe_patch_target,
    )
    assert len(written) == 0, "unsafe paths must not be written"
    assert len(errors) > 0


# ─── Code 22 manual validation regression tests ────────────────────────────────


def test_plain_website_build_routes_to_chat_artifact_not_sandbox(
    monkeypatch, tmp_path
) -> None:
    """Prompt 1: 'Build me a website for Harry'_s Hot Dog Cart.'
    Expected: chat artifact only, no sandbox write, no Operator denial."""
    sandbox_root = tmp_path / "sandbox"
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(sandbox_root))

    contract = AnswerContract()
    normalized = contract._normalize("Build me a website for Harry's Hot Dog Cart.")
    # Code artifact classification must take priority over sandbox build.
    assert contract.is_code_artifact_request(normalized) is True
    assert contract._is_sandbox_build_request(normalized) is False
    assert contract._prioritize_artifact_over_build_guard(normalized) is True
    assert contract._is_repo_mutation_build_prompt(normalized) is False


def test_explicit_sandbox_write_is_not_repo_mutation() -> None:
    """Prompt 5: 'Write it to the sandbox.' must not be classified as repo mutation."""
    from core.operator.manager import OperatorManager
    import tempfile

    contract = AnswerContract()
    normalized = contract._normalize("Write it to the sandbox.")
    # Must not be classified as repo mutation.
    assert contract._is_repo_mutation_build_prompt(normalized) is False

    # Operator manager must NOT deny sandbox write intent.
    with tempfile.TemporaryDirectory() as tmp:
        manager = OperatorManager(repo_root=__import__("pathlib").Path(tmp))
        result = manager.try_handle_chat("Write it to the sandbox.")
        # try_handle_chat returns None (routes to artifact layer) or an OperatorExecution
        # whose answer does NOT claim this is a repo mutation.
        if result is not None:
            assert "implementation/repo mutation task" not in result.answer.lower()
            assert "repo mutation" not in result.answer.lower()


def test_explicit_sandbox_write_exports_active_single_code_artifact(
    monkeypatch, tmp_path
) -> None:
    """End-to-end: Build me a website → chat artifact. Then Write it to the sandbox
    → writes the active artifact to sandbox without generating a new draft."""
    sandbox_root = tmp_path / "sandbox"
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(sandbox_root))
    monkeypatch.setenv("XV7_SANDBOX_ROOT_DISPLAY", r"X:\xoduz-sandbox")

    contract = AnswerContract()

    # Simulate the state after a plain website build: active code_artifact in session.
    fake_artifact_content = (
        "<!doctype html><html><head><style>body{background:#111;color:#eee;}</style></head>"
        "<body><h1>Harry's Hot Dog Cart</h1></body></html>"
    )
    fake_artifact = {
        "type": "code_artifact",
        "artifact_type": "code_artifact",
        "artifact_id": "harrys-hot-dog-cart-artifact",
        "revision_id": "harrys-hot-dog-cart-artifact:r1",
        "revision_number": 1,
        "filename": "index.html",
        "language": "html",
        "content": fake_artifact_content,
        "previewable": True,
        "applied": False,
        "delivery_mode": "chat_artifact",
        "source_prompt": "Build me a website for Harry's Hot Dog Cart.",
    }
    session_messages = [
        {
            "role": "user",
            "content": "Build me a website for Harry's Hot Dog Cart.",
            "metadata": {},
        },
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {"code_artifact": fake_artifact},
        },
    ]

    response = asyncio.run(
        contract.build_code_artifact_response(
            "Write it to the sandbox.",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None, "Expected a response, got None"

    # Must write to sandbox, not produce a new draft.
    provenance = response.get("provenance", {})
    assert provenance.get("delivery_mode") == "sandbox_write", (
        f"Expected delivery_mode=sandbox_write, got: {provenance.get('delivery_mode')}"
    )
    assert provenance.get("artifact_generation") == "sandbox_artifact_export"

    # Must return sandbox path info.
    target_path = str(provenance.get("sandbox_target_path") or "")
    assert target_path, "Expected a sandbox_target_path in provenance"
    assert "harrys-hot-dog-cart" in target_path
    assert "index.html" in target_path
    assert "index-html" not in target_path
    assert "/app/X:" not in target_path

    # Sandbox file must actually exist on disk.
    assert sandbox_root.exists(), "sandbox root must be created"
    expected_file = sandbox_root / "harrys-hot-dog-cart" / "index.html"
    assert expected_file.exists(), f"Expected sandbox file at {expected_file}"

    # The visible text must mention the sandbox path.
    visible = str(response.get("visible_text") or "").lower()
    assert "sandbox" in visible or "harrys-hot-dog-cart" in visible

    # Must NOT be a draft artifact response.
    assert "draft" not in visible, f"Must not produce a new draft artifact: {visible}"

    # code_artifact in response must reflect sandbox_write delivery.
    result_artifact = response.get("code_artifact", {})
    assert isinstance(result_artifact, dict) and result_artifact
    assert result_artifact.get("delivery_mode") == "sandbox_write"
    assert result_artifact.get("applied") is True
    assert result_artifact.get("sandbox_project_slug") == "harrys-hot-dog-cart"


def test_sandbox_location_query_prefers_latest_sandbox_export_over_newer_chat_preview(
    monkeypatch, tmp_path
) -> None:
    sandbox_root = tmp_path / "sandbox"
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(sandbox_root))

    contract = AnswerContract()
    export_artifact = {
        "type": "code_artifact",
        "filename": "index.html",
        "language": "html",
        "content": "<!doctype html><html><body>exported</body></html>",
        "delivery_mode": "sandbox_write",
        "sandbox_root": str(sandbox_root),
        "sandbox_project_slug": "harrys-hot-dog-cart",
        "sandbox_project_path": str(sandbox_root / "harrys-hot-dog-cart"),
        "sandbox_target_path": str(sandbox_root / "harrys-hot-dog-cart" / "index.html"),
        "sandbox_written_paths": [
            str(sandbox_root / "harrys-hot-dog-cart" / "index.html")
        ],
    }
    later_chat_preview_artifact = {
        "type": "code_artifact",
        "filename": "index.html",
        "language": "html",
        "content": "<!doctype html><html><body>new draft</body></html>",
        "delivery_mode": "chat_artifact",
    }
    session_messages = [
        {
            "role": "assistant",
            "content": "Wrote the active artifact to sandbox.",
            "metadata": {"code_artifact": export_artifact},
        },
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {"code_artifact": later_chat_preview_artifact},
        },
    ]

    response = asyncio.run(
        contract.build_code_artifact_response(
            "Show me where the files went.",
            session_messages=session_messages,
            session_metadata={},
        )
    )

    assert response is not None
    visible = str(response.get("visible_text") or "").lower()
    assert "harrys-hot-dog-cart" in visible
    assert "index.html" in visible
    assert "no sandbox files were written" not in visible


def test_sandbox_location_query_returns_fast_path_from_artifact_state(
    monkeypatch, tmp_path
) -> None:
    """Prompt 6: 'Show me where the files went.' must return fast from artifact state."""
    sandbox_root = tmp_path / "sandbox"
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(sandbox_root))

    contract = AnswerContract()
    normalized = contract._normalize("Show me where the files went.")
    assert contract._is_sandbox_location_query(normalized) is True

    fake_sandbox_path = str(tmp_path / "sandbox" / "harrys-hot-dog-cart")
    fake_written = [
        str(tmp_path / "sandbox" / "harrys-hot-dog-cart" / "index.html"),
    ]
    fake_artifact: dict = {
        "artifact_type": "site_bundle",
        "delivery_mode": "sandbox_write",
        "sandbox_project_path": fake_sandbox_path,
        "sandbox_written_paths": fake_written,
    }
    response = asyncio.run(
        contract.build_code_artifact_response(
            "Show me where the files went.",
            session_messages=[
                {
                    "role": "assistant",
                    "content": "Site bundle generated.",
                    "metadata": {"site_bundle": fake_artifact},
                }
            ],
            session_metadata={},
        )
    )

    assert response is not None
    visible = str(response.get("visible_text") or "").lower()
    # Must report the sandbox path.
    assert "harrys-hot-dog-cart" in visible
    # Must NOT tell the user Operator Mode is required for sandbox files.
    assert "operator mode" not in visible
    # Must NOT claim a repo commit occurred.
    assert "commit" not in visible


def test_repo_mutation_prompt_still_protected() -> None:
    """Prompt: 'Commit this to the repo.' must still require Operator Mode.
    No sandbox write. No repo mutation without approval."""
    from core.operator.manager import OperatorManager
    import tempfile

    contract = AnswerContract()
    normalized = contract._normalize("Commit this to the repo.")
    assert contract._is_repo_mutation_build_prompt(normalized) is True
    assert contract._prioritize_artifact_over_build_guard(normalized) is False

    # Operator manager must deny this as a mutation requiring Operator Mode.
    with tempfile.TemporaryDirectory() as tmp:
        manager = OperatorManager(repo_root=__import__("pathlib").Path(tmp))
        result = manager.try_handle_chat("Commit this to the repo.")
        # Must NOT route through sandbox export path.
        # Should be a denial via operator manager (not None) or None (fallthrough to
        # implementation_task guard). Either way, it must not perform a sandbox write.
        if result is not None:
            # If the operator manager handles it, it should be a denial.
            answer = result.answer.lower()
            assert (
                "operator mode" in answer
                or "repo mutation" in answer
                or "implementation" in answer
                or "no files were changed" in answer
            ), f"Unexpected operator answer for repo mutation: {answer!r}"


def test_sandbox_build_does_not_fire_for_plain_website_prompts() -> None:
    """is_sandbox_build_request must return False for plain website generation prompts
    so they route to the chat artifact lane, not the sandbox write lane."""
    contract = AnswerContract()
    plain_website_prompts = [
        "Build me a website for Harry's Hot Dog Cart.",
        "build me a website for another business",
        "create a website for Tony's Tavern",
        "make a website for local coffee shop",
    ]
    for prompt in plain_website_prompts:
        normalized = contract._normalize(prompt)
        assert contract._is_sandbox_build_request(normalized) is False, (
            f"Expected is_sandbox_build_request=False for: {prompt!r}"
        )
        assert contract.is_code_artifact_request(normalized) is True, (
            f"Expected is_code_artifact_request=True for: {prompt!r}"
        )
