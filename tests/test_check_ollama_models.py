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
            {"name": "qwen3:1.7b"},
            {"name": "qwen3:8b"},
            {"name": "qwen3:14b"},
            {"name": "qwen3-coder:30b"},
            {"model": "nomic-embed-text:latest"},
        ]
    }

    models = mod.parse_ollama_tags_payload(payload)

    assert models == [
        "nomic-embed-text:latest",
        "qwen3-coder:30b",
        "qwen3:1.7b",
        "qwen3:14b",
        "qwen3:8b",
    ]


def test_14b_style_model_name_treated_as_normal() -> None:
    mod = _load_module()

    assert mod.model_matches("qwen3:14b", "qwen3:14b") is True
    assert mod.has_model("qwen3:14b", ["qwen3:14b"]) is True


def test_missing_selected_chat_model_fails_required_check() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
        installed_models=["nomic-embed-text:latest", "qwen3-coder:30b"],
    )
    alias_checks = mod.build_alias_checks(
        role_aliases={"default": "chat", "model_embed": "embedding"},
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
    )

    chat = next(c for c in checks if c.role == "chat")
    assert chat.inventory_status == mod.STATUS_MISSING
    assert mod.compute_exit_code(checks, alias_checks) == 1


def test_installed_selected_chat_model_passes() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
        installed_models=[
            "qwen3:14b",
            "nomic-embed-text:latest",
            "qwen3-coder:30b",
        ],
    )
    alias_checks = mod.build_alias_checks(
        role_aliases={"default": "chat", "model_embed": "embedding"},
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
    )

    chat = next(c for c in checks if c.role == "chat")
    assert chat.inventory_status == mod.STATUS_INSTALLED
    assert mod.compute_exit_code(checks, alias_checks) == 0


def test_embedding_checked_separately_from_chat() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
        installed_models=["qwen3:14b", "qwen3-coder:30b"],
    )
    alias_checks = mod.build_alias_checks(
        role_aliases={"default": "chat", "model_embed": "embedding"},
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
    )

    chat = next(c for c in checks if c.role == "chat")
    embedding = next(c for c in checks if c.role == "embedding")

    assert chat.inventory_status == mod.STATUS_INSTALLED
    assert embedding.inventory_status == mod.STATUS_MISSING
    assert mod.compute_exit_code(checks, alias_checks) == 1


def test_alias_check_fails_on_unknown_canonical_role() -> None:
    mod = _load_module()

    alias_checks = mod.build_alias_checks(
        role_aliases={"foo": "unknown_role"},
        roles={"chat": "qwen3:14b", "embedding": "nomic-embed-text:latest"},
    )

    assert alias_checks[0].status == mod.STATUS_FAILED


def test_no_secret_values_are_printed_in_summary_context() -> None:
    mod = _load_module()

    checks = mod.build_role_checks(
        roles={
            "chat": "qwen3:14b",
            "embedding": "nomic-embed-text:latest",
            "reasoning": "qwen3:14b",
            "code": "qwen3-coder:30b",
        },
        installed_models=["qwen3:14b", "nomic-embed-text:latest"],
    )

    text = "\n".join(
        f"{c.role}|{c.model}|{c.config_status}|{c.inventory_status}" for c in checks
    )

    assert "CORE_API_KEY" not in text
    assert "XV7_API_KEY" not in text


def test_ollama_endpoint_mode_labels_host_shell_and_docker_urls() -> None:
    mod = _load_module()

    assert mod.ollama_endpoint_mode("http://localhost:11434") == "host_shell"
    assert mod.ollama_endpoint_mode("http://127.0.0.1:11434") == "host_shell"
    assert mod.ollama_endpoint_mode("http://ollama:11434") == "docker_internal"
    assert mod.ollama_endpoint_mode("http://example.test:11434") == "custom"
