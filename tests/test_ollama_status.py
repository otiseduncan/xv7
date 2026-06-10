from __future__ import annotations

import asyncio

import httpx
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from core.main import app
from core.runtime.ollama_status import fetch_ollama_status


def test_fetch_ollama_status_reports_available_models() -> None:
    async def run_probe() -> dict:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/tags"
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "llama3:latest"},
                        {"model": "nomic-embed-text:latest"},
                    ]
                },
            )

        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_ollama_status(
                client=client,
                base_url="http://ollama:11434",
                chat_model="llama3",
                embedding_model="nomic-embed-text",
            )

    status = asyncio.run(run_probe())

    assert status["reachable"] is True
    assert status["base_url"] == "http://ollama:11434"
    assert status["models"] == ["llama3:latest", "nomic-embed-text:latest"]
    assert status["chat_model_available"] is True
    assert status["embedding_model_available"] is True
    assert status["error"] is None


def test_fetch_ollama_status_reports_connection_failure() -> None:
    async def run_probe() -> dict:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_ollama_status(
                client=client,
                base_url="http://ollama:11434",
                chat_model="llama3",
                embedding_model="nomic-embed-text",
            )

    status = asyncio.run(run_probe())

    assert status["reachable"] is False
    assert status["models"] == []
    assert status["chat_model_available"] is False
    assert status["embedding_model_available"] is False
    assert status["error"]["type"] == "ConnectError"


def test_runtime_ollama_endpoint_returns_probe_result(monkeypatch: MonkeyPatch) -> None:
    async def fake_fetch_ollama_status() -> dict:
        return {
            "reachable": True,
            "base_url": "http://ollama:11434",
            "chat_model": "llama3",
            "embedding_model": "nomic-embed-text",
            "models": ["llama3:latest", "nomic-embed-text:latest"],
            "chat_model_available": True,
            "embedding_model_available": True,
            "error": None,
        }

    monkeypatch.setattr(
        "core.main.fetch_ollama_status",
        fake_fetch_ollama_status,
    )

    client = TestClient(app)

    response = client.get("/runtime/ollama")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reachable"] is True
    assert payload["chat_model_available"] is True
    assert payload["embedding_model_available"] is True
