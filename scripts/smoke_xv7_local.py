#!/usr/bin/env python
"""Post-launch local smoke proof for XV7.

This script validates that the local stack is reachable and behaves honestly.
It verifies endpoint reachability and protected-route auth behavior without
requesting model generation or claiming unchecked capabilities.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


STATUS_CONFIGURED = "configured"
STATUS_REACHABLE = "reachable"
STATUS_HEALTHY = "healthy"
STATUS_VERIFIED = "verified"
STATUS_NOT_CHECKED = "not checked"
STATUS_FAILED = "failed"


@dataclass
class SmokeCheck:
    name: str
    required: bool
    passed: bool
    configured: str
    reachable: str
    healthy: str
    verified: str
    detail: str


def redact_secret(secret: str | None) -> str:
    """Return a redacted marker for logging-safe secret output."""
    if secret is None:
        return "<not_set>"
    return "<redacted>"


def build_auth_headers(api_key: str) -> dict[str, str]:
    """Build request headers for protected-route checks."""
    return {"X-XV7-API-Key": api_key}


def safe_header_preview(headers: dict[str, str]) -> dict[str, str]:
    """Return a logging-safe headers dict with secret values redacted."""
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if "key" in key.lower() or "authorization" in key.lower():
            redacted[key] = redact_secret(value)
        else:
            redacted[key] = value
    return redacted


def compute_exit_code(checks: list[SmokeCheck]) -> int:
    """Return 0 when all required checks pass, else 1."""
    return 0 if all(c.passed for c in checks if c.required) else 1


def _detect_repo_root(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "docker-compose.yml").exists():
            return candidate
    return None


def _load_dotenv_file(dotenv_path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from .env without shell expansion."""
    loaded: dict[str, str] = {}
    if not dotenv_path.exists():
        return loaded

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            loaded[key] = value
    return loaded


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _http_json(
    method: str,
    url: str,
    *,
    timeout_seconds: float = 4.0,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    body_bytes: bytes | None = None
    request_headers = headers.copy() if headers is not None else {}
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = Request(url, method=method, headers=request_headers, data=body_bytes)
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            status = int(resp.status)
            text = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(text) if text else {}
            if not isinstance(payload, dict):
                payload = {"value": payload}
            return status, payload, None
    except HTTPError as exc:
        status = int(exc.code)
        text = exc.read().decode("utf-8", errors="replace")
        payload: dict[str, Any] | None
        try:
            loaded = json.loads(text) if text else {}
            payload = loaded if isinstance(loaded, dict) else {"value": loaded}
        except Exception:
            payload = None
        return status, payload, f"HTTPError: {exc.reason}"
    except URLError as exc:
        return None, None, f"URLError: {exc.reason}"
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"


def _endpoint_check(name: str, url: str) -> SmokeCheck:
    status, payload, error = _http_json("GET", url)
    reachable = status is not None
    passed = status == 200
    detail = f"GET {url}"
    if error is not None:
        detail = f"{detail} -> {error}"
    elif payload is not None:
        detail = f"{detail} -> status {status}"

    return SmokeCheck(
        name=name,
        required=True,
        passed=passed,
        configured=STATUS_NOT_CHECKED,
        reachable=STATUS_REACHABLE if reachable else STATUS_FAILED,
        healthy=STATUS_HEALTHY if passed else STATUS_FAILED,
        verified=STATUS_VERIFIED if passed else STATUS_FAILED,
        detail=detail,
    )


def _check_runtime_ollama(base_url: str) -> SmokeCheck:
    url = f"{base_url}/runtime/ollama"
    status, payload, error = _http_json("GET", url)
    reachable_http = status == 200 and isinstance(payload, dict)
    ollama_reachable = (
        bool(payload.get("reachable")) if isinstance(payload, dict) else False
    )

    passed = reachable_http
    configured = STATUS_CONFIGURED if reachable_http else STATUS_NOT_CHECKED
    reachable = STATUS_REACHABLE if reachable_http else STATUS_FAILED

    # Do not claim healthy unless /runtime/ollama explicitly says reachable.
    healthy = STATUS_HEALTHY if ollama_reachable else STATUS_FAILED
    verified = STATUS_VERIFIED if reachable_http else STATUS_FAILED

    detail = f"GET {url}"
    if error is not None:
        detail = f"{detail} -> {error}"
    elif isinstance(payload, dict):
        detail = (
            f"{detail} -> status {status}, reachable={payload.get('reachable')}, "
            f"chat_model_available={payload.get('chat_model_available')}, "
            f"embedding_model_available={payload.get('embedding_model_available')}"
        )

    return SmokeCheck(
        name="runtime/ollama",
        required=True,
        passed=passed,
        configured=configured,
        reachable=reachable,
        healthy=healthy,
        verified=verified,
        detail=detail,
    )


def _check_auth_behavior(base_url: str, api_key: str | None) -> list[SmokeCheck]:
    protected_url = f"{base_url}/sessions"

    unauth_status, unauth_payload, unauth_error = _http_json(
        "POST",
        protected_url,
        json_body={"current_persona": "default"},
    )

    unauth_is_401 = unauth_status == 401
    unauth_passed = unauth_is_401
    unauth_detail = f"POST {protected_url} without auth header"
    if unauth_error is not None:
        unauth_detail = f"{unauth_detail} -> {unauth_error}"
    else:
        unauth_detail = f"{unauth_detail} -> status {unauth_status}"

    checks: list[SmokeCheck] = [
        SmokeCheck(
            name="auth_without_key",
            required=True,
            passed=unauth_passed,
            configured=STATUS_CONFIGURED if unauth_is_401 else STATUS_FAILED,
            reachable=STATUS_REACHABLE if unauth_status is not None else STATUS_FAILED,
            healthy=STATUS_HEALTHY if unauth_passed else STATUS_FAILED,
            verified=STATUS_VERIFIED if unauth_status is not None else STATUS_FAILED,
            detail=unauth_detail,
        )
    ]

    if not unauth_is_401:
        checks.append(
            SmokeCheck(
                name="auth_with_key",
                required=True,
                passed=False,
                configured=STATUS_FAILED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
                detail=(
                    "Skipped key-auth verification because unauthenticated request "
                    f"did not return 401 (status={unauth_status})."
                ),
            )
        )
        return checks

    if api_key is None:
        checks.append(
            SmokeCheck(
                name="auth_with_key",
                required=True,
                passed=False,
                configured=STATUS_CONFIGURED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
                detail=(
                    "Auth is configured (401 observed) but no local API key value was "
                    "found in XV7_API_KEY/CORE_API_KEY environment or .env."
                ),
            )
        )
        return checks

    headers = build_auth_headers(api_key)
    auth_status, auth_payload, auth_error = _http_json(
        "POST",
        protected_url,
        headers=headers,
        json_body={"current_persona": "default"},
    )

    passed = auth_status is not None and auth_status != 401
    detail = f"POST {protected_url} with auth header {safe_header_preview(headers)}"
    if auth_error is not None:
        detail = f"{detail} -> {auth_error}"
    elif auth_payload is not None:
        detail = f"{detail} -> status {auth_status}"

    checks.append(
        SmokeCheck(
            name="auth_with_key",
            required=True,
            passed=passed,
            configured=STATUS_CONFIGURED,
            reachable=STATUS_REACHABLE if auth_status is not None else STATUS_FAILED,
            healthy=STATUS_HEALTHY if passed else STATUS_FAILED,
            verified=STATUS_VERIFIED if auth_status is not None else STATUS_FAILED,
            detail=detail,
        )
    )
    return checks


def _print_summary(checks: list[SmokeCheck]) -> None:
    headers = [
        "Check",
        "Required",
        "Configured",
        "Reachable",
        "Healthy",
        "Verified",
        "Result",
    ]
    rows: list[list[str]] = []
    for check in checks:
        rows.append(
            [
                check.name,
                "yes" if check.required else "no",
                check.configured,
                check.reachable,
                check.healthy,
                check.verified,
                "pass" if check.passed else "fail",
            ]
        )

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def _line(items: list[str]) -> str:
        return " | ".join(item.ljust(col_widths[i]) for i, item in enumerate(items))

    print("\nXV7 Local Smoke Proof")
    print(_line(headers))
    print("-+-".join("-" * w for w in col_widths))
    for row in rows:
        print(_line(row))

    print("\nDetails:")
    for check in checks:
        print(f"- {check.name}: {check.detail}")


def run_smoke() -> int:
    repo_root = _detect_repo_root()
    if repo_root is None:
        print("FAIL: repo root not detected (docker-compose.yml not found).")
        return 1

    print(f"Repo root: {repo_root}")

    core_port = os.getenv("CORE_PORT", "8000").strip() or "8000"
    webui_port = os.getenv("WEBUI_PORT", "8080").strip() or "8080"
    ollama_port = os.getenv("OLLAMA_PORT", "11434").strip() or "11434"

    print(f"Configured CORE_PORT={core_port}")
    print(f"Configured WEBUI_PORT={webui_port}")
    print(f"Configured OLLAMA_PORT={ollama_port}")

    base_url = f"http://localhost:{core_port}"

    dotenv_values = _load_dotenv_file(repo_root / ".env")
    api_key = _normalized(os.getenv("XV7_API_KEY"))
    if api_key is None:
        api_key = _normalized(os.getenv("CORE_API_KEY"))
    if api_key is None:
        api_key = _normalized(dotenv_values.get("XV7_API_KEY"))
    if api_key is None:
        api_key = _normalized(dotenv_values.get("CORE_API_KEY"))

    key_source = STATUS_NOT_CHECKED
    if _normalized(os.getenv("XV7_API_KEY")) is not None:
        key_source = "XV7_API_KEY (process env)"
    elif _normalized(os.getenv("CORE_API_KEY")) is not None:
        key_source = "CORE_API_KEY (process env)"
    elif _normalized(dotenv_values.get("XV7_API_KEY")) is not None:
        key_source = "XV7_API_KEY (.env)"
    elif _normalized(dotenv_values.get("CORE_API_KEY")) is not None:
        key_source = "CORE_API_KEY (.env)"

    print(f"Auth key source for smoke probe: {key_source}")
    if api_key is not None:
        print(f"Auth key value: {redact_secret(api_key)}")
    else:
        print("Auth key value: <not_set>")

    checks: list[SmokeCheck] = []
    checks.append(_endpoint_check("health", f"{base_url}/health"))
    checks.append(_endpoint_check("runtime/status", f"{base_url}/runtime/status"))
    checks.append(_check_runtime_ollama(base_url))
    checks.append(_endpoint_check("personas", f"{base_url}/personas"))
    checks.extend(_check_auth_behavior(base_url, api_key))

    _print_summary(checks)

    exit_code = compute_exit_code(checks)
    if exit_code == 0:
        print("\nSmoke proof result: PASS")
    else:
        print("\nSmoke proof result: FAIL")

    return exit_code


def main() -> None:
    sys.exit(run_smoke())


if __name__ == "__main__":
    main()
