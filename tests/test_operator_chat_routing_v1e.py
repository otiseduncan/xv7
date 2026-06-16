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


def test_operator_mode_github_proof_prompt_routes_even_when_toggle_is_off(
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
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "earthx-github-proof"),
                "commit_sha": "abc1234",
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "Operator Mode: Build and push a real GitHub proof project",
        operator_mode_enabled=False,
    )

    assert handled is not None
    assert handled.result.status == "success"
    assert forwarded["action_name"] == "operator_github_proof_project"
    assert "sandbox project workflow completed" in handled.answer.lower()


def test_operator_mode_github_proof_prompt_routes_to_operator_project_action(
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
            status="success",
            data={
                "project_path": str(tmp_path / "earthx-github-proof"),
                "commit_sha": "abc1234",
                "pushed": True,
            },
            mutates_files=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "Operator Mode: Build and push a real GitHub proof project named earthx-github-proof under X:\\xoduz-sandbox\\earthx-github-proof",
        operator_mode_enabled=True,
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    payload = json.loads(str(forwarded["target"]))
    assert payload["project_name"] == "earthx-github-proof"
    assert "xoduz-sandbox" in payload["project_path"].lower()
    assert "sandbox project workflow completed" in handled.answer.lower()


def test_create_new_repository_on_github_prompt_routes_to_operator_project_action(
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
            stderr="authentication required",
            data={
                "failed_command": "gh repo create earthx-github-proof --source . --remote origin --public --push"
            },
            mutates_files=True,
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "Operator Mode: create a new repository on GitHub for this and push",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "earthx-github-proof"
                        )
                    }
                }
            ]
        },
        operator_mode_enabled=True,
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    assert "failed command" in handled.answer.lower()


def test_finish_github_push_existing_project_routes_to_operator_project_action(
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
            mutates_files=True,
            data={
                "project_path": r"X:\xoduz-sandbox\earthx-github-proof",
                "branch": "main",
                "commit_sha": "abc1234",
                "remotes": [
                    "origin\thttps://github.com/example/earthx-github-proof.git (push)"
                ],
                "status_lines": [],
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        r"finish the github push for X:\xoduz-sandbox\earthx-github-proof"
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    payload = json.loads(str(forwarded["target"]))
    assert payload["write_project_files"] is False
    assert payload["push"] is True


def test_github_workflow_missing_remote_returns_clear_repo_target_message(
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
            status="failed",
            stderr="origin remote is not configured",
            mutates_files=True,
            data={
                "missing_remote": True,
                "suggested_repo_name": "harry-s-hot-dog-cart",
                "repo_before": {
                    "branch": "main",
                    "remotes": [],
                    "status_lines": ["## main"],
                },
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "push to github",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "harry-s-hot-dog-cart"
                        )
                    }
                }
            ]
        },
    )

    assert handled is not None
    assert "has no github remote" in handled.answer.lower()
    assert (
        "create a new github repo named harry-s-hot-dog-cart" in handled.answer.lower()
    )


def test_github_workflow_missing_gh_returns_clear_install_guidance(
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
            status="failed",
            stderr="command not found: gh",
            mutates_files=True,
            data={
                "gh_missing": True,
                "gh_required_for_repo_creation": True,
                "repo_before": {
                    "branch": "main",
                    "remotes": [],
                    "status_lines": ["## main"],
                },
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "create a new repository on github and push",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "earthx-github-proof"
                        )
                    }
                }
            ]
        },
    )

    assert handled is not None
    assert "github cli is not installed" in handled.answer.lower()
    assert "existing git remote/ssh" in handled.answer.lower()


def test_slash_push_github_routes_to_operator_project_action(
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
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "earthx-github-proof"),
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "/push github",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "earthx-github-proof"
                        )
                    }
                }
            ]
        },
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"


def test_slash_github_create_routes_to_operator_project_action(
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
        forwarded["target"] = target
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "earthx-github-proof"),
                "pushed": True,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "/github create earthx-github-proof",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "earthx-github-proof"
                        )
                    }
                }
            ]
        },
    )

    assert handled is not None
    payload = json.loads(str(forwarded["target"]))
    assert payload["create_github_repo"] is True


