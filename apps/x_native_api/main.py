from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from planner import build_repair_proposal, planner_keywords, should_stage_plan

APP_NAME = "X Native Runtime"
APP_VERSION = "0.1.0"
REPO_ROOT = Path(os.getenv("X_NATIVE_REPO_ROOT", "/workspace"))
DATA_ROOT = Path(os.getenv("X_NATIVE_DATA_ROOT", "/data/x_native"))
RECEIPTS_DIR = DATA_ROOT / "receipts"
STAGES_DIR = DATA_ROOT / "stages"
DRAFTS_DIR = DATA_ROOT / "drafts"
WORKSPACE_DIR = DATA_ROOT / "workspace"

for directory in (DATA_ROOT, RECEIPTS_DIR, STAGES_DIR, DRAFTS_DIR, WORKSPACE_DIR):
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


class WorkspaceDraftRequest(BaseModel):
    path: str = Field(default="x_native_workspace_draft.txt")
    content: str = Field(default="")
    stage_id: str | None = None
    plan: dict[str, Any] | None = None


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


def git_check() -> dict[str, Any]:
    if not (REPO_ROOT / ".git").exists():
        return {
            "status": "warn",
            "message": ".git is not mounted; git-dependent operations are unavailable but runtime can still inspect, plan, stage, and draft.",
        }
    status = git_status_short()
    if status.startswith("git status unavailable"):
        return {"status": "warn", "message": status}
    return {"status": "pass", "message": status or "clean"}


def diagnose_response(raw_text: str) -> dict[str, Any]:
    state = build_state()
    git = git_check()
    checks = {
        "api_running": {"status": "pass", "detail": "X Native API is running."},
        "data_root_writable": {
            "status": "pass" if os.access(DATA_ROOT, os.W_OK) else "fail",
            "detail": str(DATA_ROOT),
        },
        "receipts_writable": {
            "status": "pass" if os.access(RECEIPTS_DIR, os.W_OK) else "fail",
            "detail": str(RECEIPTS_DIR),
        },
        "repo_visible": {
            "status": "pass" if REPO_ROOT.exists() else "fail",
            "detail": str(REPO_ROOT),
        },
        "git_metadata": git,
        "legacy_core_isolated": {
            "status": "pass" if legacy_core_isolated() else "warn",
            "detail": "Old XV7 core is not imported." if legacy_core_isolated() else "Old XV7 core appears imported.",
        },
        "workspace_writable": {
            "status": "pass" if os.access(WORKSPACE_DIR, os.W_OK) else "fail",
            "detail": str(WORKSPACE_DIR),
        },
    }
    statuses = [entry["status"] for entry in checks.values()]
    status = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "pass")
    receipt = {
        "receipt_type": "x_native_diagnosis",
        "created_at": utc_iso(),
        "status": status,
        "request": raw_text,
        "state": state,
        "checks": checks,
        "execution_allowed": False,
        "apply_allowed": False,
        "repo_write": False,
        "next_safe_step": "Ask X Native for a planner proposal or create a sandbox workspace draft. Repo apply remains locked.",
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
        + "\n".join(f"- {name}: {entry['status'].upper()} - {entry['detail'] if 'detail' in entry else entry['message']}" for name, entry in checks.items())
        + "\n\nProof:\n"
        f"{paths['path']}\n"
        "\nNext safe step:\n"
        "Ask X to propose a repair plan or create a sandbox workspace draft. X Native will stage/preview/draft only; apply is still locked."
    )
    return {"content": content, "diagnosis": receipt}


