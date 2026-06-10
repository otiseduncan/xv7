"""Tests for scripts/check_ollama_models.py helper logic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "check_ollama_models.py"
    spec = importlib.util.spec_from_file_location("check_ollama_models", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load check_ollama_models module")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_ollama_tags_payload_handles_multiple_models() -> None:
    mod = _load_module()

    payload = {
        "models": [
            {"name": "qwen2.5-coder:14b"},
            {"model": "nomic-embed-text:latest"},
            {"name": "qwen3-coder:30b"},
        ]
    }

    models = mod.parse_ollama_tags_payload(payload)

    assert models == [
        "nomic-embed-text:latest",
        "qwen2.5-coder:14b",
        "qwen3-coder:30b",
    ]


def test_active_chat_model_prefers_env_over_dotenv_and_defaults() -> None:
    mod = _load_module()

    value = mod.resolve_setting(
        "MODEL_DEFAULT",
        env={"MODEL_DEFAULT": "qwen2.5-coder:14b"},
        dotenv={"MODEL_DEFAULT": "llama3"},
        defaults={"MODEL_DEFAULT": "llama3.2"},
    )

    assert value == "qwen2.5-coder:14b"


def test_14b_style_model_name_treated_as_normal() -> None:
    mod = _load_module()

    assert mod.model_matches("qwen2.5-coder:14b", "qwen2.5-coder:14b") is True
    assert mod.has_model("qwen2.5-coder:14b", ["qwen2.5-coder:14b"]) is True


def test_missing_selected_chat_model_fails_required_check() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        active_chat_model="qwen2.5-coder:14b",
        embedding_model="nomic-embed-text",
        reasoning_model=None,
        code_model=None,
        installed_models=["nomic-embed-text:latest"],
    )

    chat = next(c for c in checks if c.role == "chat")
    assert chat.inventory_status == mod.STATUS_MISSING
    assert mod.compute_exit_code(checks) == 1


def test_installed_selected_chat_model_passes() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        active_chat_model="qwen2.5-coder:14b",
        embedding_model="nomic-embed-text",
        reasoning_model=None,
        code_model=None,
        installed_models=["qwen2.5-coder:14b", "nomic-embed-text:latest"],
    )

    chat = next(c for c in checks if c.role == "chat")
    assert chat.inventory_status == mod.STATUS_INSTALLED
    assert mod.compute_exit_code(checks) == 0


def test_embedding_checked_separately_from_chat() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        active_chat_model="qwen2.5-coder:14b",
        embedding_model="nomic-embed-text",
        reasoning_model=None,
        code_model=None,
        installed_models=["qwen2.5-coder:14b"],
    )

    chat = next(c for c in checks if c.role == "chat")
    embedding = next(c for c in checks if c.role == "embedding")

    assert chat.inventory_status == mod.STATUS_INSTALLED
    assert embedding.inventory_status == mod.STATUS_MISSING
    assert mod.compute_exit_code(checks) == 1


def test_no_secret_values_are_printed_in_summary_context() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        active_chat_model="qwen2.5-coder:14b",
        embedding_model="nomic-embed-text",
        reasoning_model="deepseek-r1:8b",
        code_model="qwen2.5-coder:7b",
        installed_models=["qwen2.5-coder:14b", "nomic-embed-text:latest"],
    )

    text = "\n".join(
        f"{c.role}|{c.model}|{c.config_status}|{c.inventory_status}" for c in checks
    )

    assert "CORE_API_KEY" not in text
    assert "XV7_API_KEY" not in text
