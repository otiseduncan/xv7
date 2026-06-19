#!/usr/bin/env python
"""Operator-grade post-launch readiness report for XV7.

This script proves runtime readiness after local launch by checking:
- core and runtime endpoints
- frontend/Open WebUI/Ollama reachability
- auth behavior on /sessions
- effective chat model and safe model-use receipt proof

Security guarantees:
- Never prints API key values
- Never edits .env
- Never pulls/deletes models
- Never claims readiness when required checks fail
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from scripts.operator_readiness_chat_model_use_proof import _chat_model_use_proof_impl
from scripts.operator_readiness_build_operator_readiness_report import build_operator_readiness_report_impl
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STATUS_CONFIGURED = "configured"
STATUS_REACHABLE = "reachable"
STATUS_HEALTHY = "healthy"
STATUS_VERIFIED = "verified"
STATUS_NOT_CHECKED = "not checked"
STATUS_FAILED = "failed"

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_SKIP = "skip"


@dataclass
class CheckRow:
    name: str
    required: bool
    configured: str
    reachable: str
    healthy: str
    verified: str
    result: str
    detail: str

    @property
    def passed(self) -> bool:
        return self.result == RESULT_PASS

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "configured": self.configured,
            "reachable": self.reachable,
            "healthy": self.healthy,
            "verified": self.verified,
            "result": self.result,
            "detail": self.detail,
        }


@dataclass
class ReportContext:
    repo_root: Path | None
    core_port: str
    frontend_port: str
    open_webui_port: str
    ollama_port: str
    core_base_url: str
    frontend_url: str
    open_webui_url: str
    ollama_base_url: str
    auth_key_source: str
    auth_key_present: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_root": str(self.repo_root) if self.repo_root is not None else None,
            "core_port": self.core_port,
            "frontend_port": self.frontend_port,
            "open_webui_port": self.open_webui_port,
            "ollama_port": self.ollama_port,
            "core_base_url": self.core_base_url,
            "frontend_url": self.frontend_url,
            "open_webui_url": self.open_webui_url,
            "ollama_base_url": self.ollama_base_url,
            "auth_key_source": self.auth_key_source,
            "auth_key_present": self.auth_key_present,
        }


@dataclass
class ReportSummary:
    active_profile: str
    profile_source: str
    effective_chat_model: str
    receipt_model_tag: str
    ollama_model_inventory_count: int
    frontend_reachable: bool
    open_webui_reachable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_profile": self.active_profile,
            "profile_source": self.profile_source,
            "effective_chat_model": self.effective_chat_model,
            "receipt_model_tag": self.receipt_model_tag,
            "ollama_model_inventory_count": self.ollama_model_inventory_count,
            "frontend_reachable": self.frontend_reachable,
            "open_webui_reachable": self.open_webui_reachable,
        }


@dataclass
class ReadinessReport:
    context: ReportContext
    summary: ReportSummary
    checks: list[CheckRow]

    @property
    def all_required_pass(self) -> bool:
        return all(c.passed for c in self.checks if c.required)

    def exit_code(self) -> int:
        return 0 if self.all_required_pass else 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "context": self.context.as_dict(),
            "summary": self.summary.as_dict(),
            "checks": [c.as_dict() for c in self.checks],
            "all_required_pass": self.all_required_pass,
            "exit_code": self.exit_code(),
        }


def redact_secret(value: str | None) -> str:
    if value is None:
        return "<not_set>"
    return "<redacted>"


def _detect_repo_root(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "docker-compose.yml").exists():
            return candidate
    return None


def load_dotenv(path: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        value = value.strip().strip('"').strip("'")
        if key and key not in loaded:
            loaded[key] = value
    return loaded


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _resolve_port(
    env: Mapping[str, str],
    dotenv: Mapping[str, str],
    env_name: str,
    default: str,
) -> str:
    return (
        _normalized(env.get(env_name)) or _normalized(dotenv.get(env_name)) or default
    )


def resolve_api_key(
    env: Mapping[str, str], dotenv: Mapping[str, str]
) -> tuple[str | None, str]:
    xv7_env = _normalized(env.get("XV7_API_KEY"))
    core_env = _normalized(env.get("CORE_API_KEY"))
    xv7_dotenv = _normalized(dotenv.get("XV7_API_KEY"))
    core_dotenv = _normalized(dotenv.get("CORE_API_KEY"))

    if xv7_env is not None:
        return xv7_env, "XV7_API_KEY (process env)"
    if core_env is not None:
        return core_env, "CORE_API_KEY (process env)"
    if xv7_dotenv is not None:
        return xv7_dotenv, "XV7_API_KEY (.env)"
    if core_dotenv is not None:
        return core_dotenv, "CORE_API_KEY (.env)"
    return None, "not_set"


def _http_json(
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[int | None, dict[str, Any] | None, str | None]:
    req_headers = headers.copy() if headers is not None else {}
    data: bytes | None = None
    if json_body is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")

    req = Request(url, method=method, headers=req_headers, data=data)

    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8", errors="replace")
            payload: dict[str, Any]
            if raw:
                try:
                    parsed = json.loads(raw)
                    payload = parsed if isinstance(parsed, dict) else {"value": parsed}
                except Exception:
                    # HTML/text endpoints (frontend root, Open WebUI root) are valid
                    # readiness targets even when not JSON.
                    payload = {"raw": raw}
            else:
                payload = {}
            return status, payload, None
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
        payload: dict[str, Any] | None
        try:
            parsed = json.loads(raw) if raw else {}
            payload = parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            payload = None
        return status, payload, f"HTTPError: {exc.reason}"
    except URLError as exc:
        return None, None, f"URLError: {exc.reason}"
    except Exception as exc:
        return None, None, f"{type(exc).__name__}: {exc}"


def _pass_row(name: str, required: bool, detail: str) -> CheckRow:
    return CheckRow(
        name=name,
        required=required,
        configured=STATUS_CONFIGURED,
        reachable=STATUS_REACHABLE,
        healthy=STATUS_HEALTHY,
        verified=STATUS_VERIFIED,
        result=RESULT_PASS,
        detail=detail,
    )


def _fail_row(
    name: str,
    required: bool,
    detail: str,
    *,
    configured: str = STATUS_FAILED,
    reachable: str = STATUS_FAILED,
    healthy: str = STATUS_FAILED,
    verified: str = STATUS_FAILED,
) -> CheckRow:
    return CheckRow(
        name=name,
        required=required,
        configured=configured,
        reachable=reachable,
        healthy=healthy,
        verified=verified,
        result=RESULT_FAIL,
        detail=detail,
    )


def _skip_row(name: str, detail: str) -> CheckRow:
    return CheckRow(
        name=name,
        required=False,
        configured=STATUS_NOT_CHECKED,
        reachable=STATUS_NOT_CHECKED,
        healthy=STATUS_NOT_CHECKED,
        verified=STATUS_NOT_CHECKED,
        result=RESULT_SKIP,
        detail=detail,
    )


def _api_key_headers(api_key: str) -> dict[str, str]:
    return {"X-XV7-API-Key": api_key}


def _wait_for_health(
    health_url: str,
    timeout_seconds: float,
    call_timeout_seconds: float,
) -> tuple[CheckRow, bool]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_detail = "no response"

    while time.monotonic() <= deadline:
        attempts += 1
        status, payload, error = _http_json(
            "GET",
            health_url,
            timeout_seconds=call_timeout_seconds,
        )
        if (
            status == 200
            and isinstance(payload, dict)
            and payload.get("status") == "ok"
        ):
            return (
                _pass_row(
                    "wait_for_health",
                    True,
                    f"GET {health_url} reached healthy state after {attempts} attempts.",
                ),
                True,
            )
        if error is not None:
            last_detail = error
        else:
            last_detail = f"status={status}, payload={payload}"
        time.sleep(1.0)

    return (
        _fail_row(
            "wait_for_health",
            True,
            f"Timed out waiting for healthy core endpoint {health_url}: {last_detail}",
            configured=STATUS_CONFIGURED,
            reachable=STATUS_FAILED,
            healthy=STATUS_FAILED,
            verified=STATUS_NOT_CHECKED,
        ),
        False,
    )


def _endpoint_probe(
    name: str,
    url: str,
    *,
    required: bool,
    timeout_seconds: float,
) -> tuple[CheckRow, dict[str, Any] | None, int | None]:
    status, payload, error = _http_json("GET", url, timeout_seconds=timeout_seconds)
    if status == 200:
        detail = f"GET {url} -> 200"
        return (
            _pass_row(name, required, detail),
            payload if isinstance(payload, dict) else None,
            status,
        )

    if not required:
        detail = f"GET {url} -> optional endpoint unavailable"
        if error is not None:
            detail = f"{detail}: {error}"
        elif status is not None:
            detail = f"{detail}: status={status}"
        return (
            _skip_row(name, detail),
            payload if isinstance(payload, dict) else None,
            status,
        )

    detail = f"GET {url} failed"
    if error is not None:
        detail = f"{detail}: {error}"
    elif status is not None:
        detail = f"{detail}: status={status}"

    reachable = STATUS_REACHABLE if status is not None else STATUS_FAILED
    return (
        _fail_row(
            name,
            required,
            detail,
            configured=STATUS_CONFIGURED,
            reachable=reachable,
            healthy=STATUS_FAILED,
            verified=STATUS_FAILED,
        ),
        payload if isinstance(payload, dict) else None,
        status,
    )


def _auth_behavior_checks(
    sessions_url: str,
    api_key: str | None,
    timeout_seconds: float,
) -> tuple[list[CheckRow], str | None]:
    checks: list[CheckRow] = []
    session_id: str | None = None

    unauth_status, _, unauth_error = _http_json(
        "POST",
        sessions_url,
        timeout_seconds=timeout_seconds,
        json_body={"current_persona": "default"},
    )
    if unauth_status == 401:
        checks.append(
            _pass_row(
                "auth_without_key",
                True,
                f"POST {sessions_url} without auth returned 401 as expected.",
            )
        )
    else:
        detail = f"POST {sessions_url} without auth expected 401, got {unauth_status}."
        if unauth_error is not None:
            detail = f"{detail} {unauth_error}"
        checks.append(
            _fail_row(
                "auth_without_key",
                True,
                detail,
                configured=STATUS_CONFIGURED,
                reachable=(
                    STATUS_REACHABLE if unauth_status is not None else STATUS_FAILED
                ),
                healthy=STATUS_FAILED,
                verified=STATUS_FAILED,
            )
        )

    if api_key is None:
        checks.append(
            _fail_row(
                "auth_with_key",
                True,
                "Cannot verify auth with key because no API key is configured in env/.env.",
                configured=STATUS_FAILED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )
        return checks, None

    auth_status, auth_payload, auth_error = _http_json(
        "POST",
        sessions_url,
        timeout_seconds=timeout_seconds,
        headers=_api_key_headers(api_key),
        json_body={"current_persona": "default"},
    )
    if auth_status == 201 and isinstance(auth_payload, dict):
        sid = auth_payload.get("session_id")
        if isinstance(sid, str) and sid.strip():
            session_id = sid
            checks.append(
                _pass_row(
                    "auth_with_key",
                    True,
                    f"POST {sessions_url} with auth header returned 201.",
                )
            )
        else:
            checks.append(
                _fail_row(
                    "auth_with_key",
                    True,
                    "Auth with key returned 201 but response did not include a valid session_id.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_REACHABLE,
                    healthy=STATUS_FAILED,
                    verified=STATUS_FAILED,
                )
            )
    else:
        detail = f"POST {sessions_url} with auth expected 201, got {auth_status}."
        if auth_error is not None:
            detail = f"{detail} {auth_error}"
        checks.append(
            _fail_row(
                "auth_with_key",
                True,
                detail,
                configured=STATUS_CONFIGURED,
                reachable=STATUS_REACHABLE
                if auth_status is not None
                else STATUS_FAILED,
                healthy=STATUS_FAILED,
                verified=STATUS_FAILED,
            )
        )

    return checks, session_id
def _chat_model_use_proof(
    *,
    core_base_url: str,
    profile: str,
    api_key: str | None,
    timeout_seconds: float,
    skip_chat_proof: bool,
) -> tuple[list[CheckRow], str, str, str, str]:
    return _chat_model_use_proof_impl(
        globals(),
        core_base_url=core_base_url,
        profile=profile,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        skip_chat_proof=skip_chat_proof,
    )

def build_operator_readiness_report(args: argparse.Namespace) -> ReadinessReport:
    return build_operator_readiness_report_impl(globals(), args)







def render_text_report(report: ReadinessReport) -> str:
    headers = [
        "Check",
        "Configured",
        "Reachable",
        "Healthy",
        "Verified",
        "Result",
    ]

    rows: list[list[str]] = []
    for check in report.checks:
        rows.append(
            [
                check.name,
                check.configured,
                check.reachable,
                check.healthy,
                check.verified,
                check.result,
            ]
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def _fmt(items: list[str]) -> str:
        return " | ".join(items[idx].ljust(widths[idx]) for idx in range(len(items)))

    lines: list[str] = []
    lines.append("XV7 Operator Readiness Report")
    lines.append(_fmt(headers))
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        lines.append(_fmt(row))

    lines.append("")
    lines.append("Safe Details")
    lines.append(f"- active_profile: {report.summary.active_profile}")
    lines.append(f"- profile_source: {report.summary.profile_source}")
    lines.append(f"- effective_chat_model: {report.summary.effective_chat_model}")
    lines.append(f"- model_use_receipt_model_tag: {report.summary.receipt_model_tag}")
    lines.append(
        f"- ollama_model_inventory_count: {report.summary.ollama_model_inventory_count}"
    )
    lines.append(
        f"- frontend_reachable: {'yes' if report.summary.frontend_reachable else 'no'}"
    )
    lines.append(
        f"- open_webui_reachable: {'yes' if report.summary.open_webui_reachable else 'no'}"
    )
    lines.append(f"- auth_key_source: {report.context.auth_key_source}")
    lines.append(
        "- auth_key_value: "
        + (
            redact_secret("set")
            if report.context.auth_key_present
            else redact_secret(None)
        )
    )

    lines.append("")
    lines.append("Check Details")
    for check in report.checks:
        lines.append(f"- {check.name}: {check.detail}")

    lines.append("")
    lines.append(
        f"Final Result: {'PASS' if report.all_required_pass else 'FAIL'} (exit {report.exit_code()})"
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Operator-grade launch readiness report for XV7.",
    )
    parser.add_argument(
        "--profile",
        default="local_test",
        help="Runtime profile to use for chat proof override (default: local_test).",
    )
    parser.add_argument(
        "--skip-chat-proof",
        action="store_true",
        help="Skip chat model-use receipt proof while keeping core readiness checks.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Total timeout budget in seconds for health wait and endpoint probes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report.",
    )
    parser.add_argument(
        "--no-open-webui",
        action="store_true",
        help="Treat Open WebUI probe as optional.",
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Treat frontend probe as optional.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_operator_readiness_report(args)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(render_text_report(report))

    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
