from __future__ import annotations

from dataclasses import dataclass

from core.brain.session_signal_manager import SessionSignalManager


@dataclass
class Fact:
    statement: str


@dataclass
class Record:
    facts: list[Fact]


def make_record(*statements: str) -> Record:
    return Record([Fact(statement) for statement in statements])


def test_facts_returns_fact_statements() -> None:
    record = make_record("First fact.", "Second fact.")

    assert SessionSignalManager.facts(record) == ["First fact.", "Second fact."]
    assert SessionSignalManager.facts(None) == []


def test_extract_user_name_prefers_otis_duncan() -> None:
    record = make_record("The user/operator is Somebody Else.", "Name: Otis Duncan")

    assert SessionSignalManager.extract_user_name(record) == "Otis Duncan"


def test_extract_user_name_reads_operator_fact() -> None:
    record = make_record("The user/operator is Xoduz Operator.")

    assert SessionSignalManager.extract_user_name(record) == "Xoduz Operator"


def test_extract_user_name_returns_none_without_match() -> None:
    assert SessionSignalManager.extract_user_name(make_record("No name here.")) is None
    assert SessionSignalManager.extract_user_name(None) is None


def test_active_focus_summary_reads_dict_or_string() -> None:
    assert (
        SessionSignalManager.active_focus_summary(
            {"active_focus": {"summary": "Code 22 refactor"}}
        )
        == "Code 22 refactor"
    )
    assert (
        SessionSignalManager.active_focus_summary({"active_focus": " XV7 branch "})
        == "XV7 branch"
    )
    assert SessionSignalManager.active_focus_summary({"active_focus": {}}) is None


def test_normalize_reminder_request_cleans_common_prefixes() -> None:
    assert (
        SessionSignalManager.normalize_reminder_request("Remind me to call the shop.")
        == "Call the shop"
    )
    assert (
        SessionSignalManager.normalize_reminder_request(
            "Set me a reminder to check XV7 at 7:30 p.m."
        )
        == "Check XV7 at 7:30 PM"
    )


def test_normalize_reminder_request_handles_empty_details() -> None:
    assert (
        SessionSignalManager.normalize_reminder_request("Remind me to")
        == "your requested reminder details"
    )


def test_normalize_reminder_request_rewrites_time_to_separator() -> None:
    assert (
        SessionSignalManager.normalize_reminder_request(
            "Remind me to at 8:00 AM to review commits"
        )
        == "At 8:00 AM — review commits"
    )


def test_has_live_repo_check_proof_accepts_boolean() -> None:
    assert SessionSignalManager.has_live_repo_check_proof({"live_repo_check": True})
    assert not SessionSignalManager.has_live_repo_check_proof({"live_repo_check": False})


def test_has_live_repo_check_proof_accepts_tool_result() -> None:
    metadata = {"tool_results": [{"type": "Repo_Check"}]}

    assert SessionSignalManager.has_live_repo_check_proof(metadata)
    assert not SessionSignalManager.has_live_repo_check_proof({"tool_results": []})


def test_latest_model_tag_filters_policy_sources() -> None:
    assert (
        SessionSignalManager.latest_model_tag(
            {
                "model_use_receipt": {
                    "model_selection_source": "brain_records",
                    "model_tag": "llama3.1:8b",
                }
            }
        )
        is None
    )


def test_latest_model_tag_returns_cleaned_runtime_tag() -> None:
    assert (
        SessionSignalManager.latest_model_tag(
            {
                "model_use_receipt": {
                    "model_selection_source": "runtime",
                    "model_tag": " llama3.1:8b ",
                }
            }
        )
        == "llama3.1:8b"
    )


def test_latest_model_tag_filters_brain_records_tag() -> None:
    assert (
        SessionSignalManager.latest_model_tag(
            {
                "model_use_receipt": {
                    "model_selection_source": "runtime",
                    "model_tag": "xv7-brain-records",
                }
            }
        )
        is None
    )


def test_last_verified_operator_model_reads_operator_readiness_fact() -> None:
    record = make_record("Operator readiness report verified llama3.1:8b locally.")

    assert SessionSignalManager.last_verified_operator_model(record) == "llama3.1:8b"


def test_last_verified_operator_model_returns_none_without_match() -> None:
    assert SessionSignalManager.last_verified_operator_model(make_record("No model.")) is None
    assert SessionSignalManager.last_verified_operator_model(None) is None
