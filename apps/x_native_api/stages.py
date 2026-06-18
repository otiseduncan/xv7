from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from receipts import STAGES_DIR, locked_flags, read_latest_json, utc_iso, write_json


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
        "suggested_path": f"data/x_native/workspace/{Path(suggested_path).name}",
        "preview_ready": False,
        **locked_flags(),
        "next_step": "Preview this stage or create a sandbox workspace draft. Apply remains locked.",
    }
    paths = write_json(STAGES_DIR, f"stage_{stage_id}", stage, "latest_stage.json")
    stage.update({"stage_path": paths["path"], "latest_stage_path": paths.get("latest_path")})
    return {"content": render_stage(stage, paths["path"]), "stage": stage}


def latest_stage() -> dict[str, Any]:
    stage = read_latest_json(STAGES_DIR, "latest_stage.json")
    return {"status": "completed" if stage else "empty", "stage": stage, **locked_flags()}


def preview_stage(stage_id: str) -> dict[str, Any]:
    stage = read_latest_json(STAGES_DIR, "latest_stage.json")
    if not stage or stage.get("stage_id") != stage_id:
        return {"status": "not_found", "stage_id": stage_id, **locked_flags()}
    planner_proposal = stage.get("planner_proposal") if isinstance(stage.get("planner_proposal"), dict) else None
    preview = {
        "kind": "x_native_preview_v0",
        "stage_id": stage_id,
        "source_text": stage.get("source_text"),
        "suggested_path": stage.get("suggested_path"),
        "planner_proposal": planner_proposal,
        "preview_only": True,
        "is_executor_ready": False,
        **locked_flags(),
        "rendered_preview": render_preview(stage_id, stage, planner_proposal),
    }
    stage.update({"status": "preview_ready", "preview_ready": True, "preview": preview})
    paths = write_json(STAGES_DIR, f"preview_{stage_id}", stage, "latest_stage.json")
    return {"status": "preview_ready", "stage_id": stage_id, "preview": preview, "receipt_path": paths["path"], **locked_flags()}


def attach_draft(stage_id: str, content: str) -> dict[str, Any]:
    stage = read_latest_json(STAGES_DIR, "latest_stage.json")
    if not stage or stage.get("stage_id") != stage_id:
        return {"status": "not_found", "stage_id": stage_id, **locked_flags()}
    draft = {
        "kind": "x_native_draft_v0",
        "created_at": utc_iso(),
        "stage_id": stage_id,
        "source_text": stage.get("source_text"),
        "path": stage.get("suggested_path"),
        "content": content,
        "draft_only": True,
        **locked_flags(),
        "rendered_draft": f"X NATIVE DRAFT ONLY\n\nStage ID: {stage_id}\nPath: {stage.get('suggested_path')}\nApply is locked.",
    }
    from receipts import DRAFTS_DIR, RECEIPTS_DIR

    draft_paths = write_json(DRAFTS_DIR, f"draft_{stage_id}", draft, "latest_draft.json")
    receipt = {"receipt_type": "x_native_draft", "created_at": utc_iso(), "draft": draft, "paths": draft_paths}
    receipt_paths = write_json(RECEIPTS_DIR, f"draft_{stage_id}", receipt, "latest_draft_receipt.json")
    stage.update({"status": "draft_ready", "draft_ready": True, "draft_path": draft_paths["path"]})
    write_json(STAGES_DIR, f"draft_stage_{stage_id}", stage, "latest_stage.json")
    return {"status": "draft_ready", "draft": draft, "draft_path": draft_paths["path"], "receipt_path": receipt_paths["path"], **locked_flags()}


def latest_draft() -> dict[str, Any]:
    from receipts import DRAFTS_DIR

    draft = read_latest_json(DRAFTS_DIR, "latest_draft.json")
    return {"status": "completed" if draft else "empty", "draft": draft, **locked_flags()}


def render_stage(stage: dict[str, Any], path: str) -> str:
    return (
        "X Native staged the request.\n\n"
        f"Stage ID: {stage['stage_id']}\nIntent: {stage['intent']}\nRisk: {stage['risk']}\n"
        f"Suggested path: {stage['suggested_path']}\nExecution allowed: False\nApply allowed: False\nRepo write: False\n\n"
        f"Proof: {path}\n\nNext safe step: Preview this stage in the X Native UI."
    )


def render_preview(stage_id: str, stage: dict[str, Any], proposal: dict[str, Any] | None) -> str:
    if proposal:
        return f"X NATIVE PLANNER PREVIEW ONLY\n\nStage ID: {stage_id}\nProblem: {proposal.get('problem_summary')}\n\nProposed fix: {proposal.get('proposed_fix')}\n\nNo apply path is enabled."
    return f"X NATIVE PREVIEW ONLY\n\nStage ID: {stage_id}\nSource request: {stage.get('source_text')}\nSuggested path: {stage.get('suggested_path')}\n\nNo apply path is enabled."
