from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_NAME = "X Native Runtime"
APP_VERSION = "0.1.0"
REPO_ROOT = Path(os.getenv("X_NATIVE_REPO_ROOT", "/workspace"))
DATA_ROOT = Path(os.getenv("X_NATIVE_DATA_ROOT", "/data/x_native"))
RECEIPTS_DIR = DATA_ROOT / "receipts"
STAGES_DIR = DATA_ROOT / "stages"
DRAFTS_DIR = DATA_ROOT / "drafts"
WORKSPACE_DIR = DATA_ROOT / "workspace"
REVIEW_BUNDLES_DIR = STAGES_DIR / "review_bundles"
PROMPTS_DIR = STAGES_DIR / "prompts"
RESULT_INTAKE_DIR = STAGES_DIR / "result_intake"


def ensure_data_dirs() -> None:
    for directory in (
        DATA_ROOT,
        RECEIPTS_DIR,
        STAGES_DIR,
        DRAFTS_DIR,
        WORKSPACE_DIR,
        REVIEW_BUNDLES_DIR,
        PROMPTS_DIR,
        RESULT_INTAKE_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(
    directory: Path,
    prefix: str,
    payload: dict[str, Any],
    latest_name: str | None = None,
) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    stamped = directory / f"{utc_stamp()}_{prefix}.json"
    stamped.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    paths = {"path": str(stamped)}
    if latest_name:
        latest = directory / latest_name
        latest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        paths["latest_path"] = str(latest)
    return paths


def read_latest_json(directory: Path, latest_name: str) -> dict[str, Any] | None:
    path = directory / latest_name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def locked_flags() -> dict[str, bool]:
    return {
        "execution_allowed": False,
        "apply_allowed": False,
        "repo_write": False,
        "promoted_to_repo": False,
        "sandbox_only": True,
    }
