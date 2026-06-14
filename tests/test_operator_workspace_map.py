from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from core.operator.actions.workspace import workspace_map
from core.operator.registry import run_action


class _Proc:
    def __init__(self, code: int, out: str = "", err: str = "") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = err


def _make_workspace(root: Path) -> None:
    (root / "core").mkdir()
    (root / "core" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    (root / "public").mkdir()
    (root / "public" / "index.html").write_text("<div></div>", encoding="utf-8")
    (root / "public" / "app.js").write_text("console.log('xv7')", encoding="utf-8")
    (root / "public" / "app.test.js").write_text(
        "test('ok', () => {})",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "XODUZ_ROADMAP.md").write_text(
        "# Roadmap\n",
        encoding="utf-8",
    )
    (root / "docs" / "CODE_LANE_INDEX.md").write_text("# CODE\n", encoding="utf-8")
    (root / "README.md").write_text("# XV7\n", encoding="utf-8")
    (root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (root / "package.json").write_text('{"scripts": {}}\n', encoding="utf-8")


def test_workspace_map_returns_repo_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _make_workspace(tmp_path)

    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _Proc(0, "main\n")  # type: ignore[return-value]
        if args == ["status", "--porcelain"]:
            return _Proc(0, " M core/main.py\n?? docs/new.md\n")  # type: ignore[return-value]
        return _Proc(1, "", "unexpected git command")  # type: ignore[return-value]

    monkeypatch.setattr("core.operator.actions.workspace._run_git", _fake_run_git)

    result = workspace_map(action_id="OP-20260611-0201", repo_root=tmp_path)

    assert result.status == "success"
    assert result.safety.allowed is True
    assert result.safety.read_only is True
    assert result.safety.mutates_files is False
    assert result.safety.mutates_git is False
    assert result.safety.mutates_runtime is False
    assert result.data["repo_root"] == str(tmp_path.resolve())
    assert result.data["branch"] == "main"
    assert result.data["dirty_file_count"] == 2
    assert result.data["dirty_files"] == ["core/main.py", "docs/new.md"]
    assert "core" in result.data["top_level_folders"]
    assert "docs" in result.data["top_level_folders"]
    assert result.data["detected_stack"]["python"] is True
    assert result.data["detected_stack"]["fastapi"] is True
    assert result.data["detected_stack"]["frontend_static"] is True
    assert result.data["detected_stack"]["docker"] is True
    assert (
        "python -m pytest tests/ -v --tb=short --asyncio-mode=auto"
        in result.data["test_commands"]
    )
    assert "docs/CODE_LANE_INDEX.md" in result.data["present_key_files"]


def test_workspace_map_is_available_through_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _make_workspace(tmp_path)

    def _fake_run_git(_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if "rev-parse" in args:
            return _Proc(0, "main\n")  # type: ignore[return-value]
        return _Proc(0, "")  # type: ignore[return-value]

    monkeypatch.setattr("core.operator.actions.workspace._run_git", _fake_run_git)

    result = run_action(
        "workspace_map",
        action_id="OP-20260611-0202",
        repo_root=tmp_path,
    )

    assert result.status == "success"
    assert result.action_name == "workspace_map"
    assert "workspace_map" in result.receipt_label


def test_workspace_map_reports_invalid_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"

    result = workspace_map(action_id="OP-20260611-0203", repo_root=missing_root)

    assert result.status == "failed"
    assert result.safety.allowed is True
    assert result.safety.read_only is True
    assert "does not exist" in result.stderr_summary
