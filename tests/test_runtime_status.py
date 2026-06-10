from fastapi.testclient import TestClient

from core.main import app
from core.runtime.status import build_runtime_status


def test_runtime_status_defaults_are_truthful() -> None:
    status = build_runtime_status()

    assert status["status"] == "ok"
    assert status["platform"]["name"] == "XV7"
    assert status["platform"]["mode"] == "local-first"
    assert status["platform"]["cloud_fallback_enabled"] is False
    assert status["assistant"]["name"] == "Xoduz"
    assert status["ollama"]["verified"] is False
    assert status["ollama"]["verification"] == "not_checked"
    assert status["capabilities"]["gpu_verified"] is False
    assert status["capabilities"]["microphone_verified"] is False
    assert status["capabilities"]["voice_pipeline_verified"] is False
    assert status["capabilities"]["synthetic_telemetry"] is False


def test_runtime_status_endpoint_returns_configuration() -> None:
    client = TestClient(app)

    response = client.get("/runtime/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["platform"]["name"] == "XV7"
    assert payload["assistant"]["name"] == "Xoduz"
    assert payload["ollama"]["verified"] is False
