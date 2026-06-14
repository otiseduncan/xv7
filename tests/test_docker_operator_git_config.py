from __future__ import annotations

from pathlib import Path


def test_core_container_declares_operator_git_config() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "XV7_OPERATOR_REPO_ROOT=/workspace" in compose
    assert "XV7_OPERATOR_FAST_GIT_STATUS=1" in compose
    assert "GIT_CONFIG_COUNT=3" in compose
    assert "GIT_CONFIG_KEY_0=safe.directory" in compose
    assert "GIT_CONFIG_VALUE_0=/workspace" in compose
    assert "GIT_CONFIG_KEY_1=core.autocrlf" in compose
    assert "GIT_CONFIG_VALUE_1=true" in compose
    assert "GIT_CONFIG_KEY_2=core.filemode" in compose
    assert "GIT_CONFIG_VALUE_2=false" in compose
