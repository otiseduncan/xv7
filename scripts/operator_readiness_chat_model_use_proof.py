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


def _chat_model_use_proof_impl(
    _deps,
    *,
    core_base_url: str,
    profile: str,
    api_key: str | None,
    timeout_seconds: float,
    skip_chat_proof: bool,
) -> tuple[list[CheckRow], str, str, str, str]:
    globals().update(_deps)
    checks: list[CheckRow] = []
    active_profile = "unknown"
    profile_source = "unknown"
    effective_chat_model = "-"
    receipt_model_tag = "-"

    if skip_chat_proof:
        checks.append(
            _skip_row("chat_model_use_receipt_proof", "Skipped by --skip-chat-proof.")
        )
        return (
            checks,
            active_profile,
            profile_source,
            effective_chat_model,
            receipt_model_tag,
        )

    if api_key is None:
        checks.append(
            _fail_row(
                "chat_model_use_receipt_proof",
                True,
                "Cannot run chat proof: API key is required for runtime override and authenticated session checks.",
                configured=STATUS_FAILED,
                reachable=STATUS_NOT_CHECKED,
                healthy=STATUS_FAILED,
                verified=STATUS_NOT_CHECKED,
            )
        )
        return (
            checks,
            active_profile,
            profile_source,
            effective_chat_model,
            receipt_model_tag,
        )

    override_set = False
    try:
        put_status, _, put_error = _http_json(
            "PUT",
            f"{core_base_url}/runtime/models/active",
            timeout_seconds=timeout_seconds,
            headers=_api_key_headers(api_key),
            json_body={"profile": profile, "require_available": True},
        )
        if put_status == 200:
            override_set = True
            checks.append(
                _pass_row(
                    "runtime_override_set",
                    True,
                    f"PUT /runtime/models/active succeeded for profile={profile}.",
                )
            )
        else:
            detail = f"PUT /runtime/models/active failed with status={put_status}."
            if put_error is not None:
                detail = f"{detail} {put_error}"
            checks.append(
                _fail_row(
                    "runtime_override_set",
                    True,
                    detail,
                    configured=STATUS_CONFIGURED,
                    reachable=STATUS_REACHABLE
                    if put_status is not None
                    else STATUS_FAILED,
                    healthy=STATUS_FAILED,
                    verified=STATUS_FAILED,
                )
            )
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        effective_status, effective_payload, effective_error = _http_json(
            "GET",
            f"{core_base_url}/runtime/models/effective",
            timeout_seconds=timeout_seconds,
        )
        if effective_status != 200 or not isinstance(effective_payload, dict):
            detail = (
                f"GET /runtime/models/effective failed with status={effective_status}."
            )
            if effective_error is not None:
                detail = f"{detail} {effective_error}"
            checks.append(_fail_row("effective_model_for_chat_proof", True, detail))
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        active_profile = str(effective_payload.get("active_profile", "unknown"))
        profile_source = str(effective_payload.get("profile_source", "unknown"))
        effective_models = effective_payload.get("effective_models")
        if isinstance(effective_models, dict):
            maybe_chat = effective_models.get("chat")
            if isinstance(maybe_chat, str) and maybe_chat.strip():
                effective_chat_model = maybe_chat.strip()

        if effective_chat_model == "-":
            checks.append(
                _fail_row(
                    "effective_model_for_chat_proof",
                    True,
                    "Effective chat model is missing in /runtime/models/effective response.",
                )
            )
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        checks.append(
            _pass_row(
                "effective_model_for_chat_proof",
                True,
                f"Effective chat model resolved to {effective_chat_model}.",
            )
        )

        session_status, session_payload, session_error = _http_json(
            "POST",
            f"{core_base_url}/sessions",
            timeout_seconds=timeout_seconds,
            headers=_api_key_headers(api_key),
            json_body={"current_persona": "default"},
        )
        if session_status != 201 or not isinstance(session_payload, dict):
            detail = (
                f"POST /sessions for chat proof failed with status={session_status}."
            )
            if session_error is not None:
                detail = f"{detail} {session_error}"
            checks.append(_fail_row("chat_proof_session_create", True, detail))
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        sid = session_payload.get("session_id")
        if not isinstance(sid, str) or not sid.strip():
            checks.append(
                _fail_row(
                    "chat_proof_session_create",
                    True,
                    "Session create succeeded but response had no valid session_id.",
                )
            )
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        checks.append(
            _pass_row(
                "chat_proof_session_create", True, "Session created for chat proof."
            )
        )

        message_status, message_payload, message_error = _http_json(
            "POST",
            f"{core_base_url}/sessions/{sid}/messages",
            timeout_seconds=timeout_seconds,
            headers=_api_key_headers(api_key),
            json_body={"raw_text": "Return exactly: XV7_OPERATOR_READY"},
        )
        if message_status != 200 or not isinstance(message_payload, dict):
            detail = f"POST /sessions/{{id}}/messages for chat proof failed with status={message_status}."
            if message_error is not None:
                detail = f"{detail} {message_error}"
            checks.append(_fail_row("chat_proof_send_message", True, detail))
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        metadata = message_payload.get("metadata")
        receipt: dict[str, Any] | None = (
            metadata if isinstance(metadata, dict) else None
        )
        model_use_receipt = (
            receipt.get("model_use_receipt") if isinstance(receipt, dict) else None
        )
        if not isinstance(model_use_receipt, dict):
            checks.append(
                _fail_row(
                    "chat_model_use_receipt_present",
                    True,
                    "Response metadata.model_use_receipt is missing or invalid.",
                )
            )
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        checks.append(
            _pass_row(
                "chat_model_use_receipt_present",
                True,
                "Response includes safe metadata.model_use_receipt.",
            )
        )

        receipt_tag = model_use_receipt.get("model_tag")
        if isinstance(receipt_tag, str) and receipt_tag.strip():
            receipt_model_tag = receipt_tag.strip()
        else:
            checks.append(
                _fail_row(
                    "chat_model_use_receipt_matches_effective",
                    True,
                    "model_use_receipt.model_tag is missing.",
                )
            )
            return (
                checks,
                active_profile,
                profile_source,
                effective_chat_model,
                receipt_model_tag,
            )

        if receipt_model_tag == effective_chat_model:
            checks.append(
                _pass_row(
                    "chat_model_use_receipt_matches_effective",
                    True,
                    "model_use_receipt.model_tag matches effective chat model.",
                )
            )
        else:
            checks.append(
                _fail_row(
                    "chat_model_use_receipt_matches_effective",
                    True,
                    (
                        "model_use_receipt.model_tag does not match effective chat model "
                        f"({receipt_model_tag} != {effective_chat_model})."
                    ),
                )
            )

    finally:
        if override_set:
            clear_status, _, clear_error = _http_json(
                "DELETE",
                f"{core_base_url}/runtime/models/active",
                timeout_seconds=timeout_seconds,
                headers=_api_key_headers(api_key),
            )
            if clear_status == 200:
                checks.append(
                    _pass_row(
                        "runtime_override_clear",
                        True,
                        "Runtime override cleared after chat proof.",
                    )
                )
            else:
                detail = f"Failed to clear runtime override after proof (status={clear_status})."
                if clear_error is not None:
                    detail = f"{detail} {clear_error}"
                checks.append(_fail_row("runtime_override_clear", True, detail))

    return (
        checks,
        active_profile,
        profile_source,
        effective_chat_model,
        receipt_model_tag,
    )
