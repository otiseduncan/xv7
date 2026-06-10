"""Tests for scripts/smoke_xv7_local.py helper logic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_smoke_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "smoke_xv7_local.py"
    spec = importlib.util.spec_from_file_location("smoke_xv7_local", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load smoke_xv7_local module")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_redact_secret_masks_value() -> None:
    smoke = _load_smoke_module()

    assert smoke.redact_secret("super-secret") == "<redacted>"
    assert smoke.redact_secret(None) == "<not_set>"


def test_safe_header_preview_redacts_api_key() -> None:
    smoke = _load_smoke_module()
    headers = {
        "X-XV7-API-Key": "super-secret-key",
        "Content-Type": "application/json",
    }

    preview = smoke.safe_header_preview(headers)

    assert preview["X-XV7-API-Key"] == "<redacted>"
    assert preview["Content-Type"] == "application/json"
    assert "super-secret-key" not in str(preview)


def test_build_auth_headers_constructs_expected_header() -> None:
    smoke = _load_smoke_module()

    headers = smoke.build_auth_headers("abc123")

    assert headers == {"X-XV7-API-Key": "abc123"}


def test_compute_exit_code_passes_when_required_checks_pass() -> None:
    smoke = _load_smoke_module()

    checks = [
        smoke.SmokeCheck(
            name="required-pass",
            required=True,
            passed=True,
            configured=smoke.STATUS_NOT_CHECKED,
            reachable=smoke.STATUS_REACHABLE,
            healthy=smoke.STATUS_HEALTHY,
            verified=smoke.STATUS_VERIFIED,
            detail="ok",
        ),
        smoke.SmokeCheck(
            name="optional-fail",
            required=False,
            passed=False,
            configured=smoke.STATUS_NOT_CHECKED,
            reachable=smoke.STATUS_FAILED,
            healthy=smoke.STATUS_FAILED,
            verified=smoke.STATUS_FAILED,
            detail="ignored",
        ),
    ]

    assert smoke.compute_exit_code(checks) == 0


def test_compute_exit_code_fails_when_required_check_fails() -> None:
    smoke = _load_smoke_module()

    checks = [
        smoke.SmokeCheck(
            name="required-fail",
            required=True,
            passed=False,
            configured=smoke.STATUS_FAILED,
            reachable=smoke.STATUS_FAILED,
            healthy=smoke.STATUS_FAILED,
            verified=smoke.STATUS_FAILED,
            detail="failed",
        )
    ]

    assert smoke.compute_exit_code(checks) == 1


def test_auth_detail_preview_does_not_expose_secret() -> None:
    smoke = _load_smoke_module()
    headers = smoke.build_auth_headers("top-secret-value")
    detail = f"with auth header {smoke.safe_header_preview(headers)}"

    assert "top-secret-value" not in detail
    assert "<redacted>" in detail
