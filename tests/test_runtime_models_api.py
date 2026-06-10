from __future__ import annotations

import asyncio

import httpx
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from core.main import app
from core.runtime.models_api import (
    build_effective_runtime_models,
    build_runtime_model_profiles,
    fetch_runtime_models,
)


def test_build_runtime_model_profiles_resolves_env_profile(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_MODEL_PROFILE", "local_test")

    payload = build_runtime_model_profiles()

    assert "local_test" in payload["available_profiles"]
    assert payload["active_profile"] == "local_test"
    assert payload["profile_source"] == "env"
    assert payload["resolved_models"]["chat"] == "qwen3:14b"


def test_runtime_models_endpoint_returns_profiles_and_inventory_shape(
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_fetch_ollama_status(**_kwargs: object) -> dict[str, object]:
        return {
            "reachable": True,
            "base_url": "http://ollama:11434",
            "models": ["qwen3:8b", "nomic-embed-text:latest"],
            "error": None,
            "role_model_availability": {
                "chat": True,
                "reasoning": False,
                "code": False,
                "embedding": True,
            },
        }

    monkeypatch.setattr(
        "core.runtime.models_api.fetch_ollama_status",
        fake_fetch_ollama_status,
    )

    client = TestClient(app)
    response = client.get("/runtime/models")

    assert response.status_code == 200
    payload = response.json()
    assert "available_profiles" in payload
    assert "profiles" in payload
    assert "active_profile" in payload
    assert "profile_source" in payload
    assert "role_aliases" in payload
    assert "resolved_models" in payload
    assert payload["availability"]["chat"] is True
    assert payload["availability"]["embedding"] is True


def test_runtime_models_active_endpoint_supports_profile_override(
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_fetch_ollama_status(**_kwargs: object) -> dict[str, object]:
        return {
            "reachable": True,
            "base_url": "http://ollama:11434",
            "models": ["qwen3:14b", "qwen3-coder:30b", "nomic-embed-text:latest"],
            "error": None,
            "role_model_availability": {
                "chat": True,
                "reasoning": True,
                "code": True,
                "embedding": True,
            },
        }

    monkeypatch.setattr(
        "core.runtime.models_api.fetch_ollama_status",
        fake_fetch_ollama_status,
    )

    client = TestClient(app)
    response = client.get("/runtime/models/active?profile=local_test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_profile"] == "local_test"
    assert payload["profile_source"] == "override"
    assert payload["resolved_models"]["code"] == "qwen3-coder:30b"


def test_runtime_models_endpoint_does_not_return_api_key_values(
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_fetch_ollama_status(**_kwargs: object) -> dict[str, object]:
        return {
            "reachable": False,
            "base_url": "http://ollama:11434",
            "models": [],
            "error": {"type": "ConnectError", "message": "connection refused"},
            "role_model_availability": {
                "chat": False,
                "reasoning": False,
                "code": False,
                "embedding": False,
            },
        }

    monkeypatch.setenv("XV7_API_KEY", "super-secret-key")
    monkeypatch.setenv("CORE_API_KEY", "also-secret")
    monkeypatch.setattr(
        "core.runtime.models_api.fetch_ollama_status",
        fake_fetch_ollama_status,
    )

    client = TestClient(app)
    response = client.get("/runtime/models")

    assert response.status_code == 200
    payload_text = str(response.json())
    assert "super-secret-key" not in payload_text
    assert "also-secret" not in payload_text


def test_fetch_runtime_models_reports_unreachable_ollama_honestly(
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_fetch_ollama_status(**_kwargs: object) -> dict[str, object]:
        return {
            "reachable": False,
            "base_url": "http://ollama:11434",
            "models": [],
            "error": {"type": "ConnectError", "message": "connect failed"},
            "role_model_availability": {
                "chat": False,
                "reasoning": False,
                "code": False,
                "embedding": False,
            },
        }

    monkeypatch.setattr(
        "core.runtime.models_api.fetch_ollama_status",
        fake_fetch_ollama_status,
    )

    payload = asyncio.run(fetch_runtime_models())

    assert payload["ollama"]["reachable"] is False
    assert payload["ollama"]["models"] == []
    assert payload["availability"]["chat"] is False
    assert payload["availability"]["reasoning"] is False
    assert payload["availability"]["code"] is False
    assert payload["availability"]["embedding"] is False


def test_fetch_runtime_models_with_mock_transport_reports_inventory() -> None:
    async def run_probe() -> dict[str, object]:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/tags"
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen3:8b"},
                        {"name": "qwen3:14b"},
                        {"name": "qwen3-coder:30b"},
                        {"name": "nomic-embed-text:latest"},
                    ]
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_runtime_models(client=client)

    payload = asyncio.run(run_probe())

    assert payload["ollama"]["reachable"] is True
    assert "qwen3:8b" in payload["ollama"]["models"]
    assert "availability" in payload


def test_build_effective_runtime_models_reports_expected_tags() -> None:
    payload = build_effective_runtime_models(profile_override="balanced")

    assert payload["active_profile"] == "balanced"
    assert payload["effective_models"]["chat"] == "qwen3:8b"
    assert payload["effective_models"]["reasoning"] == "qwen3:14b"
    assert payload["effective_models"]["code"] == "qwen3:14b"
    assert payload["effective_models"]["embedding"] == "nomic-embed-text:latest"


def test_runtime_models_effective_endpoint_is_public_and_returns_payload() -> None:
    client = TestClient(app)

    response = client.get("/runtime/models/effective")

    assert response.status_code == 200
    payload = response.json()
    assert "effective_models" in payload
    assert "chat" in payload["effective_models"]
    assert "reasoning" in payload["effective_models"]
    assert "code" in payload["effective_models"]
    assert "embedding" in payload["effective_models"]


def test_runtime_models_effective_endpoint_does_not_return_secret_values(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "very-secret")
    monkeypatch.setenv("CORE_API_KEY", "also-very-secret")

    client = TestClient(app)
    response = client.get("/runtime/models/effective")

    assert response.status_code == 200
    payload_text = str(response.json())
    assert "very-secret" not in payload_text
    assert "also-very-secret" not in payload_text


def test_runtime_models_effective_uses_runtime_override_when_set(
    monkeypatch: MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    from core.runtime.model_profile_selection import set_runtime_profile_override

    set_runtime_profile_override(
        "large_code",
        {"low_resource", "balanced", "local_test", "large_code"},
    )

    payload = build_effective_runtime_models()

    assert payload["active_profile"] == "large_code"
    assert payload["profile_source"] == "runtime_override"
    assert payload["effective_models"]["chat"] == "qwen3-coder:30b"


def test_runtime_models_active_put_rejects_unknown_profile(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    client = TestClient(app)

    response = client.put(
        "/runtime/models/active",
        json={"profile": "unknown_profile", "require_available": False},
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert response.status_code == 400
    assert "Unknown profile" in response.json()["detail"]


def test_runtime_models_active_put_can_skip_availability_gate(
    monkeypatch: MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    async def fake_fetch_runtime_models(**_kwargs: object) -> dict[str, object]:
        return {
            "active_profile": "local_test",
            "profile_source": "runtime_override",
            "resolved_models": {
                "chat": "qwen3:14b",
                "reasoning": "qwen3:14b",
                "code": "qwen3-coder:30b",
                "embedding": "nomic-embed-text:latest",
            },
            "role_aliases": {"default": "chat"},
            "availability": {
                "chat": False,
                "reasoning": False,
                "code": False,
                "embedding": False,
            },
            "ollama": {
                "reachable": False,
                "base_url": "http://ollama:11434",
                "models": [],
                "error": {"type": "ConnectError", "message": "connect failed"},
            },
            "config_error": None,
        }

    monkeypatch.setattr("core.main.fetch_runtime_models", fake_fetch_runtime_models)

    client = TestClient(app)
    response = client.put(
        "/runtime/models/active",
        json={"profile": "local_test", "require_available": False},
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_profile"] == "local_test"
    assert payload["profile_source"] == "runtime_override"
    assert payload["availability"]["chat"] is False
    assert payload["ollama"]["reachable"] is False


def test_runtime_models_active_put_enforces_availability_gate(
    monkeypatch: MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    async def fake_fetch_runtime_models(**_kwargs: object) -> dict[str, object]:
        return {
            "active_profile": "local_test",
            "profile_source": "runtime_override",
            "resolved_models": {
                "chat": "qwen3:14b",
                "reasoning": "qwen3:14b",
                "code": "qwen3-coder:30b",
                "embedding": "nomic-embed-text:latest",
            },
            "role_aliases": {"default": "chat"},
            "availability": {
                "chat": False,
                "reasoning": False,
                "code": False,
                "embedding": False,
            },
            "ollama": {
                "reachable": False,
                "base_url": "http://ollama:11434",
                "models": [],
                "error": {"type": "ConnectError", "message": "connect failed"},
            },
            "config_error": None,
        }

    monkeypatch.setattr("core.main.fetch_runtime_models", fake_fetch_runtime_models)

    client = TestClient(app)
    response = client.put(
        "/runtime/models/active",
        json={"profile": "local_test", "require_available": True},
        headers={"X-XV7-API-Key": "test-secret"},
    )

    assert response.status_code == 400
    assert "Ollama is unreachable" in response.json()["detail"]
