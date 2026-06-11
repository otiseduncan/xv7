from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import operator_readiness_report as report_mod


def _args(extra: list[str] | None = None):
    return report_mod.parse_args(extra or [])


def _http_fake_factory(
    *, secret_expected: str | None = None, effective_chat: str = "qwen3:14b"
):
    state = {
        "unauth_sessions_called": 0,
        "auth_sessions_called": 0,
        "override_set": False,
        "effective_chat": effective_chat,
    }

    def _fake(
        method: str,
        url: str,
        *,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
    ):
        path = url.split("localhost", 1)[-1]
        headers = headers or {}
        has_key = "X-XV7-API-Key" in headers
        if secret_expected is not None and has_key:
            assert headers["X-XV7-API-Key"] == secret_expected

        if method == "GET" and path.endswith(":8000/health"):
            return 200, {"status": "ok"}, None
        if method == "GET" and path.endswith(":8000/runtime/status"):
            return 200, {"status": "ok"}, None
        if method == "GET" and path.endswith(":8000/runtime/ollama"):
            return 200, {"reachable": True}, None
        if method == "GET" and path.endswith(":8000/runtime/models"):
            return 200, {"available_profiles": ["balanced", "local_test"]}, None
        if method == "GET" and path.endswith(":8000/runtime/models/active"):
            source = "runtime_override" if state["override_set"] else "env"
            profile = "local_test" if state["override_set"] else "balanced"
            return 200, {"active_profile": profile, "profile_source": source}, None
        if method == "GET" and path.endswith(":8000/runtime/models/effective"):
            source = "runtime_override" if state["override_set"] else "env"
            profile = "local_test" if state["override_set"] else "balanced"
            return (
                200,
                {
                    "active_profile": profile,
                    "profile_source": source,
                    "effective_models": {"chat": state["effective_chat"]},
                },
                None,
            )
        if method == "GET" and path.endswith(":8000/personas"):
            return 200, {"count": 1, "personas": {"default": {"name": "default"}}}, None
        if method == "GET" and path.endswith(":3000/"):
            return 200, {"ok": True}, None
        if method == "GET" and path.endswith(":8080/"):
            return 200, {"ok": True}, None
        if method == "GET" and path.endswith(":11434/api/tags"):
            return 200, {"models": [{"name": "qwen3:8b"}, {"name": "qwen3:14b"}]}, None

        if method == "POST" and path.endswith(":8000/sessions") and not has_key:
            state["unauth_sessions_called"] += 1
            return 401, {"detail": "XV7 API key required"}, "HTTPError: Unauthorized"

        if method == "POST" and path.endswith(":8000/sessions") and has_key:
            state["auth_sessions_called"] += 1
            sid = (
                "session-auth" if state["auth_sessions_called"] == 1 else "session-chat"
            )
            return 201, {"session_id": sid, "current_persona": "default"}, None

        if method == "PUT" and path.endswith(":8000/runtime/models/active") and has_key:
            if json_body and json_body.get("profile") == "local_test":
                state["override_set"] = True
                return 200, {"active_profile": "local_test"}, None
            return 400, {"detail": "bad profile"}, "HTTPError: Bad Request"

        if (
            method == "POST"
            and ":8000/sessions/" in path
            and path.endswith("/messages")
            and has_key
        ):
            return (
                200,
                {
                    "metadata": {
                        "model_use_receipt": {
                            "model_tag": state["effective_chat"],
                            "runtime_role": "chat",
                        }
                    },
                    "messages": [
                        {"role": "assistant", "content": "XV7_OPERATOR_READY"},
                    ],
                },
                None,
            )

        if (
            method == "DELETE"
            and path.endswith(":8000/runtime/models/active")
            and has_key
        ):
            state["override_set"] = False
            return 200, {"active_profile": "balanced", "profile_source": "env"}, None

        return 500, {"detail": f"unmocked {method} {url}"}, "HTTPError: Server Error"

    return _fake, state


def _patch_common(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(report_mod, "_detect_repo_root", lambda _start=None: tmp_path)
    monkeypatch.setattr(report_mod.time, "sleep", lambda _s: None)


def test_env_parse_and_output_redacts_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "CORE_API_KEY=super-secret-value\n", encoding="utf-8"
    )
    _patch_common(monkeypatch, tmp_path)

    fake_http, _ = _http_fake_factory(secret_expected="super-secret-value")
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    report = report_mod.build_operator_readiness_report(
        _args(["--profile", "local_test"])
    )
    text = report_mod.render_text_report(report)
    blob = json.dumps(report.as_dict()) + "\n" + text

    assert "super-secret-value" not in blob
    assert "<redacted>" in text


