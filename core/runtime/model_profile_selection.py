from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RuntimeProfileSelectionState:
    profile: str | None
    source: str


def _normalized(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _state_file_path() -> Path:
    override = _normalized(os.getenv("XV7_RUNTIME_PROFILE_STATE_PATH"))
    if override is not None:
        return Path(override)

    db_path = _normalized(os.getenv("DB_PATH"))
    if db_path is not None:
        return Path(db_path).parent / "runtime" / "model_profile_selection.json"

    return Path("data") / "runtime" / "model_profile_selection.json"


def _read_state_file() -> dict[str, Any]:
    path = _state_file_path()
    if not path.exists():
        return {}

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(parsed, dict):
        return {}

    return parsed


def _write_state_file(payload: dict[str, Any]) -> None:
    path = _state_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def get_runtime_profile_override() -> str | None:
    state = _read_state_file()
    profile = _normalized(state.get("profile"))
    return profile


def set_runtime_profile_override(profile: str, valid_profiles: set[str]) -> str:
    cleaned = _normalized(profile)
    if cleaned is None:
        raise ValueError("Profile is required.")

    if cleaned not in valid_profiles:
        known = ", ".join(sorted(valid_profiles))
        raise ValueError(f"Unknown profile '{cleaned}'. Available profiles: {known}")

    payload = {
        "profile": cleaned,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_state_file(payload)
    return cleaned


def clear_runtime_profile_override() -> None:
    path = _state_file_path()
    if not path.exists():
        return
    path.unlink(missing_ok=True)


def get_runtime_profile_selection_state() -> RuntimeProfileSelectionState:
    override = get_runtime_profile_override()
    if override is None:
        return RuntimeProfileSelectionState(profile=None, source="not_set")
    return RuntimeProfileSelectionState(profile=override, source="runtime_override")
