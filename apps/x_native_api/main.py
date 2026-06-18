from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from diagnostics import APP_NAME, APP_VERSION, build_state, diagnose_response
from models import AttachContentRequest, NativeMessageRequest, WorkspaceDraftRequest
from planner import build_repair_proposal, planner_keywords, should_stage_plan
from receipts import STAGES_DIR, ensure_data_dirs, locked_flags, utc_iso, write_json
from stages import attach_draft, latest_draft, latest_stage, preview_stage, stage_response
from workspace import create_workspace_draft, list_workspace


ensure_data_dirs()

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def classify(raw_text: str) -> dict[str, Any]:
    lower = raw_text.lower()
    write_words = ("create file", "edit file", "write file", "patch", "repair", "fix", "modify", "change")
    inspect_words = ("diagnose", "inspect", "state", "status", "health", "doctor", "readiness")
    if any(word in lower for word in write_words):
        return {"intent": "repo_change_request", "risk": "developer_write", "route": "stage", "summary": "Stage a requested repair/change without applying it."}
    if any(word in lower for word in inspect_words):
        return {"intent": "diagnose", "risk": "developer_read", "route": "tool", "summary": "Inspect X Native runtime state and write proof receipt."}
    return {"intent": "conversation", "risk": "read_only", "route": "answer", "summary": "Answer without execution."}


def planner_response(raw_text: str, *, save_stage: bool) -> dict[str, Any]:
    state = build_state()
    stage_id = None
    if save_stage:
        from uuid import uuid4

        stage_id = str(uuid4())
    proposal = build_repair_proposal(raw_text, state, staged=save_stage, stage_id=stage_id)
    if save_stage:
        proposal = save_planner_stage(raw_text, stage_id or "", proposal)
    return {"content": render_planner(proposal), "state": state, "planner_proposal": proposal}


def save_planner_stage(raw_text: str, stage_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    stage = {
        "receipt_type": "x_native_planner_stage",
        "created_at": utc_iso(),
        "stage_id": stage_id,
        "status": "planner_proposal_staged",
        "source_text": raw_text,
        "planner_proposal": proposal,
        **locked_flags(),
        "next_step": "Preview the staged plan or create a sandbox workspace draft. Repo apply remains locked.",
    }
    paths = write_json(STAGES_DIR, f"planner_stage_{stage_id}", stage, "latest_stage.json")
    proposal["receipt_path"] = paths["path"]
    stage["planner_proposal"] = proposal
    write_json(STAGES_DIR, f"planner_stage_{stage_id}", stage, "latest_stage.json")
    return proposal


def render_planner(proposal: dict[str, Any]) -> str:
    return (
        "X Native Planner v0 proposal.\n\n"
        f"Problem: {proposal['problem_summary']}\n\n"
        f"Probable cause: {proposal['probable_cause']}\n\n"
        f"Proposed fix: {proposal['proposed_fix']}\n\nAffected files:\n"
        + "\n".join(f"- {path}" for path in proposal["affected_files"])
        + "\n\nValidation commands:\n"
        + "\n".join(f"- {command}" for command in proposal["validation_commands"])
        + "\n\nSafety: execution_allowed=false, apply_allowed=false, repo_write=false"
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "runtime": APP_NAME, "version": APP_VERSION}


@app.get("/x-native/state")
def x_native_state() -> dict[str, Any]:
    from receipts import RECEIPTS_DIR

    state = build_state()
    receipt = {"receipt_type": "x_native_state", "created_at": utc_iso(), "state": state}
    paths = write_json(RECEIPTS_DIR, "state", receipt, "latest_state.json")
    return {"status": "completed", "state": state, "receipt_path": paths["path"]}


@app.post("/x-native/message")
def x_native_message(payload: NativeMessageRequest) -> dict[str, Any]:
    raw_text = payload.raw_text.strip()
    lower = raw_text.lower()
    if _is_direct_diagnosis(lower):
        decision = {"intent": "diagnose", "risk": "developer_read", "route": "tool", "summary": "Inspect X Native runtime state and write proof receipt."}
        return {"status": "completed", "decision": decision, **diagnose_response(raw_text)}
    if planner_keywords(raw_text):
        decision = {"intent": "planner_proposal", "risk": "developer_read", "route": "planner", "summary": "Generate a sandbox-only X Native repair proposal."}
        result = planner_response(raw_text, save_stage=should_stage_plan(raw_text))
        return {"status": "staged" if result["planner_proposal"].get("staged") else "completed", "decision": decision, **result}
    return _classified_response(raw_text)


def _is_direct_diagnosis(lower: str) -> bool:
    repair_words = ("propose", "repair", "patch", "production-ready", "production readiness", "next fix", "next repair")
    return "diagnose" in lower and not any(word in lower for word in repair_words)


def _classified_response(raw_text: str) -> dict[str, Any]:
    decision = classify(raw_text)
    if decision["route"] == "tool":
        return {"status": "completed", "decision": decision, **diagnose_response(raw_text)}
    if decision["route"] == "stage":
        return {"status": "staged", "decision": decision, **stage_response(raw_text, decision)}
    content = "X Native received the message. No action was required. Ask me to diagnose, inspect, or stage a repair."
    return {"status": "answered", "decision": decision, "content": content}


@app.get("/x-native/stages/latest")
def x_native_latest_stage() -> dict[str, Any]:
    return latest_stage()


@app.post("/x-native/stages/{stage_id}/preview")
def x_native_preview(stage_id: str) -> dict[str, Any]:
    return preview_stage(stage_id)


@app.post("/x-native/stages/{stage_id}/draft")
def x_native_draft(stage_id: str, payload: AttachContentRequest) -> dict[str, Any]:
    return attach_draft(stage_id, payload.content)


@app.get("/x-native/drafts/latest")
def x_native_latest_draft() -> dict[str, Any]:
    return latest_draft()


@app.post("/x-native/workspace/draft")
def x_native_workspace_draft(payload: WorkspaceDraftRequest) -> dict[str, Any]:
    return create_workspace_draft(payload.path, payload.content, payload.stage_id, payload.plan)


@app.get("/x-native/workspace")
def x_native_workspace() -> dict[str, Any]:
    return list_workspace()
