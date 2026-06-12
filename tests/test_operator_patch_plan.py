from __future__ import annotations

from pathlib import Path

from core.operator.actions.patch_plan import patch_plan


WORKSPACE = {
    "branch": "main",
    "dirty_file_count": 0,
    "detected_stack_labels": ["python", "fastapi", "frontend_static", "tests"],
    "key_files": [
        {"path": "docs/CODE_LANE_INDEX.md", "exists": True},
    ],
    "test_commands": [
        "python -m pytest tests/ -v --tb=short --asyncio-mode=auto",
    ],
    "limitations": [],
}


def test_patch_plan_is_read_only_and_plan_only(tmp_path: Path) -> None:
    result = patch_plan(
        action_id="OP-20260611-0301",
        repo_root=tmp_path,
        goal="Implement CODE-02 Patch Planner",
        workspace=WORKSPACE,
    )

    assert result.status == "success"
    assert result.action_name == "patch_plan"
    assert result.safety.allowed is True
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.safety.mutates_runtime is False
    assert result.data["mode"] == "plan_only"
    assert result.data["goal"] == "Implement CODE-02 Patch Planner"


def test_patch_plan_includes_files_tests_risk_and_approval(tmp_path: Path) -> None:
    result = patch_plan(
        action_id="OP-20260611-0302",
        repo_root=tmp_path,
        goal="Build CODE-02 patch planner",
        workspace=WORKSPACE,
    )

    assert result.data["mutation_required"] is True
    assert result.data["approval_required"] is True
    assert result.data["risk"] == "medium"
    assert "core/operator/actions/patch_plan.py" in result.data["likely_files"]
    assert "tests/test_operator_patch_plan.py" in result.data["likely_files"]
    assert any("pytest" in command for command in result.data["tests_to_run"])
    assert any("ruff" in command for command in result.data["tests_to_run"])
    assert result.data["proposed_changes"]


def test_patch_plan_uses_workspace_summary(tmp_path: Path) -> None:
    workspace = dict(WORKSPACE)
    workspace["branch"] = "feature/code-02"
    workspace["dirty_file_count"] = 2
    workspace["detected_stack_labels"] = ["python", "tests"]

    result = patch_plan(
        action_id="OP-20260611-0303",
        repo_root=tmp_path,
        goal="Plan operator command center UI",
        workspace=workspace,
    )

    assert result.data["workspace_summary"] == {
        "branch": "feature/code-02",
        "dirty_file_count": 2,
        "detected_stack_labels": ["python", "tests"],
        "limitations": [],
    }
    assert "public/app.js" in result.data["likely_files"]


def test_patch_plan_can_return_questions_for_vague_goal(tmp_path: Path) -> None:
    result = patch_plan(
        action_id="OP-20260611-0304",
        repo_root=tmp_path,
        goal="fix",
        workspace=WORKSPACE,
    )

    assert result.data["questions"] == [
        "The goal is short. Confirm the desired behavior before patching."
    ]
