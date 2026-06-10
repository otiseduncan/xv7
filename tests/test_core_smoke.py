from fastapi.testclient import TestClient

from core.main import app, build_facts_system_prompt


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_facts_prompt_has_clear_boundary() -> None:
    prompt = build_facts_system_prompt({"assistant": "Xoduz", "runtime": "XV7"})

    assert "PERSISTENT SESSION MEMORY" in prompt
    assert "Xoduz" in prompt
    assert "XV7" in prompt
