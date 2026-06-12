from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ProofStep:
    name: str
    ok: bool
    detail: str


def _request_json(
    *,
    method: str,
    url: str,
    api_key: str | None,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-XV7-API-Key"] = api_key

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310: local operator proof utility
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {raw}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc}") from exc


def _latest_message(payload: dict[str, Any]) -> dict[str, Any]:
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise AssertionError("session response did not include messages")
    latest = messages[-1]
    if not isinstance(latest, dict):
        raise AssertionError("latest message is not an object")
    return latest


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise AssertionError("session response did not include metadata")
    return metadata


def _provenance(payload: dict[str, Any]) -> dict[str, Any]:
    provenance = _metadata(payload).get("answer_provenance")
    if not isinstance(provenance, dict):
        raise AssertionError("metadata.answer_provenance is missing")
    return provenance


def _last_assistant_payload(payload: dict[str, Any]) -> dict[str, Any]:
    assistant_payload = _metadata(payload).get("last_assistant_payload")
    if not isinstance(assistant_payload, dict):
        raise AssertionError("metadata.last_assistant_payload is missing")
    return assistant_payload


def _context_record_ids(payload: dict[str, Any]) -> list[str]:
    receipt = _metadata(payload).get("context_receipt", {})
    if not isinstance(receipt, dict):
        return []
    return [str(item) for item in receipt.get("record_ids", [])]


def _assert_policy_only(payload: dict[str, Any]) -> None:
    provenance = _provenance(payload)
    if provenance.get("runtime_model_inference_proven") is not False:
        raise AssertionError(f"expected policy-only route, got provenance={provenance}")
    if provenance.get("answer_source") == "runtime_model_inference":
        raise AssertionError(f"unexpected model fallback provenance={provenance}")

    assistant_payload = _last_assistant_payload(payload)
    model_receipt = assistant_payload.get("model_use_receipt")
    if model_receipt not in ({}, None):
        raise AssertionError(f"unexpected model_use_receipt={model_receipt}")


def _assert_contains(text: str, *needles: str) -> None:
    lowered = text.lower()
    missing = [needle for needle in needles if needle.lower() not in lowered]
    if missing:
        raise AssertionError(f"missing {missing!r} from text: {text!r}")


