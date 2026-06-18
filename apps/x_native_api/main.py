from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_NAME = "X Native Runtime"
APP_VERSION = "0.1.0"
REPO_ROOT = Path(os.getenv("X_NATIVE_REPO_ROOT", "/workspace"))
DATA_ROOT = Path(os.getenv("X_NATIVE_DATA_ROOT", "/data/x_native"))
RECEIPTS_DIR = DATA_ROOT / "receipts"
STAGES_DIR = DATA_ROOT / "stages"
DRAFTS_DIR = DATA_ROOT / "drafts"

for directory in (DATA_ROOT, RECEIPTS_DIR, STAGES_DIR, DRAFTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NativeMessageRequest(BaseModel):
    raw_text: str = Field(default="")
    operator_mode: bool = False


class AttachContentRequest(BaseModel):
    content: str = Field(default="")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_slug(text: str, default: str = "x_native_output") -> str:
    match = re.search(r"(?:file|path)\s+([A-Za-z0-9_./\\-]+)", text, re.IGNORECASE)
    candidate = match.group(1) if match else default
    candidate = candidate.replace("\\", "/").strip("/.")
    candidate = re.sub(r"[^A-Za-z0-9_./-]", "_", candidate)
    if not candidate or ".." in candidate.split("/"):
        candidate = default
    if "." not in Path(candidate).name:
        candidate = f"{candidate}.txt"
    return candidate


def write_json(directory: Path, prefix: str, payload: dict[str, Any], latest_name: str | None = None) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    stamped = directory / f"{utc_stamp()}_{prefix}.json"
    stamped.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    paths = {"path": str(stamped)}
    if latest_name:
        latest = directory / latest_name
        latest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        paths["latest_path"] = str(latest)
    return paths


def git_status_short() -> str:
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


def classify(raw_text: str) -> dict[str, Any]:
    lower = raw_text.lower()
    write_words = ("create file", "edit file", "write file", "patch", "repair", "fix", "modify", "change")
    inspect_words = ("diagnose", "inspect", "state", "status", "health", "doctor", "readiness")
    if any(word in lower for word in write_words):
        return {
            "intent": "repo_change_request",
            "risk": "developer_write",
            "route": "stage",
            "summary": "Stage a requested repair/change without applying it.",
        }
    if any(word in lower for word in inspect_words):
        return {
            "intent": "diagnose",
            "risk": "developer_read",
            "route": "tool",
            "summary": "Inspect X Native runtime state and write proof receipt.",
        }
    return {
        "intent": "conversation",
        "risk": "read_only",
        "route": "answer",
        "summary": "Answer without execution.",
    }


def build_state() -> dict[str, Any]:
    receipts = sorted(RECEIPTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    stages = sorted(STAGES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    drafts = sorted(DRAFTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
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
        "latest_receipt": str(receipts[0]) if receipts else None,
        "first_blocker": "none",
    }


def diagnose_response(raw_text: str) -> dict[str, Any]:
    state = build_state()
    checks = {
        "api_running": True,
        "data_root_writable": os.access(DATA_ROOT, os.W_OK),
        "receipts_writable": os.access(RECEIPTS_DIR, os.W_OK),
        "repo_visible": REPO_ROOT.exists(),
        "git_available": not git_status_short().startswith("git status unavailable"),
        "legacy_core_imported": False,
    }
    status = "pass" if all(checks.values()) else "warn"
    receipt = {
        "receipt_type": "x_native_diagnosis",
        "created_at": utc_iso(),
        "status": status,
        "request": raw_text,
        "state": state,
        "checks": checks,
        "next_safe_step": "Use a staged repair request if a blocker appears. No apply path is enabled in X Native baseline.",
    }
    paths = write_json(RECEIPTS_DIR, "diagnosis", receipt, "latest_diagnosis.json")
    receipt.update({"receipt_path": paths["path"], "latest_receipt_path": paths.get("latest_path")})
    content = (
        "X Native diagnosis complete.\n\n"
        f"Status: {status.upper()}\n"
        f"Runtime: {APP_NAME} {APP_VERSION}\n"
        f"Repo: {state['repo_root']}\n"
        f"Branch: {state['branch']}\n"
        f"Dirty files: {state['dirty_files'] or '0'}\n"
        f"Data root: {state['data_root']}\n"
        "First blocker: none\n\n"
        "Checks:\n"
        + "\n".join(f"- {name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items())
        + "\n\nProof:\n"
        f"{paths['path']}\n"
        "\nNext safe step:\n"
        "Ask X to stage a repair plan. X Native will stage/preview only; apply is still locked."
    )
    return {"content": content, "diagnosis": receipt}


def stage_response(raw_text: str, decision: dict[str, Any]) -> dict[str, Any]:
    stage_id = str(uuid4())
    suggested_path = safe_slug(raw_text)
    stage = {
        "receipt_type": "x_native_stage",
        "created_at": utc_iso(),
        "stage_id": stage_id,
        "status": "staged_pending_preview",
        "source_text": raw_text,
        "intent": decision["intent"],
        "risk": decision["risk"],
        "route": decision["route"],
        "summary": decision["summary"],
        "suggested_path": f"data/x_runtime/tmp/{Path(suggested_path).name}",
        "execution_allowed": False,
        "apply_allowed": False,
        "repo_write": False,
        "preview_ready": False,
        "next_step": "Preview the staged action, then attach operator-reviewed content. Apply remains locked.",
    }
    paths = write_json(STAGES_DIR, f"stage_{stage_id}", stage, "latest_stage.json")
    stage.update({"stage_path": paths["path"], "latest_stage_path": paths.get("latest_path")})
    content = (
        "X Native staged the request.\n\n"
        f"Stage ID: {stage_id}\n"
        f"Intent: {decision['intent']}\n"
        f"Risk: {decision['risk']}\n"
        f"Source request: {raw_text}\n"
        f"Suggested path: {stage['suggested_path']}\n"
        "Execution allowed: False\n"
        "Apply allowed: False\n"
        "Repo write: False\n\n"
        f"Proof: {paths['path']}\n"
        "\nNext safe step: Preview this stage in the X Native UI."
    )
    return {"content": content, "stage": stage}


def read_latest_json(directory: Path, latest_name: str) -> dict[str, Any] | None:
    path = directory / latest_name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "runtime": APP_NAME, "version": APP_VERSION}


@app.get("/x-native/state")
def x_native_state() -> dict[str, Any]:
    state = build_state()
    receipt = {"receipt_type": "x_native_state", "created_at": utc_iso(), "state": state}
    paths = write_json(RECEIPTS_DIR, "state", receipt, "latest_state.json")
    return {"status": "completed", "state": state, "receipt_path": paths["path"]}


@app.post("/x-native/message")
def x_native_message(payload: NativeMessageRequest) -> dict[str, Any]:
    raw_text = payload.raw_text.strip()
    decision = classify(raw_text)
    if decision["route"] == "tool":
        result = diagnose_response(raw_text)
        return {"status": "completed", "decision": decision, **result}
    if decision["route"] == "stage":
        result = stage_response(raw_text, decision)
        return {"status": "staged", "decision": decision, **result}
    content = "X Native received the message. No action was required. Ask me to diagnose, inspect, or stage a repair."
    return {"status": "answered", "decision": decision, "content": content}


@app.get("/x-native/stages/latest")
def x_native_latest_stage() -> dict[str, Any]:
    stage = read_latest_json(STAGES_DIR, "latest_stage.json")
    return {"status": "completed" if stage else "empty", "stage": stage, "execution_allowed": False, "apply_allowed": False}


@app.post("/x-native/stages/{stage_id}/preview")
def x_native_preview(stage_id: str) -> dict[str, Any]:
    stage = read_latest_json(STAGES_DIR, "latest_stage.json")
    if not stage or stage.get("stage_id") != stage_id:
        return {"status": "not_found", "stage_id": stage_id, "execution_allowed": False, "apply_allowed": False}
    preview = {
        "kind": "x_native_preview_v0",
        "stage_id": stage_id,
        "source_text": stage.get("source_text"),
        "suggested_path": stage.get("suggested_path"),
        "preview_only": True,
        "is_executor_ready": False,
        "execution_allowed": False,
        "apply_allowed": False,
        "rendered_preview": (
            "X NATIVE PREVIEW ONLY\n\n"
            f"Stage ID: {stage_id}\n"
            f"Source request: {stage.get('source_text')}\n"
            f"Suggested path: {stage.get('suggested_path')}\n\n"
            "No apply path is enabled in this baseline."
        ),
    }
    stage.update({"status": "preview_ready", "preview_ready": True, "preview": preview})
    paths = write_json(STAGES_DIR, f"preview_{stage_id}", stage, "latest_stage.json")
    return {"status": "preview_ready", "stage_id": stage_id, "preview": preview, "receipt_path": paths["path"], "execution_allowed": False, "apply_allowed": False}


@app.post("/x-native/stages/{stage_id}/draft")
def x_native_draft(stage_id: str, payload: AttachContentRequest) -> dict[str, Any]:
    stage = read_latest_json(STAGES_DIR, "latest_stage.json")
    if not stage or stage.get("stage_id") != stage_id:
        return {"status": "not_found", "stage_id": stage_id, "execution_allowed": False, "apply_allowed": False}
    draft = {
        "kind": "x_native_draft_v0",
        "created_at": utc_iso(),
        "stage_id": stage_id,
        "source_text": stage.get("source_text"),
        "path": stage.get("suggested_path"),
        "content": payload.content,
        "draft_only": True,
        "not_in_pending_queue": True,
        "is_executor_ready": False,
        "execution_allowed": False,
        "apply_allowed": False,
        "rendered_draft": (
            "X NATIVE DRAFT ONLY\n\n"
            f"Stage ID: {stage_id}\n"
            f"Path: {stage.get('suggested_path')}\n"
            "Content attached for review only. Apply is locked."
        ),
    }
    draft_paths = write_json(DRAFTS_DIR, f"draft_{stage_id}", draft, "latest_draft.json")
    receipt = {"receipt_type": "x_native_draft", "created_at": utc_iso(), "draft": draft, "paths": draft_paths}
    receipt_paths = write_json(RECEIPTS_DIR, f"draft_{stage_id}", receipt, "latest_draft_receipt.json")
    stage.update({"status": "draft_ready", "draft_ready": True, "draft_path": draft_paths["path"]})
    write_json(STAGES_DIR, f"draft_stage_{stage_id}", stage, "latest_stage.json")
    return {"status": "draft_ready", "draft": draft, "draft_path": draft_paths["path"], "receipt_path": receipt_paths["path"], "execution_allowed": False, "apply_allowed": False}


@app.get("/x-native/drafts/latest")
def x_native_latest_draft() -> dict[str, Any]:
    draft = read_latest_json(DRAFTS_DIR, "latest_draft.json")
    return {"status": "completed" if draft else "empty", "draft": draft, "execution_allowed": False, "apply_allowed": False}