def test_report_fails_when_required_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)

    def _http_fail_status(
        method: str,
        url: str,
        *,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
    ):
        if method == "GET" and url.endswith("/health"):
            return 200, {"status": "ok"}, None
        if method == "GET" and url.endswith("/runtime/status"):
            return 500, {"detail": "boom"}, "HTTPError: Internal Server Error"
        # keep the rest green enough to isolate required-check failure handling
        return 200, {}, None

    monkeypatch.setattr(report_mod, "_http_json", _http_fail_status)
    monkeypatch.setenv("CORE_API_KEY", "x")

    report = report_mod.build_operator_readiness_report(_args(["--skip-chat-proof"]))
    assert report.exit_code() != 0


def test_auth_proof_requires_401_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setenv("CORE_API_KEY", "test-key")

    fake_http, _ = _http_fake_factory(secret_expected="test-key")
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    report = report_mod.build_operator_readiness_report(_args(["--skip-chat-proof"]))
    auth_without = next(c for c in report.checks if c.name == "auth_without_key")
    assert auth_without.result == "pass"


def test_auth_proof_fails_if_unauthenticated_session_creation_returns_201(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setenv("CORE_API_KEY", "test-key")

    fake_http, _ = _http_fake_factory(secret_expected="test-key")

    def _fake_with_regression(
        method: str,
        url: str,
        *,
        timeout_seconds: float,
        headers: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
    ):
        if (
            method == "POST"
            and url.endswith(":8000/sessions")
            and not (headers or {}).get("X-XV7-API-Key")
        ):
            return 201, {"session_id": "unexpected-public"}, None
        return fake_http(
            method,
            url,
            timeout_seconds=timeout_seconds,
            headers=headers,
            json_body=json_body,
        )

    monkeypatch.setattr(report_mod, "_http_json", _fake_with_regression)

    report = report_mod.build_operator_readiness_report(_args(["--skip-chat-proof"]))
    auth_without = next(c for c in report.checks if c.name == "auth_without_key")
    assert auth_without.result == "fail"
    assert report.exit_code() != 0


def test_auth_proof_requires_201_with_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setenv("CORE_API_KEY", "test-key")

    fake_http, _ = _http_fake_factory(secret_expected="test-key")
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    report = report_mod.build_operator_readiness_report(_args(["--skip-chat-proof"]))
    auth_with = next(c for c in report.checks if c.name == "auth_with_key")
    assert auth_with.result == "pass"


def test_receipt_model_tag_must_match_effective_chat_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setenv("CORE_API_KEY", "test-key")

    fake_http, _ = _http_fake_factory(
        secret_expected="test-key", effective_chat="qwen3:14b"
    )
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    report = report_mod.build_operator_readiness_report(
        _args(["--profile", "local_test"])
    )
    match_check = next(
        c for c in report.checks if c.name == "chat_model_use_receipt_matches_effective"
    )
    assert match_check.result == "pass"
    assert report.summary.effective_chat_model == "qwen3:14b"
    assert report.summary.receipt_model_tag == "qwen3:14b"


def test_skip_chat_proof_skips_only_chat_proof(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setenv("CORE_API_KEY", "test-key")

    fake_http, state = _http_fake_factory(secret_expected="test-key")
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    report = report_mod.build_operator_readiness_report(_args(["--skip-chat-proof"]))

    skip_check = next(
        c for c in report.checks if c.name == "chat_model_use_receipt_proof"
    )
    assert skip_check.result == "skip"

    # Core readiness still runs.
    health = next(c for c in report.checks if c.name == "wait_for_health")
    runtime = next(c for c in report.checks if c.name == "runtime_status")
    assert health.result == "pass"
    assert runtime.result == "pass"

    # Chat proof path (second authenticated session create) was not called.
    assert state["auth_sessions_called"] == 1


def test_json_output_is_valid_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".env").write_text("CORE_API_KEY=json-secret\n", encoding="utf-8")
    _patch_common(monkeypatch, tmp_path)

    fake_http, _ = _http_fake_factory(secret_expected="json-secret")
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    exit_code = report_mod.main(["--json", "--skip-chat-proof"])
    assert exit_code in (0, 1)

    out = capsys.readouterr().out
    loaded = json.loads(out)
    assert isinstance(loaded, dict)
    assert "checks" in loaded
    assert "json-secret" not in out


def test_script_artifact_exists_and_expected_flags_present() -> None:
    script_path = Path("scripts/operator_readiness_report.py")
    assert script_path.exists()

    text = script_path.read_text(encoding="utf-8")
    for flag in (
        "--profile",
        "--skip-chat-proof",
        "--timeout-seconds",
        "--json",
        "--no-open-webui",
        "--no-frontend",
    ):
        assert flag in text


def test_text_output_never_prints_raw_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setenv("XV7_API_KEY", "no-print-key")

    fake_http, _ = _http_fake_factory(secret_expected="no-print-key")
    monkeypatch.setattr(report_mod, "_http_json", fake_http)

    report = report_mod.build_operator_readiness_report(_args(["--skip-chat-proof"]))
    text = report_mod.render_text_report(report)
    assert "no-print-key" not in text
    assert "<redacted>" in text
