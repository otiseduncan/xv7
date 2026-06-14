from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.operator.actions.patch_report import operator_patch_report
from core.operator.registry import run_action


APPROVAL = {"approved": True, "approval_id": "APP-PATCH-1"}


def test_patch_report_preview_does_not_mutate_file(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "example.md"
    target.parent.mkdir()
    target.write_text("old\n", encoding="utf-8")

    result = operator_patch_report(
        action_id="OP-PATCH-1",
        repo_root=tmp_path,
        request={
            "mode": "preview",
            "changes": [{"path": "docs/example.md", "content": "new\n"}],
        },
    )

    assert result.status == "success"
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert target.read_text(encoding="utf-8") == "old\n"
    assert result.data["changed_files"] == ["docs/example.md"]
    assert result.data["approval_required"] is True
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False
    assert any("-old" in line for line in result.data["file_results"][0]["diff"])
    assert any("+new" in line for line in result.data["file_results"][0]["diff"])


def test_patch_report_approved_apply_mutates_allowed_repo_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "core" / "demo.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")

    result = operator_patch_report(
        action_id="OP-PATCH-2",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "approval": APPROVAL,
            "changes": [{"path": "core/demo.py", "content": "VALUE = 2\n"}],
        },
    )

    assert result.status == "success"
    assert result.safety.read_only is False
    assert result.safety.mutates_files is True
    assert result.safety.mutates_git is False
    assert target.read_text(encoding="utf-8") == "VALUE = 2\n"
    assert result.data["changed_files"] == ["core/demo.py"]
    assert result.data["validation_recommended"] is True
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_patch_report_apply_without_repo_approval_is_blocked(
    tmp_path: Path,
) -> None:
    target = tmp_path / "core" / "demo.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")

    result = operator_patch_report(
        action_id="OP-PATCH-3",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "changes": [{"path": "core/demo.py", "content": "VALUE = 2\n"}],
        },
    )

    assert result.status == "denied"
    assert result.safety.requires_approval is True
    assert "approval is required" in result.stderr_summary
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_patch_report_sandbox_write_is_limited_to_sandbox_root(
    tmp_path: Path,
) -> None:
    sandbox_root = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    result = operator_patch_report(
        action_id="OP-PATCH-4",
        repo_root=tmp_path / "repo",
        request={
            "mode": "apply",
            "sandbox_root": str(sandbox_root),
            "changes": [
                {
                    "scope": "sandbox",
                    "path": "site/index.html",
                    "content": "<h1>ok</h1>\n",
                }
            ],
        },
    )

    assert result.status == "success"
    assert (sandbox_root / "site" / "index.html").read_text(
        encoding="utf-8"
    ) == "<h1>ok</h1>\n"
    assert not outside.exists()
    assert result.data["file_results"][0]["scope"] == "sandbox"
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False

    blocked = operator_patch_report(
        action_id="OP-PATCH-5",
        repo_root=tmp_path / "repo",
        request={
            "mode": "apply",
            "sandbox_root": str(sandbox_root),
            "changes": [
                {
                    "scope": "sandbox",
                    "path": "../outside/index.html",
                    "content": "bad\n",
                }
            ],
        },
    )

    assert blocked.status == "denied"
    assert "outside-root" in blocked.stderr_summary
    assert not (tmp_path / "outside" / "index.html").exists()


def test_patch_report_blocks_outside_root_path(tmp_path: Path) -> None:
    result = operator_patch_report(
        action_id="OP-PATCH-6",
        repo_root=tmp_path,
        request={
            "mode": "preview",
            "changes": [{"path": "../escape.txt", "content": "bad\n"}],
        },
    )

    assert result.status == "denied"
    assert result.safety.read_only is True
    assert "outside-root" in result.stderr_summary
    assert result.data["file_results"][0]["scope"] == "blocked"


def test_patch_report_blocks_protected_local_only_compose_by_default(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    result = operator_patch_report(
        action_id="OP-PATCH-7",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "approval": APPROVAL,
            "changes": [{"path": "docker-compose.yml", "content": "bad: true\n"}],
        },
    )

    assert result.status == "denied"
    assert result.data["file_results"][0]["scope"] == "local_only"
    assert "protected local-only" in result.stderr_summary
    assert compose.read_text(encoding="utf-8") == "services: {}\n"


def test_patch_report_blocks_sensitive_env_file(tmp_path: Path) -> None:
    result = operator_patch_report(
        action_id="OP-PATCH-8",
        repo_root=tmp_path,
        request={
            "mode": "apply",
            "approval": APPROVAL,
            "changes": [{"path": ".env", "content": "TOKEN=secret\n"}],
        },
    )

    assert result.status == "denied"
    assert "sensitive target" in result.stderr_summary
    assert not (tmp_path / ".env").exists()
    assert result.data["commit_created"] is False
    assert result.data["push_performed"] is False


def test_patch_report_is_available_through_registry(tmp_path: Path) -> None:
    payload = {
        "mode": "preview",
        "changes": [{"path": "README.md", "content": "hello\n"}],
    }

    result = run_action(
        "operator_patch_report",
        action_id="OP-PATCH-9",
        repo_root=tmp_path,
        target=json.dumps(payload),
    )

    assert result.status == "success"
    assert result.action_name == "operator_patch_report"
    assert result.data["target_files"] == ["README.md"]
    assert not (tmp_path / "README.md").exists()


def test_run_action_patch_report_requires_json_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a target JSON payload"):
        run_action(
            "operator_patch_report",
            action_id="OP-PATCH-10",
            repo_root=tmp_path,
            target=None,
        )
