from __future__ import annotations

from core.brain.answer_contract import AnswerContract
from core.brain.manager import BrainContextManager
from core.brain.schema import BrainLayer


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
    assert "B8.2 brain content fill and communication routing repair" in answer


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
    assert who == "I am Xoduz, the XV7 assistant."


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

    assert creator == "I was created by Otis Duncan for the XV7 project under Syfernetics."
    assert "Otis Duncan" in built
    assert "app-development assistant and operator partner" in built
    assert "help Otis turn his ideas" in purpose
    assert who_is_otis == "Otis Duncan is my creator/operator and the human directing XV7."


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
