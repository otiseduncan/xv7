from __future__ import annotations

import asyncio
import pytest

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
        "Generate a small HTML code artifact for a one-page \"Flow Flowers\" website. "
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
    assert response["provenance"]["artifact_validation"] == "passed"


def test_code_artifact_generation_falls_back_when_model_invalid(monkeypatch) -> None:
    contract = AnswerContract()
    prompt = (
        "Generate a small HTML code artifact for a one-page \"Rico's Mobile Detailing\" website. "
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
    assert response["provenance"]["artifact_generation"] == "deterministic_prompt_template_fallback"
    assert response["provenance"]["fallback_reason"] == "html_shell_missing"
    assert "Rico's Mobile Detailing" in response["code_artifact"]["content"]


def test_code_artifact_generation_falls_back_on_timeout(monkeypatch) -> None:
    contract = AnswerContract()
    prompt = (
        "Generate a small HTML code artifact for a one-page \"Crimson Turtle Locksmiths\" website. "
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
    assert response["provenance"]["artifact_generation"] == "deterministic_prompt_template_fallback"
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
                "Generate a small HTML code artifact for a one-page \"Crimson Turtle Locksmiths\" website. "
                "Use black, red, and silver colors, make it trustworthy and urgent."
            ),
            filename="index.html",
            language="html",
            previewable=True,
            apply_requested=False,
            business_name="Crimson Turtle Locksmiths",
            style_hints={"colors": ["black", "red", "silver"], "styles": ["trustworthy", "urgent"]},
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
    assert any(token in lowered for token in ("locksmith", "security", "key", "lock", "emergency", "lockout"))
    assert any(token in lowered for token in ("black", "dark", "#000", "#111"))
    assert "red" in lowered or "#dc2626" in lowered
    assert any(token in lowered for token in ("silver", "gray", "grey", "metal", "#9ca3af"))
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
    assert any(token in lowered for token in ("groom", "pet", "dog", "bath", "wash", "trim", "fur", "paw"))
    assert "white" in lowered or "#ffffff" in lowered
    assert "purple" in lowered or "#7c3aed" in lowered or "#a855f7" in lowered
    assert "green" in lowered or "#22c55e" in lowered
    assert "local business website" not in lowered
    assert "a clean one-page website with a clear offer and simple call to action." not in content
    for forbidden in ("harry", "flow flowers", "rico", "neon byte", "crimson turtle"):
        assert forbidden not in lowered


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


def test_generation_fallback_raises_when_template_cannot_pass_validation(monkeypatch) -> None:
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
        staticmethod(lambda filename, language, question: "<!doctype html><html><head><style>body{background:black;color:red;}</style></head><body><h1>Local Business Website</h1><p>A clean one-page website with a clear offer and simple call to action.</p></body></html>"),
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

    monkeypatch.setattr(AnswerContract, "_generate_artifact_with_local_model", _fake_generate_failure)

    with pytest.raises(RuntimeError, match="artifact generation failed validation"):
        asyncio.run(
            contract.build_code_artifact_response(
                "generate a small HTML artifact for Soggy Doggy grooming using white purple and green"
            )
        )


def test_artifact_generation_retry_prompt_includes_missing_requirements(monkeypatch) -> None:
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
            style_hints={"colors": ["black", "red", "silver"], "styles": ["trustworthy", "urgent"]},
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

    assert contract._tool_intent_category("change the text on the website to script") is None
    artifact, source = contract._latest_assistant_artifact(session_messages, {})
    assert artifact is not None
    assert source == "latest session artifact"
    assert contract._looks_like_artifact_edit("change the text on the website to script") is True
    assert contract.SMS_EXPLICIT_SEND_PATTERN.search("change the text on the website to script") is None


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

    monkeypatch.setattr(AnswerContract, "_revise_artifact_with_local_model", _fake_revise)

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
    assert response["provenance"]["artifact_validation"] == "passed"
    assert response["provenance"]["source_artifact"] == "latest session artifact"


def test_build_code_artifact_response_revision_uses_deterministic_fallback(monkeypatch) -> None:
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

    monkeypatch.setattr(AnswerContract, "_revise_artifact_with_local_model", _fake_revise)
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
    assert artifact["filename"] == "index.html"
    assert artifact["language"] == "html"
    assert artifact["previewable"] is True
    assert artifact["applied"] is False
    assert "#d4af37" in artifact["content"] or "gold" in artifact["content"].lower()
    assert "premium" in artifact["content"].lower()
    assert response["provenance"]["artifact_generation"] == "deterministic_prompt_template_fallback"
    assert response["provenance"]["model_used"] == "qwen3:14b"
    assert response["provenance"]["source_artifact"] == "latest session artifact"
    assert "artifact revision fallback" in response["provenance"]["fallback_reason"]


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
