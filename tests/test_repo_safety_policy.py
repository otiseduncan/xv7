from __future__ import annotations

from pathlib import Path

import pytest

from core.brain.answer_contract import AnswerContract
from core.brain.repo_safety_policy import RepoSafetyPolicy


VALID_HTML = """<!doctype html>
<html>
<head><style>body { color: black; }</style></head>
<body><h1>Tony's Tavern</h1></body>
</html>
"""


def _checks_by_name(checks: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {check["name"]: check for check in checks}


def _validate(
    root: Path,
    *,
    target_path: str = "generated-sites/tonys-tavern/index.html",
    content: str = VALID_HTML,
    language: str = "html",
    business_name: str = "Tony's Tavern",
    operation: str = "create",
) -> tuple[str, list[dict[str, str]], list[str]]:
    return RepoSafetyPolicy.validate_patch_proposal(
        root=root,
        target_path=target_path,
        content=content,
        language=language,
        business_name=business_name,
        operation=operation,
    )


def test_workspace_root_respects_env_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))

    assert RepoSafetyPolicy.workspace_root() == tmp_path.resolve()


@pytest.mark.parametrize(
    "path_text",
    [
        "generated-sites/demo/.git/config",
        "generated-sites/demo/.env",
        "generated-sites/demo/node_modules/app.js",
        "generated-sites/demo/runtime/logs/output.txt",
        "generated-sites/demo/data/brain/layer.json",
    ],
)
def test_is_blocked_patch_target_blocks_protected_paths(path_text: str) -> None:
    assert RepoSafetyPolicy.is_blocked_patch_target(path_text)


@pytest.mark.parametrize(
    "path_text",
    [
        "data/brain/layer.json",
        "runtime/logs/output.txt",
        ".git/config",
        "node_modules/app.js",
        ".env",
    ],
)
def test_is_blocked_commit_target_blocks_top_level_protected_paths(
    path_text: str,
) -> None:
    assert RepoSafetyPolicy.is_blocked_commit_target(path_text)


def test_validate_patch_proposal_accepts_valid_html_create(tmp_path: Path) -> None:
    status, checks, failures = _validate(tmp_path)

    assert status == "passed"
    assert failures == []
    assert all(check["status"] == "passed" for check in checks)


@pytest.mark.parametrize(
    ("kwargs", "failed_check"),
    [
        ({"operation": "delete"}, "operation_allowed"),
        ({"target_path": "unsafe-sites/tonys-tavern/index.html"}, "target_path_prefix"),
        (
            {"target_path": str(Path("X:/outside/generated-sites/x/index.html"))},
            "target_path_relative",
        ),
        (
            {"target_path": "../generated-sites/x/index.html"},
            "target_path_no_traversal",
        ),
        (
            {"target_path": "generated-sites/tonys-tavern/node_modules/app.js"},
            "target_path_not_blocked",
        ),
        ({"target_path": "generated-sites/tonys-tavern/app.js"}, "target_extension"),
        ({"content": ""}, "content_non_empty"),
        ({"content": f"```html\n{VALID_HTML}\n```"}, "content_no_markdown_fence"),
    ],
)
def test_validate_patch_proposal_rejects_unsafe_inputs(
    tmp_path: Path,
    kwargs: dict[str, str],
    failed_check: str,
) -> None:
    status, checks, failures = _validate(tmp_path, **kwargs)
    check = _checks_by_name(checks)[failed_check]

    assert status == "failed"
    assert check["status"] == "failed"
    assert any(failure.startswith(f"{failed_check}:") for failure in failures)


def test_validate_patch_proposal_rejects_sibling_root_prefix_escape(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "repo-evil").mkdir()

    status, checks, failures = _validate(
        root,
        target_path="../repo-evil/generated-sites/x/index.html",
    )
    inside_repo = _checks_by_name(checks)["target_path_inside_repo"]

    assert status == "failed"
    assert inside_repo == {
        "name": "target_path_inside_repo",
        "status": "failed",
        "detail": "target path must resolve inside repo root",
    }
    assert any(
        failure == "target_path_inside_repo: target path must resolve inside repo root"
        for failure in failures
    )


def test_answer_contract_wrappers_match_repo_safety_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))

    assert AnswerContract._workspace_root() == RepoSafetyPolicy.workspace_root()
    assert AnswerContract._is_blocked_patch_target(
        "generated-sites/demo/node_modules/app.js"
    ) == RepoSafetyPolicy.is_blocked_patch_target(
        "generated-sites/demo/node_modules/app.js"
    )
    assert AnswerContract._is_blocked_commit_target(
        "data/brain/layer.json"
    ) == RepoSafetyPolicy.is_blocked_commit_target("data/brain/layer.json")
    assert AnswerContract._validate_patch_proposal(
        root=tmp_path,
        target_path="generated-sites/tonys-tavern/index.html",
        content=VALID_HTML,
        language="html",
        business_name="Tony's Tavern",
        operation="create",
    ) == RepoSafetyPolicy.validate_patch_proposal(
        root=tmp_path,
        target_path="generated-sites/tonys-tavern/index.html",
        content=VALID_HTML,
        language="html",
        business_name="Tony's Tavern",
        operation="create",
    )
