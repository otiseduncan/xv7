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
    assert "B5.1 provenance cleanup" in answer


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
