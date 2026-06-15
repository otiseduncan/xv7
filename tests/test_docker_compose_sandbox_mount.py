from __future__ import annotations

from pathlib import Path


def test_core_service_mounts_generated_sites_from_env_configurable_host_path() -> None:
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "${XV7_HOST_SANDBOX:-./generated-sites}:/app/generated-sites" in compose_text


def test_env_example_documents_optional_host_sandbox_export_path() -> None:
    env_example_path = Path(__file__).resolve().parents[1] / ".env.example"
    env_text = env_example_path.read_text(encoding="utf-8")

    assert "XV7_HOST_SANDBOX=./generated-sites" in env_text
    assert "XV7_HOST_SANDBOX=X:/xoduz-sandbox" in env_text
