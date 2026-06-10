from __future__ import annotations

from pathlib import Path

from core.runtime.model_registry import load_registry_config, resolve_active_models


def test_resolve_active_models_uses_profile_override(monkeypatch) -> None:
    monkeypatch.delenv("XV7_MODEL_PROFILE", raising=False)

    result = resolve_active_models(profile_override="local_test")

    assert result.profile == "local_test"
    assert result.profile_source == "override"
    assert result.roles["chat"] == "qwen3:14b"
    assert result.roles["embedding"] == "nomic-embed-text:latest"
    assert result.error is None


def test_resolve_active_models_uses_env_profile(monkeypatch) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "large_code")

    result = resolve_active_models()

    assert result.profile == "large_code"
    assert result.profile_source == "env"
    assert result.roles["chat"] == "qwen3-coder:30b"
    assert result.roles["code"] == "qwen3-coder:30b"
    assert result.error is None


def test_resolve_active_models_includes_alias_mapping() -> None:
    result = resolve_active_models(profile_override="balanced")

    assert result.role_aliases["default"] == "chat"
    assert result.role_aliases["model_embed"] == "embedding"
    assert result.role_aliases["model_reasoning"] == "reasoning"


def test_resolve_active_models_fails_when_required_roles_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = tmp_path / "models.yml"
    config.write_text(
        """
registry:
  active_profile: broken
  profiles:
    broken:
      reasoning: qwen3:14b
      code: qwen3-coder:30b
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("XV7_MODELS_CONFIG_PATH", str(config))
    monkeypatch.delenv("XV7_MODEL_PROFILE", raising=False)

    result = resolve_active_models()

    assert result.profile == "broken"
    assert result.roles["chat"] is None
    assert result.roles["embedding"] is None
    assert result.error is not None
    assert "missing required roles" in result.error


def test_load_registry_config_keeps_legacy_unused_values(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = tmp_path / "models.yml"
    config.write_text(
        """
registry:
  legacy:
    unused:
      - qwen2.5-coder:14b
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("XV7_MODELS_CONFIG_PATH", str(config))

    loaded = load_registry_config()

    unused = loaded.registry["legacy"]["unused"]
    assert "qwen2.5-coder:14b" in unused
