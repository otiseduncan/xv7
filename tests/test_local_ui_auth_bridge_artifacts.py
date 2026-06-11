from __future__ import annotations

from pathlib import Path


def test_nginx_proxy_template_exists() -> None:
    template = Path("docker/frontend/default.conf.template")
    assert template.exists()


def test_frontend_nginx_template_injects_auth_header_server_side() -> None:
    template_text = Path("docker/frontend/default.conf.template").read_text(
        encoding="utf-8"
    )
    assert "location ^~ /api/" in template_text
    assert "proxy_set_header X-XV7-API-Key ${XV7_API_KEY};" in template_text


def test_frontend_compose_service_receives_key_as_container_env() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "xv7-frontend:" in compose_text
    assert "XV7_API_KEY=${CORE_API_KEY:?CORE_API_KEY must be set}" in compose_text


def test_no_hardcoded_secret_values_in_proxy_config() -> None:
    template_text = Path("docker/frontend/default.conf.template").read_text(
        encoding="utf-8"
    )
    # Ensure config references env substitution rather than embedding literal key values.
    assert "test-secret" not in template_text
    assert "super-secret" not in template_text
    assert "changeme" not in template_text.lower()
