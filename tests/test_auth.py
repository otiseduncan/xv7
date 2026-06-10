from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from core.runtime.auth import require_api_key


def _client() -> TestClient:
    app = FastAPI()

    @app.post("/protected", dependencies=[Depends(require_api_key)])
    async def protected() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/public")
    async def public() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_api_key_not_required_when_unconfigured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("XV7_API_KEY", raising=False)
    client = _client()

    response = client.post("/protected")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_key_allows_xv7_header(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("XV7_API_KEY", "secret-key")
    client = _client()

    response = client.post(
        "/protected",
        headers={"X-XV7-API-Key": "secret-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_key_allows_bearer_token(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("XV7_API_KEY", "secret-key")
    client = _client()

    response = client.post(
        "/protected",
        headers={"Authorization": "Bearer secret-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_key_rejects_missing_key_when_configured(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("XV7_API_KEY", "secret-key")
    client = _client()

    response = client.post("/protected")

    assert response.status_code == 401
    assert response.json() == {"detail": "XV7 API key required"}


def test_public_route_does_not_require_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("XV7_API_KEY", "secret-key")
    client = _client()

    response = client.get("/public")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
