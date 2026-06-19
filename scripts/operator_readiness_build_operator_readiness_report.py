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

def build_operator_readiness_report_impl(_deps, args: argparse.Namespace) -> ReadinessReport:
    globals().update(_deps)
    repo_root = _detect_repo_root(Path.cwd())
    dotenv_values = load_dotenv(repo_root / ".env") if repo_root is not None else {}

    env = dict(os.environ)

    core_port = _resolve_port(env, dotenv_values, "CORE_PORT", "8000")
    frontend_port = _resolve_port(env, dotenv_values, "FRONTEND_PORT", "3000")
    open_webui_port = _resolve_port(env, dotenv_values, "WEBUI_PORT", "8080")
    ollama_port = _resolve_port(env, dotenv_values, "OLLAMA_PORT", "11434")

    core_base_url = f"http://localhost:{core_port}"
    frontend_url = f"http://localhost:{frontend_port}"
    open_webui_url = f"http://localhost:{open_webui_port}"
    ollama_base_url = f"http://localhost:{ollama_port}"

    api_key, key_source = resolve_api_key(env, dotenv_values)

    context = ReportContext(
        repo_root=repo_root,
        core_port=core_port,
        frontend_port=frontend_port,
        open_webui_port=open_webui_port,
        ollama_port=ollama_port,
        core_base_url=core_base_url,
        frontend_url=frontend_url,
        open_webui_url=open_webui_url,
        ollama_base_url=ollama_base_url,
        auth_key_source=key_source,
        auth_key_present=api_key is not None,
    )

    checks: list[CheckRow] = []

    if repo_root is None:
        checks.append(
            _fail_row(
                "repo_root_detected",
                True,
                "Could not detect repo root (docker-compose.yml not found).",
                configured=STATUS_FAILED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )
    else:
        checks.append(
            _pass_row(
                "repo_root_detected",
                True,
                f"Repo root detected at {repo_root}.",
            )
        )

    health_row, core_is_healthy = _wait_for_health(
        f"{core_base_url}/health",
        timeout_seconds=float(args.timeout_seconds),
        call_timeout_seconds=min(float(args.timeout_seconds), 5.0),
    )
    checks.append(health_row)

    if not core_is_healthy:
        checks.extend(
            [
                _fail_row(
                    "runtime_status",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
                _fail_row(
                    "runtime_ollama",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
                _fail_row(
                    "runtime_models",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
                _fail_row(
                    "runtime_models_active",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
                _fail_row(
                    "runtime_models_effective",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
                _fail_row(
                    "personas",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
                _fail_row(
                    "ollama_api_tags",
                    True,
                    "Skipped because /health did not reach healthy state.",
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_NOT_CHECKED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_NOT_CHECKED,
                ),
            ]
        )

        checks.append(
            _skip_row(
                "frontend_root", "Skipped because /health did not reach healthy state."
            )
            if args.no_frontend
            else _fail_row(
                "frontend_root",
                True,
                "Skipped because /health did not reach healthy state.",
                configured=STATUS_CONFIGURED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )
        checks.append(
            _skip_row(
                "open_webui_root",
                "Skipped because /health did not reach healthy state.",
            )
            if args.no_open_webui
            else _fail_row(
                "open_webui_root",
                True,
                "Skipped because /health did not reach healthy state.",
                configured=STATUS_CONFIGURED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )

        checks.append(
            _fail_row(
                "auth_without_key",
                True,
                "Skipped because /health did not reach healthy state.",
                configured=STATUS_CONFIGURED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )
        checks.append(
            _fail_row(
                "auth_with_key",
                True,
                "Skipped because /health did not reach healthy state.",
                configured=STATUS_CONFIGURED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )
        checks.append(
            _fail_row(
                "chat_model_use_receipt_proof",
                True,
                "Skipped because /health did not reach healthy state.",
                configured=STATUS_CONFIGURED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )

        summary = ReportSummary(
            active_profile="unknown",
            profile_source="unknown",
            effective_chat_model="-",
            receipt_model_tag="-",
            ollama_model_inventory_count=0,
            frontend_reachable=False,
            open_webui_reachable=False,
        )

        return ReadinessReport(context=context, summary=summary, checks=checks)

    runtime_status_row, _, _ = _endpoint_probe(
        "runtime_status",
        f"{core_base_url}/runtime/status",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(runtime_status_row)

    runtime_ollama_row, runtime_ollama_payload, _ = _endpoint_probe(
        "runtime_ollama",
        f"{core_base_url}/runtime/ollama",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(runtime_ollama_row)

    runtime_models_row, _, _ = _endpoint_probe(
        "runtime_models",
        f"{core_base_url}/runtime/models",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(runtime_models_row)

    runtime_active_row, runtime_active_payload, _ = _endpoint_probe(
        "runtime_models_active",
        f"{core_base_url}/runtime/models/active",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(runtime_active_row)

    runtime_effective_row, runtime_effective_payload, _ = _endpoint_probe(
        "runtime_models_effective",
        f"{core_base_url}/runtime/models/effective",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(runtime_effective_row)

    personas_row, _, _ = _endpoint_probe(
        "personas",
        f"{core_base_url}/personas",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(personas_row)

    frontend_row, _, frontend_status = _endpoint_probe(
        "frontend_root",
        f"{frontend_url}/",
        required=not bool(args.no_frontend),
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(frontend_row)

    open_webui_row, _, open_webui_status = _endpoint_probe(
        "open_webui_root",
        f"{open_webui_url}/",
        required=not bool(args.no_open_webui),
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(open_webui_row)

    ollama_tags_row, ollama_tags_payload, _ = _endpoint_probe(
        "ollama_api_tags",
        f"{ollama_base_url}/api/tags",
        required=True,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.append(ollama_tags_row)

    auth_checks, _ = _auth_behavior_checks(
        f"{core_base_url}/sessions",
        api_key,
        timeout_seconds=float(args.timeout_seconds),
    )
    checks.extend(auth_checks)

    (
        chat_checks,
        active_profile,
        profile_source,
        effective_chat_model,
        receipt_model_tag,
    ) = _chat_model_use_proof(
        core_base_url=core_base_url,
        profile=args.profile,
        api_key=api_key,
        timeout_seconds=float(args.timeout_seconds),
        skip_chat_proof=bool(args.skip_chat_proof),
    )
    checks.extend(chat_checks)

    if active_profile == "unknown" and isinstance(runtime_active_payload, dict):
        maybe_active = runtime_active_payload.get("active_profile")
        if isinstance(maybe_active, str) and maybe_active.strip():
            active_profile = maybe_active.strip()

    if profile_source == "unknown" and isinstance(runtime_active_payload, dict):
        maybe_source = runtime_active_payload.get("profile_source")
        if isinstance(maybe_source, str) and maybe_source.strip():
            profile_source = maybe_source.strip()

    if effective_chat_model == "-" and isinstance(runtime_effective_payload, dict):
        effective_models = runtime_effective_payload.get("effective_models")
        if isinstance(effective_models, dict):
            maybe_chat = effective_models.get("chat")
            if isinstance(maybe_chat, str) and maybe_chat.strip():
                effective_chat_model = maybe_chat.strip()

    ollama_count = 0
    if isinstance(ollama_tags_payload, dict):
        models = ollama_tags_payload.get("models")
        if isinstance(models, list):
            ollama_count = len(models)

    summary = ReportSummary(
        active_profile=active_profile,
        profile_source=profile_source,
        effective_chat_model=effective_chat_model,
        receipt_model_tag=receipt_model_tag,
        ollama_model_inventory_count=ollama_count,
        frontend_reachable=frontend_status == 200,
        open_webui_reachable=open_webui_status == 200,
    )

    return ReadinessReport(context=context, summary=summary, checks=checks)
