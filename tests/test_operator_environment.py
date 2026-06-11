from __future__ import annotations

from pathlib import Path

import pytest

from core.operator.actions.environment import operator_environment


def test_operator_environment_reports_read_only_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XV7_PERSISTENT_MEMORY_PATH", "data/memory/records")
    monkeypatch.setattr(
        "core.operator.actions.environment.shutil.which",
        lambda name: "/usr/bin/tool" if name == "git" else None,
    )

    result = operator_environment(action_id="OP-20260611-0201", repo_root=tmp_path)

    assert result.status == "success"
    assert result.safety.read_only is True
    assert result.data["repo_root"] == str(tmp_path)
    assert result.data["git_available"] is True
    assert result.data["docker_cli_available"] is False
    assert "service_url_config" in result.data
    assert result.data["memory_store_path"] == "data/memory/records"
    assert result.data["read_only_mode"] is True
