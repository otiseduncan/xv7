#!/usr/bin/env python3
"""
xv7_rescue_chat.py

Tiny standard-library CLI for talking to XV7/Xoduz through xv7-core without
VS Code credits, Continue credits, Copilot, or any editor extension.

Usage:
  python scripts/xv7_rescue_chat.py
  python scripts/xv7_rescue_chat.py --message "repo status" --operator
  python scripts/xv7_rescue_chat.py --status
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CORE_URL = "http://localhost:8000"
RESCUE_FOCUS = {
    "id": "XV7-RESCUE-LOCAL-CHAT",
    "title": "XV7 local rescue chat",
    "summary": (
        "Keep Xoduz usable locally first: chat, diagnose runtime/model status, "
        "inspect repo state, and stage safe operator actions without paid VS Code credits."
    ),
    "source": "scripts/xv7_rescue_chat.py",
    "persistence": "session_metadata",
}


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        if key and value:
            values[key] = value
    return values


class XV7Client:
    def __init__(self, core_url: str, api_key: str | None) -> None:
        self.core_url = core_url.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["X-XV7-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.core_url}{path}",
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return {}
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {method} {path}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach xv7-core at {self.core_url}. Is Docker up? {exc}"
            ) from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload)

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PUT", path, payload)

    def create_session(self) -> str:
        state = self.post(
            "/sessions",
            {
                "current_persona": "default",
                "metadata": {
                    "active_focus": RESCUE_FOCUS,
                    "operator_mode_enabled": False,
                },
            },
        )
        return str(state["session_id"])

    def send_message(self, session_id: str, text: str, operator: bool) -> dict[str, Any]:
        return self.post(
            f"/sessions/{session_id}/messages",
            {"raw_text": text, "operator_mode": operator},
        )

    def set_profile(self, profile: str, require_available: bool = False) -> Any:
        return self.put(
            "/runtime/models/active",
            {"profile": profile, "require_available": require_available},
        )


def extract_assistant_text(state: dict[str, Any]) -> str:
    messages = state.get("messages", [])
    for message in reversed(messages):
        if message.get("role") == "assistant":
            metadata = message.get("metadata") or {}
            if isinstance(metadata, dict):
                visible = metadata.get("visible_text")
                if isinstance(visible, str) and visible.strip():
                    return visible.strip()
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
    return "[No assistant message returned]"


def print_json(title: str, payload: Any) -> None:
    print(f"\n## {title}")
    print(json.dumps(payload, indent=2, sort_keys=True))


def print_status(client: XV7Client) -> None:
    for title, path in (
        ("health", "/health"),
        ("runtime status", "/runtime/status"),
        ("ollama", "/runtime/ollama"),
        ("effective models", "/runtime/models/effective?profile=low_resource"),
        ("active model", "/runtime/models/active?profile=low_resource"),
    ):
        try:
            print_json(title, client.get(path))
        except Exception as exc:  # noqa: BLE001 - rescue tool should keep going
            print(f"\n## {title}\nERROR: {exc}")


def interactive_loop(client: XV7Client, session_id: str, operator: bool) -> None:
    print("\nXV7 rescue chat is ready.")
    print("Commands: /status, /profile low_resource, /operator on, /operator off, /repo, /quit")
    print(f"Operator mode: {'on' if operator else 'off'}\n")
    while True:
        try:
            text = input("Otis> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return
        if not text:
            continue
        lowered = text.lower()
        if lowered in {"/q", "/quit", "quit", "exit"}:
            return
        if lowered == "/status":
            print_status(client)
            continue
        if lowered.startswith("/profile"):
            parts = text.split(maxsplit=1)
            profile = parts[1].strip() if len(parts) > 1 else "low_resource"
            try:
                print_json("active model profile", client.set_profile(profile, False))
            except Exception as exc:  # noqa: BLE001
                print(f"Profile switch failed: {exc}")
            continue
        if lowered == "/operator on":
            operator = True
            print("Operator mode on. Mutations should still stage/confirm inside X.")
            continue
        if lowered == "/operator off":
            operator = False
            print("Operator mode off. Read-only chat mode.")
            continue
        if lowered == "/repo":
            text = "repo status"
            operator = True
        try:
            state = client.send_message(session_id, text, operator)
            print(f"\nX> {extract_assistant_text(state)}\n")
        except Exception as exc:  # noqa: BLE001
            print(f"\nERROR: {exc}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Talk to local XV7/Xoduz without VS Code credits.")
    parser.add_argument("--core-url", default=os.getenv("XV7_CORE_URL", DEFAULT_CORE_URL))
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--message", "-m", default=None)
    parser.add_argument("--operator", action="store_true", help="Send message with operator_mode=true")
    parser.add_argument("--status", action="store_true", help="Print runtime status and exit")
    parser.add_argument("--profile", default="low_resource", help="Model profile to activate before chat")
    parser.add_argument(
        "--skip-profile-set",
        action="store_true",
        help="Do not call /runtime/models/active before chatting",
    )
    args = parser.parse_args()

    dotenv = load_dotenv(Path(".env"))
    api_key = args.api_key or os.getenv("XV7_API_KEY") or os.getenv("CORE_API_KEY") or dotenv.get("CORE_API_KEY") or dotenv.get("XV7_API_KEY")
    client = XV7Client(args.core_url, api_key)

    try:
        if args.status:
            print_status(client)
            return 0
        if not args.skip_profile_set:
            client.set_profile(args.profile, require_available=False)
        session_id = client.create_session()
        if args.message:
            state = client.send_message(session_id, args.message, args.operator)
            print(extract_assistant_text(state))
            return 0
        interactive_loop(client, session_id, args.operator)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI entry point
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
