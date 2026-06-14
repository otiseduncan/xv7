from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from core.operator.manager import OperatorManager
from core.operator.schema import OperatorActionResult, OperatorSafety


def _result(
    *,
    action_name: str,
    action_id: str,
    repo_root: Path,
    status: str = "success",
    data: dict[str, Any] | None = None,
    stderr: str = "",
    mutates_files: bool = False,
    requires_approval: bool = False,
) -> OperatorActionResult:
    now = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name=action_name,
        mode="operator" if mutates_files else "read_only",
        status=status,  # type: ignore[arg-type]
        started_at=now,
        completed_at=now,
        command_or_operation=f"fake {action_name}",
        target=str(repo_root),
        stdout_summary="fake",
        stderr_summary=stderr,
        exit_code=0 if status == "success" else 1,
        data=(data or {}) | {"commit_created": False, "push_performed": False},
        safety=OperatorSafety(
            allowed=status != "denied",
            read_only=not mutates_files,
            mutates_files=mutates_files,
            requires_approval=requires_approval,
        ),
        receipt_label=f"{action_name} {action_id}",
    )


def test_check_repo_routes_to_operator_status_report(
    monkeypatch: Any, tmp_path: Path
) -> None:
    calls: list[str] = []

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        calls.append(action_name)
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            data={"branch": "main", "clean": True, "sync": "in_sync"},
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat("check the repo")

    assert handled is not None
    assert calls == ["operator_status_report"]
    assert handled.result.safety.mutates_files is False
    assert "repo is on main" in handled.answer.lower()


def test_run_validation_routes_to_operator_validation_report(
    monkeypatch: Any, tmp_path: Path
) -> None:
    forwarded: dict[str, Any] = {}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        forwarded["action_name"] = action_name
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            data={
                "passed": True,
                "selected_commands": [
                    "python -m ruff format --check core tests scripts"
                ],
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat("run validation")

    assert handled is not None
    assert forwarded["action_name"] == "operator_validation_report"
    assert json.loads(str(forwarded["target"])) == {"profile": "python-core"}
    assert "validation passed" in handled.answer.lower()
    assert handled.result.data["commit_created"] is False
    assert handled.result.data["push_performed"] is False


def test_fix_first_failure_routes_to_repair_report_without_commit_push_claims(
    monkeypatch: Any, tmp_path: Path
) -> None:
    forwarded: dict[str, Any] = {}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        forwarded["action_name"] = action_name
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="failed",
            data={
                "first_failure_command": "python -m ruff check core tests scripts",
                "changed_files": [],
            },
            stderr="First validation failure: python -m ruff check core tests scripts",
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "fix the first failure"
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_repair_report"
    assert json.loads(str(forwarded["target"]))["max_cycles"] == 1
    assert "concrete approved patch is required" in handled.answer.lower()
    assert "no commit or push occurred" in handled.answer.lower()
    assert handled.result.data["commit_created"] is False
    assert handled.result.data["push_performed"] is False


def test_status_prompt_does_not_mutate_files(monkeypatch: Any, tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            data={"branch": "main", "clean": True, "sync": "in_sync"},
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat("give me repo status")

    assert handled is not None
    assert marker.read_text(encoding="utf-8") == "unchanged\n"
    assert handled.result.safety.mutates_files is False


def test_patch_apply_without_approval_routes_and_is_blocked(
    monkeypatch: Any, tmp_path: Path
) -> None:
    forwarded: dict[str, Any] = {}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        forwarded["action_name"] = action_name
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="denied",
            stderr="Patch apply denied: repo mutation approval is required.",
            mutates_files=True,
            requires_approval=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)
    patch = {"changes": [{"path": "core/demo.py", "content": "VALUE = 2\n"}]}

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        f"apply this patch {json.dumps(patch)}"
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_patch_report"
    payload = json.loads(str(forwarded["target"]))
    assert payload["mode"] == "apply"
    assert "approval" not in payload
    assert handled.result.status == "denied"
    assert "denied" in handled.answer.lower()


def test_sandbox_patch_route_preserves_sandbox_scope(
    monkeypatch: Any, tmp_path: Path
) -> None:
    forwarded: dict[str, Any] = {}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        forwarded["action_name"] = action_name
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            data={
                "mode": "preview",
                "changed_files": ["site/index.html"],
                "file_results": [{"scope": "sandbox", "path": "site/index.html"}],
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)
    patch = {
        "sandbox_root": str(tmp_path / "sandbox"),
        "changes": [
            {
                "scope": "sandbox",
                "path": "site/index.html",
                "content": "<h1>ok</h1>\n",
            }
        ],
    }

    handled = OperatorManager(repo_root=tmp_path / "repo").try_handle_chat(
        f"preview this patch {json.dumps(patch)}"
    )

    assert handled is not None
    payload = json.loads(str(forwarded["target"]))
    assert forwarded["action_name"] == "operator_patch_report"
    assert payload["mode"] == "preview"
    assert payload["changes"][0]["scope"] == "sandbox"
    assert payload["sandbox_root"] == str(tmp_path / "sandbox")


def test_protected_compose_patch_route_reaches_safety_block(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="denied",
            stderr="protected local-only file is blocked by default: docker-compose.yml",
            mutates_files=True,
            requires_approval=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)
    patch = {"changes": [{"path": "docker-compose.yml", "content": "bad: true\n"}]}

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        f"apply this approved patch {json.dumps(patch)}"
    )

    assert handled is not None
    assert "protected local-only" in handled.answer
    assert not (tmp_path / "docker-compose.local.diff").exists()


def test_website_prompt_does_not_route_to_operator_lane(tmp_path: Path) -> None:
    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "Build me a multi-page website for Harry's Hot Dog Cart."
    )

    assert handled is None


def test_commit_phrases_route_to_operator_commit_report(
    monkeypatch: Any, tmp_path: Path
) -> None:
    forwarded: dict[str, Any] = {}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        forwarded["action_name"] = action_name
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="denied",
            data={
                "mode": "apply",
                "candidate_files": ["core/main.py"],
                "committed_files": [],
                "skipped_files": ["docker-compose.yml"],
                "commit_sha": "",
                "pushed": False,
            },
            stderr="Commit approval is required before mutation.",
            mutates_files=True,
            requires_approval=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "commit these changes"
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_commit_report"
    payload = json.loads(str(forwarded["target"]))
    assert payload["mode"] == "apply"
    assert payload["approval"]["approved"] is True


def test_push_phrase_routes_to_operator_commit_report_with_separate_push_approval(
    monkeypatch: Any, tmp_path: Path
) -> None:
    forwarded: dict[str, Any] = {}

    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        forwarded["action_name"] = action_name
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="denied",
            data={
                "mode": "apply",
                "candidate_files": ["core/main.py"],
                "committed_files": [],
                "skipped_files": [],
                "commit_sha": "",
                "pushed": False,
            },
            stderr="Push approval is required before push.",
            mutates_files=True,
            requires_approval=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat("push the branch")

    assert handled is not None
    assert forwarded["action_name"] == "operator_commit_report"
    payload = json.loads(str(forwarded["target"]))
    assert payload["mode"] == "apply"
    assert payload["push"] is True
    assert payload["push_approval"]["approved"] is False
