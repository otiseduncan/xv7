from __future__ import annotations

from pathlib import Path

import pytest

from core.runtime.model_registry import (
    load_registry_config,
    resolve_active_models,
    resolve_model_for_runtime_role,
)


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


def test_resolve_model_for_runtime_role_balanced_chat() -> None:
    result = resolve_model_for_runtime_role("chat", profile="balanced")

    assert result.profile == "balanced"
    assert result.canonical_role == "chat"
    assert result.model_tag == "qwen3:8b"


def test_resolve_model_for_runtime_role_local_test_chat() -> None:
    result = resolve_model_for_runtime_role("chat", profile="local_test")

    assert result.profile == "local_test"
    assert result.canonical_role == "chat"
    assert result.model_tag == "qwen3:14b"


def test_resolve_model_for_runtime_role_large_code_code() -> None:
    result = resolve_model_for_runtime_role("code", profile="large_code")

    assert result.profile == "large_code"
    assert result.canonical_role == "code"
    assert result.model_tag == "qwen3-coder:30b"


def test_resolve_model_for_runtime_role_aliases_map_to_canonical() -> None:
    chat = resolve_model_for_runtime_role("default", profile="balanced")
    assistant = resolve_model_for_runtime_role("assistant", profile="balanced")
    embedding = resolve_model_for_runtime_role("model_embed", profile="balanced")

    assert chat.canonical_role == "chat"
    assert assistant.canonical_role == "chat"
    assert embedding.canonical_role == "embedding"


def test_resolve_model_for_runtime_role_unknown_role_fails_clearly() -> None:
    with pytest.raises(ValueError, match="Unknown runtime role alias"):
        resolve_model_for_runtime_role("unknown_role", profile="balanced")


def test_legacy_model_env_keys_do_not_override_registry_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_DEFAULT", "llama3")
    monkeypatch.setenv("MODEL_CODE", "qwen2.5-coder:14b")
    monkeypatch.setenv("MODEL_REASONING", "deepseek-r1:8b")
    monkeypatch.setenv("MODEL_EMBED", "nomic-embed-text")
    monkeypatch.setenv("XV7_MODEL_PROFILE", "balanced")

    result = resolve_model_for_runtime_role("chat")

    assert result.model_tag == "qwen3:8b"