def test_push_to_github_uses_active_exported_slug_for_repo_name(
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
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "sandbox" / "marco-s-taco-cart"),
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "push to github",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_target_path": "generated-sites/marco-s-taco-cart/index.html"
                    }
                }
            ]
        },
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    payload = json.loads(str(forwarded["target"]))
    assert payload["project_name"] == "marco-s-taco-cart"
    assert payload["github_repo_name"] == "marco-s-taco-cart"
    assert payload["write_project_files"] is False
    assert payload["push"] is True


def test_create_new_repo_named_routes_to_github_repo_creation_intent(
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
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "sandbox" / "marco-s-taco-cart"),
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "create a new repo named GitHub poop project",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "marco-s-taco-cart"
                        )
                    }
                }
            ]
        },
        operator_mode_enabled=False,
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    payload = json.loads(str(forwarded["target"]))
    assert payload["create_github_repo"] is True
    assert payload["push"] is False
    assert payload["github_repo_name"] == "github-poop-project"
    assert payload["write_project_files"] is False


def test_push_to_github_new_repo_carries_requested_repo_name(
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
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "sandbox" / "marco-s-taco-cart"),
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "push to github new repo X push proof",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_project_path": str(
                            tmp_path / "sandbox" / "marco-s-taco-cart"
                        )
                    }
                }
            ]
        },
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    payload = json.loads(str(forwarded["target"]))
    assert payload["create_github_repo"] is True
    assert payload["push"] is True
    assert payload["github_repo_name"] == "x-push-proof"
    assert payload["write_project_files"] is False


def test_missing_remote_suggests_active_exported_slug_repo_name(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def _run_action(
        action_name: str,
        *,
        action_id: str,
        repo_root: Path,
        target: str | None = None,
    ) -> OperatorActionResult:
        payload = json.loads(str(target or "{}"))
        return _result(
            action_name=action_name,
            action_id=action_id,
            repo_root=repo_root,
            status="failed",
            stderr="origin remote is not configured",
            mutates_files=True,
            data={
                "missing_remote": True,
                "suggested_repo_name": payload.get("github_repo_name", ""),
                "repo_before": {
                    "branch": "main",
                    "remotes": [],
                    "status_lines": ["## main"],
                },
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "push to github",
        session_metadata={
            "artifact_history": [
                {
                    "artifact": {
                        "sandbox_target_path": "generated-sites/marco-s-taco-cart/index.html"
                    }
                }
            ]
        },
    )

    assert handled is not None
    assert "create a new github repo named marco-s-taco-cart" in handled.answer.lower()


def test_push_to_github_uses_active_export_metadata_without_explicit_path_prompt(
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
            mutates_files=True,
            data={
                "project_path": str(tmp_path / "sandbox" / "tony-s-taco-tavern"),
                "pushed": False,
            },
        )

    monkeypatch.setattr("core.operator.manager.run_action", _run_action)

    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "push to github",
        session_metadata={
            "active_exported_artifact": {
                "project_slug": "tony-s-taco-tavern",
                "relative_project_path": "generated-sites/tony-s-taco-tavern",
                "container_project_path": "/app/generated-sites/tony-s-taco-tavern",
                "host_project_path": "X:\\xoduz-sandbox\\tony-s-taco-tavern",
                "file_count": 10,
                "entry_file": "index.html",
            }
        },
    )

    assert handled is not None
    assert forwarded["action_name"] == "operator_github_proof_project"
    payload = json.loads(str(forwarded["target"]))
    assert payload["project_name"] == "tony-s-taco-tavern"
    assert payload["github_repo_name"] == "tony-s-taco-tavern"
    assert payload["sandbox_project_path"].endswith("tony-s-taco-tavern")
    assert "need one confirmation" not in handled.answer.lower()


def test_missing_path_confirmation_message_is_dynamic_not_stale_example(
    tmp_path: Path,
) -> None:
    handled = OperatorManager(repo_root=tmp_path).try_handle_chat(
        "push to github",
        session_metadata={
            "artifact_history": [],
        },
    )

    assert handled is not None
    assert handled.result.status == "pending"
    assert "earthx-github-proof" not in handled.answer.lower()