def run_proof(base_url: str, api_key: str | None, timeout: float) -> list[ProofStep]:
    base = base_url.rstrip("/")
    steps: list[ProofStep] = []

    health = _request_json(
        method="GET",
        url=f"{base}/health",
        api_key=None,
        timeout=timeout,
    )
    if health.get("status") != "ok":
        raise AssertionError(f"health endpoint did not return ok: {health}")
    steps.append(ProofStep("health", True, "runtime API reachable"))

    session = _request_json(
        method="POST",
        url=f"{base}/sessions",
        api_key=api_key,
        payload={"current_persona": "default"},
        timeout=timeout,
    )
    session_id = str(session.get("session_id", "")).strip()
    if not session_id:
        raise AssertionError(f"session create did not return session_id: {session}")
    steps.append(ProofStep("session", True, session_id))

    focus_text = (
        "correct communication with operator Otis, learning his workflows, "
        "and reducing hallucinations with proof-first answers"
    )
    set_focus = _request_json(
        method="POST",
        url=f"{base}/sessions/{session_id}/messages",
        api_key=api_key,
        payload={"raw_text": f"change your active focus to {focus_text}"},
        timeout=timeout,
    )
    answer = str(_latest_message(set_focus).get("content", ""))
    _assert_contains(answer, "updating active focus")
    _assert_policy_only(set_focus)
    metadata = _metadata(set_focus)
    active_focus = metadata.get("active_focus")
    if not isinstance(active_focus, dict):
        raise AssertionError("metadata.active_focus missing after focus update")
    focus_id = str(active_focus.get("id", "")).strip()
    if not focus_id.startswith("XV7-FOCUS-"):
        raise AssertionError(f"unexpected active focus id: {focus_id!r}")
    if active_focus.get("persistence") != "brain_record_saved":
        raise AssertionError(f"active focus was not persisted: {active_focus}")
    provenance = _provenance(set_focus)
    if provenance.get("intent_class") != "active_focus_update":
        raise AssertionError(f"wrong intent class: {provenance}")
    if provenance.get("action") != "create_active_focus_record":
        raise AssertionError(f"wrong focus action: {provenance}")
    steps.append(ProofStep("focus_update", True, f"{focus_id} persisted"))

    ask_focus = _request_json(
        method="POST",
        url=f"{base}/sessions/{session_id}/messages",
        api_key=api_key,
        payload={"raw_text": "what did I just change your focus to?"},
        timeout=timeout,
    )
    ask_text = str(_latest_message(ask_focus).get("content", ""))
    _assert_contains(ask_text, "active focus", "communication")
    _assert_policy_only(ask_focus)
    if focus_id not in _context_record_ids(ask_focus):
        raise AssertionError(
            f"focus id {focus_id} missing from context receipt: {_metadata(ask_focus).get('context_receipt')!r}"
        )
    steps.append(ProofStep("same_session_recall", True, "focus recalled without model fallback"))

    new_session = _request_json(
        method="POST",
        url=f"{base}/sessions",
        api_key=api_key,
        payload={"current_persona": "default"},
        timeout=timeout,
    )
    new_session_id = str(new_session.get("session_id", "")).strip()
    if not new_session_id:
        raise AssertionError(f"new session did not return session_id: {new_session}")

    fresh_recall = _request_json(
        method="POST",
        url=f"{base}/sessions/{new_session_id}/messages",
        api_key=api_key,
        payload={"raw_text": "what is your current active focus"},
        timeout=timeout,
    )
    fresh_text = str(_latest_message(fresh_recall).get("content", ""))
    _assert_contains(fresh_text, "communication")
    _assert_policy_only(fresh_recall)
    if focus_id not in _context_record_ids(fresh_recall):
        raise AssertionError(
            f"persisted focus id {focus_id} missing in fresh session receipt: {_metadata(fresh_recall).get('context_receipt')!r}"
        )
    steps.append(ProofStep("fresh_session_recall", True, "persisted focus loaded in new session"))

    guided = _request_json(
        method="POST",
        url=f"{base}/sessions/{new_session_id}/messages",
        api_key=api_key,
        payload={
            "raw_text": "so what are the next steps that we need to pursue an increasing fluid communication",
        },
        timeout=timeout,
    )
    guided_text = str(_latest_message(guided).get("content", ""))
    _assert_contains(
        guided_text,
        "track otis corrections",
        "save communication preferences",
        "learn workflow habits",
        "compact receipts",
        "source/proof",
    )
    guided_metadata = _metadata(guided)
    if guided_metadata.get("response_mode") != "active_focus_guided":
        raise AssertionError(f"guided response_mode missing: {guided_metadata}")
    if guided_metadata.get("model_used") != "policy_only":
        raise AssertionError(f"guided response was not policy_only: {guided_metadata}")
    if guided_metadata.get("fallback_used") is not False:
        raise AssertionError(f"guided response fallback flag is wrong: {guided_metadata}")
    if focus_id not in [str(item) for item in guided_metadata.get("source_record_ids", [])]:
        raise AssertionError(f"focus id missing from source_record_ids: {guided_metadata}")
    steps.append(ProofStep("guided_follow_up", True, "active-focus-guided response used"))

    query = urlencode({"layer": "active_focus", "include_archived": "false"})
    records = _request_json(
        method="GET",
        url=f"{base}/runtime/brain/records?{query}",
        api_key=None,
        timeout=timeout,
    )
    active_records = records.get("records")
    if not isinstance(active_records, list):
        raise AssertionError(f"runtime brain records response invalid: {records}")
    if not any(isinstance(item, dict) and item.get("record_id") == focus_id for item in active_records):
        raise AssertionError(f"focus id {focus_id} missing from active runtime records: {records}")
    steps.append(ProofStep("runtime_records", True, "active focus visible through runtime brain API"))

    return steps


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Code 7 live proof for XV7 Active Focus communication routing."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="XV7 API base URL. Default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="XV7 API key. Defaults to XV7_API_KEY from the environment when omitted.",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    import os

    api_key = args.api_key or os.getenv("XV7_API_KEY")
    start = time.perf_counter()
    try:
        steps = run_proof(args.base_url, api_key, args.timeout)
    except Exception as exc:  # pragma: no cover - CLI diagnostic path
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    print(
        json.dumps(
            {
                "ok": True,
                "elapsed_ms": elapsed_ms,
                "steps": [step.__dict__ for step in steps],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
