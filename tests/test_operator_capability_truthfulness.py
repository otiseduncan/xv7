from __future__ import annotations

from core.brain.answer_contract import AnswerContract
from core.brain.manager import BrainContextManager
from core.brain.schema import BrainLayer
from core.operator.slash_commands import get_tool_capability_summary


def _layer_map() -> dict[BrainLayer, object]:
    manager = BrainContextManager()
    records = manager.loader.load_active_records()
    return manager._highest_priority_by_layer(records)


def test_capability_summary_separates_implemented_and_stubbed_tools() -> None:
    summary = get_tool_capability_summary()

    implemented_read_only = set(summary["implemented_read_only_tools"])
    implemented_operator = set(summary["implemented_operator_tools"])
    stubbed_read_only = set(summary["stubbed_read_only_tools"])
    stubbed_operator = set(summary["stubbed_operator_tools"])

    assert implemented_read_only
    assert implemented_operator
    assert stubbed_read_only or stubbed_operator
    assert implemented_read_only.isdisjoint(stubbed_read_only)
    assert implemented_operator.isdisjoint(stubbed_operator)
    assert "/scan-system" in implemented_read_only
    assert "/vscode-open-file" in stubbed_read_only


def test_capability_summary_reports_counts_consistently() -> None:
    summary = get_tool_capability_summary()

    expected_implemented = len(summary["implemented_read_only_tools"]) + len(
        summary["implemented_operator_tools"]
    )
    expected_stubbed = len(summary["stubbed_read_only_tools"]) + len(
        summary["stubbed_operator_tools"]
    )

    assert summary["total_implemented"] == expected_implemented
    assert summary["total_stubbed"] == expected_stubbed


def test_capabilities_answer_is_truthful_about_unwired_modules() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "What are your current capabilities?",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    lowered = answer.lower()
    assert "read-only tools" in lowered
    assert "operator/mutation tools" in lowered
    assert "roadmap/stubbed tools" in lowered
    assert "live internet browsing" in lowered
    assert "email connectors" in lowered
    assert "calendar scheduling" in lowered
    assert "vs code control commands" in lowered
    assert "filesystem mutation is only available" in lowered


def test_capabilities_answer_marks_stubbed_tools_as_roadmap() -> None:
    contract = AnswerContract()
    answer = contract.try_answer(
        "what can you currently do",
        records_by_layer=_layer_map(),
        session_metadata={},
    )

    assert answer is not None
    lowered = answer.lower()
    assert "roadmap/stubbed tools" in lowered
    assert "/vscode-open-file" in lowered
    assert "/scan-system" in lowered
