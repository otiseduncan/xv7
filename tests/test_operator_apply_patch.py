from __future__ import annotations

from pathlib import Path

from core.operator.actions.apply_patch import apply_approved_patch


APPROVAL = {"approved": True, "approved_by": "Otis", "approval_id": "APP-1"}


def test_apply_patch_denies_unapproved_patch(tmp_path: Path) -> None:
    result = apply_approved_patch(
        action_id="OP-20260611-0401",
        repo_root=tmp_path,
        patch={
            "source_plan_id": "PLAN-1",
            "risk": "low",
            "changes": [{"path": "docs/example.md", "content": "hello\n"}],
        },
    )

    assert result.status == "denied"
    assert result.safety.allowed is False
    assert result.safety.mutates_files is True
    assert result.safety.requires_approval is True
    assert "approval is required" in result.stderr_summary
    assert not (tmp_path / "docs" / "example.md").exists()


def test_apply_patch_denies_outside_root_path(tmp_path: Path) -> None:
    result = apply_approved_patch(
        action_id="OP-20260611-0402",
        repo_root=tmp_path,
        patch={
            "approval": APPROVAL,
            "source_plan_id": "PLAN-2",
            "risk": "high",
            "changes": [{"path": "../outside.txt", "content": "bad\n"}],
        },
    )

    assert result.status == "denied"
    assert "outside-root" in result.stderr_summary
    assert not (tmp_path.parent / "outside.txt").exists()


def test_apply_patch_denies_absolute_path(tmp_path: Path) -> None:
    absolute = tmp_path.parent / "outside-absolute.txt"
    result = apply_approved_patch(
        action_id="OP-20260611-0403",
        repo_root=tmp_path,
        patch={
            "approval": APPROVAL,
            "source_plan_id": "PLAN-3",
            "risk": "high",
            "changes": [{"path": str(absolute), "content": "bad\n"}],
        },
    )

    assert result.status == "denied"
    assert "Absolute patch paths are denied" in result.stderr_summary
    assert not absolute.exists()


def test_apply_patch_writes_approved_file_and_returns_diff(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "example.md"
    target.parent.mkdir()
    target.write_text("old\n", encoding="utf-8")

    result = apply_approved_patch(
        action_id="OP-20260611-0404",
        repo_root=tmp_path,
        patch={
            "approval": APPROVAL,
            "source_plan_id": "PLAN-4",
            "risk": "low",
            "test_commands": ["python -m pytest tests/test_operator_apply_patch.py"],
            "changes": [{"path": "docs/example.md", "content": "new\n"}],
        },
    )

    assert result.status == "success"
    assert result.mode == "operator"
    assert result.safety.read_only is False
    assert result.safety.mutates_files is True
    assert target.read_text(encoding="utf-8") == "new\n"
    assert result.data["changed_files"] == ["docs/example.md"]
    assert result.data["committed"] is False
    assert result.data["requires_commit_approval"] is True
    assert result.data["tests_recommended"] == [
        "python -m pytest tests/test_operator_apply_patch.py"
    ]
    assert result.data["file_results"][0]["before_sha256"] != result.data[
        "file_results"
    ][0]["after_sha256"]
    assert any("-old" in line for line in result.data["file_results"][0]["diff"])
    assert any("+new" in line for line in result.data["file_results"][0]["diff"])


def test_apply_patch_can_create_parent_directories_inside_repo(tmp_path: Path) -> None:
    result = apply_approved_patch(
        action_id="OP-20260611-0405",
        repo_root=tmp_path,
        patch={
            "approval": APPROVAL,
            "source_plan_id": "PLAN-5",
            "risk": "low",
            "changes": [{"path": "docs/nested/example.md", "content": "created\n"}],
        },
    )

    assert result.status == "success"
    assert (tmp_path / "docs" / "nested" / "example.md").read_text(
        encoding="utf-8"
    ) == "created\n"
    assert result.data["changed_files"] == ["docs/nested/example.md"]


def test_apply_patch_reports_noop_without_writing_change(tmp_path: Path) -> None:
    target = tmp_path / "same.txt"
    target.write_text("same\n", encoding="utf-8")

    result = apply_approved_patch(
        action_id="OP-20260611-0406",
        repo_root=tmp_path,
        patch={
            "approval": APPROVAL,
            "source_plan_id": "PLAN-6",
            "risk": "low",
            "changes": [{"path": "same.txt", "content": "same\n"}],
        },
    )

    assert result.status == "success"
    assert result.data["changed_files"] == []
    assert result.data["file_results"][0]["changed"] is False
    assert result.data["diff_summary"] == ["No content change for same.txt."]
