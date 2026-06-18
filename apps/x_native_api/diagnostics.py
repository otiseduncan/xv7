from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from receipts import (
    APP_NAME,
    APP_VERSION,
    DATA_ROOT,
    RECEIPTS_DIR,
    REPO_ROOT,
    STAGES_DIR,
    DRAFTS_DIR,
    WORKSPACE_DIR,
    locked_flags,
    utc_iso,
    write_json,
)


def git_status_short() -> str:
    if not (REPO_ROOT / ".git").exists():
        return "git metadata unavailable: .git is not mounted"
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
        return result.stdout.strip()
    except Exception as exc:
        return f"git status unavailable: {exc}"


def git_branch() -> str:
    if not (REPO_ROOT / ".git").exists():
        return "unknown"
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def build_state() -> dict[str, Any]:
    receipts = sorted(RECEIPTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    stages = sorted(STAGES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    drafts = sorted(DRAFTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    workspace_files = sorted(
        [path for path in WORKSPACE_DIR.rglob("*") if path.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return {
        "runtime": APP_NAME,
        "version": APP_VERSION,
        "host": platform.node(),
        "platform": platform.platform(),
        "repo_root": str(REPO_ROOT),
        "branch": git_branch(),
        "dirty_files": git_status_short(),
        "data_root": str(DATA_ROOT),
        "receipts_count": len(receipts),
        "stages_count": len(stages),
        "drafts_count": len(drafts),
        "workspace_path": str(WORKSPACE_DIR),
        "workspace_files_count": len(workspace_files),
        "latest_workspace_file": str(workspace_files[0]) if workspace_files else None,
        "latest_receipt": str(receipts[0]) if receipts else None,
        "first_blocker": "none",
    }


def legacy_core_isolated() -> bool:
    return not any(name == "core" or name.startswith("core.") for name in sys.modules)


def git_check() -> dict[str, str]:
    if not (REPO_ROOT / ".git").exists():
        return {
            "status": "warn",
            "message": ".git is not mounted; git-dependent operations are unavailable.",
        }
    status = git_status_short()
    if status.startswith("git status unavailable"):
        return {"status": "warn", "message": status}
    return {"status": "pass", "message": status or "clean"}


def build_checks() -> dict[str, dict[str, str]]:
    return {
        "api_running": {"status": "pass", "detail": "X Native API is running."},
        "data_root_writable": _path_check(DATA_ROOT),
        "receipts_writable": _path_check(RECEIPTS_DIR),
        "repo_visible": {"status": "pass" if REPO_ROOT.exists() else "fail", "detail": str(REPO_ROOT)},
        "git_metadata": git_check(),
        "legacy_core_isolated": {
            "status": "pass" if legacy_core_isolated() else "warn",
            "detail": "Old XV7 core is not imported." if legacy_core_isolated() else "Old XV7 core appears imported.",
        },
        "workspace_writable": _path_check(WORKSPACE_DIR),
    }


def _path_check(path: Path) -> dict[str, str]:
    return {"status": "pass" if os.access(path, os.W_OK) else "fail", "detail": str(path)}


def diagnose_response(raw_text: str) -> dict[str, Any]:
    state = build_state()
    checks = build_checks()
    statuses = [entry["status"] for entry in checks.values()]
    status = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
    receipt = {
        "receipt_type": "x_native_diagnosis",
        "created_at": utc_iso(),
        "status": status,
        "request": raw_text,
        "state": state,
        "checks": checks,
        **locked_flags(),
        "next_safe_step": "Ask X Native for a planner proposal or create a sandbox workspace draft.",
    }
    paths = write_json(RECEIPTS_DIR, "diagnosis", receipt, "latest_diagnosis.json")
    receipt.update({"receipt_path": paths["path"], "latest_receipt_path": paths.get("latest_path")})
    return {"content": render_diagnosis(status, state, checks, paths["path"]), "diagnosis": receipt}


def render_diagnosis(status: str, state: dict[str, Any], checks: dict[str, dict[str, str]], path: str) -> str:
    lines = [
        "X Native diagnosis complete.",
        "",
        f"Status: {status.upper()}",
        f"Runtime: {APP_NAME} {APP_VERSION}",
        f"Repo: {state['repo_root']}",
        f"Branch: {state['branch']}",
        f"Dirty files: {state['dirty_files'] or '0'}",
        f"Data root: {state['data_root']}",
        "First blocker: none",
        "",
        "Checks:",
    ]
    for name, entry in checks.items():
        detail = entry.get("detail", entry.get("message", ""))
        lines.append(f"- {name}: {entry['status'].upper()} - {detail}")
    lines.extend(["", "Proof:", path, "", "Next safe step:", "Ask X to propose a repair plan or create a sandbox workspace draft."])
    return "\n".join(lines)