def planner_response(raw_text: str, *, save_stage: bool) -> dict[str, Any]:
    state = build_state()
    stage_id = str(uuid4()) if save_stage else None
    proposal = build_repair_proposal(raw_text, state, staged=save_stage, stage_id=stage_id)
    if save_stage:
        stage = {
            "receipt_type": "x_native_planner_stage",
            "created_at": utc_iso(),
            "stage_id": stage_id,
            "status": "planner_proposal_staged",
            "source_text": raw_text,
            "planner_proposal": proposal,
            "execution_allowed": False,
            "apply_allowed": False,
            "repo_write": False,
            "next_step": "Preview the staged plan or create a sandbox workspace draft. Repo apply remains locked.",
        }
        paths = write_json(STAGES_DIR, f"planner_stage_{stage_id}", stage, "latest_stage.json")
        proposal["receipt_path"] = paths["path"]
        stage["planner_proposal"] = proposal
        STAGES_DIR.joinpath(Path(paths["path"]).name).write_text(json.dumps(stage, indent=2, sort_keys=True), encoding="utf-8")
        (STAGES_DIR / "latest_stage.json").write_text(json.dumps(stage, indent=2, sort_keys=True), encoding="utf-8")
    content = (
        "X Native Planner v0 proposal.\n\n"
        f"Problem: {proposal['problem_summary']}\n\n"
        f"Probable cause: {proposal['probable_cause']}\n\n"
        f"Proposed fix: {proposal['proposed_fix']}\n\n"
        "Affected files:\n"
        + "\n".join(f"- {path}" for path in proposal["affected_files"])
        + "\n\nValidation commands:\n"
        + "\n".join(f"- {command}" for command in proposal["validation_commands"])
        + "\n\nSafety: execution_allowed=false, apply_allowed=false, repo_write=false"
    )
    return {"content": content, "planner_proposal": proposal}


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


def safe_workspace_path(raw_path: str) -> Path:
    if not raw_path.strip():
        raise ValueError("workspace path is required")
    if re.match(r"^[A-Za-z]:", raw_path):
        raise ValueError("Windows drive prefixes are not allowed")
    candidate = Path(raw_path.replace("\\", "/"))
    if candidate.is_absolute():
        raise ValueError("absolute paths are not allowed")
    if ".." in candidate.parts:
        raise ValueError("path traversal is not allowed")
    resolved = (WORKSPACE_DIR / candidate).resolve()
    workspace_root = WORKSPACE_DIR.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("path outside workspace is not allowed") from exc
    return resolved


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
    lower = raw_text.lower()
    if "diagnose" in lower and not any(word in lower for word in ("propose", "repair", "patch", "production-ready", "production readiness", "next fix", "next repair")):
        decision = {
            "intent": "diagnose",
            "risk": "developer_read",
            "route": "tool",
            "summary": "Inspect X Native runtime state and write proof receipt.",
        }
        result = diagnose_response(raw_text)
        return {"status": "completed", "decision": decision, **result}
    if planner_keywords(raw_text):
        decision = {
            "intent": "planner_proposal",
            "risk": "developer_read",
            "route": "planner",
            "summary": "Generate a sandbox-only X Native repair proposal.",
        }
        result = planner_response(raw_text, save_stage=should_stage_plan(raw_text))
        return {"status": "staged" if result["planner_proposal"].get("staged") else "completed", "decision": decision, **result}
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


@app.post("/x-native/workspace/draft")
def x_native_workspace_draft(payload: WorkspaceDraftRequest) -> dict[str, Any]:
    try:
        target = safe_workspace_path(payload.path)
    except ValueError as exc:
        return {
            "status": "rejected",
            "error": str(exc),
            "workspace_path": str(WORKSPACE_DIR),
            "repo_write": False,
            "apply_allowed": False,
            "execution_allowed": False,
            "promoted_to_repo": False,
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.content, encoding="utf-8")
    receipt = {
        "receipt_type": "x_native_workspace_draft",
        "created_at": utc_iso(),
        "workspace_file": str(target),
        "relative_path": str(target.relative_to(WORKSPACE_DIR.resolve())),
        "stage_id": payload.stage_id,
        "plan": payload.plan,
        "repo_write": False,
        "apply_allowed": False,
        "execution_allowed": False,
        "promoted_to_repo": False,
    }
    paths = write_json(RECEIPTS_DIR, "workspace_draft", receipt, "latest_workspace_draft_receipt.json")
    return {
        "status": "draft_created",
        "workspace_file": str(target),
        "workspace_path": str(WORKSPACE_DIR),
        "receipt_path": paths["path"],
        "latest_receipt_path": paths.get("latest_path"),
        "repo_write": False,
        "apply_allowed": False,
        "execution_allowed": False,
        "promoted_to_repo": False,
    }


@app.get("/x-native/workspace")
def x_native_workspace() -> dict[str, Any]:
    files = []
    for path in sorted(WORKSPACE_DIR.rglob("*")):
        if path.is_file():
            files.append({
                "path": str(path),
                "relative_path": str(path.relative_to(WORKSPACE_DIR)),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            })
    return {
        "status": "completed",
        "workspace_path": str(WORKSPACE_DIR),
        "files": files,
        "repo_write": False,
        "apply_allowed": False,
        "execution_allowed": False,
        "promoted_to_repo": False,
    }
