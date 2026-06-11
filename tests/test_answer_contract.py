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
