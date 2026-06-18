from __future__ import annotations

from typing import Any
from uuid import uuid4

from diagnostics import build_state
from planner import build_repair_proposal
from receipts import REVIEW_BUNDLES_DIR, locked_flags, read_latest_json, utc_iso, write_json


def create_review_bundle(
    raw_text: str,
    planner_proposal: dict[str, Any] | None = None,
    stage_id: str | None = None,
) -> dict[str, Any]:
    proposal = planner_proposal or build_repair_proposal(raw_text, build_state(), staged=True, stage_id=stage_id)
    bundle_id = str(uuid4())
    bundle = {
        "kind": "x_native_review_bundle_v0",
        "created_at": utc_iso(),
        "bundle_id": bundle_id,
        "stage_id": proposal.get("stage_id") or stage_id,
        "source_request": raw_text,
        "planner_proposal": proposal,
        "intended_files": proposal.get("affected_files", []),
        "intended_file_paths": proposal.get("affected_files", []),
        "pseudo_diff_or_patch_preview": build_pseudo_diff(proposal),
        "validation_checklist": build_validation_checklist(proposal),
        "rollback_checklist": build_rollback_checklist(proposal),
        "safety_flags": locked_flags(),
        "human_authorization_required": True,
        "human_decision_required": (
            "Decide whether future X Native milestones may add repo-write sandbox promotion. "
            "This bundle does not grant that authority."
        ),
        "recommended_codex_prompt_draft": build_codex_prompt(proposal),
        **locked_flags(),
    }
    paths = write_json(REVIEW_BUNDLES_DIR, f"review_bundle_{bundle_id}", bundle, "latest_review_bundle.json")
    bundle.update({"receipt_path": paths["path"], "latest_receipt_path": paths.get("latest_path")})
    write_json(REVIEW_BUNDLES_DIR, f"review_bundle_{bundle_id}", bundle, "latest_review_bundle.json")
    return {"status": "review_bundle_created", "review_bundle": bundle, **locked_flags()}


def list_review_bundles() -> dict[str, Any]:
    bundles = []
    for path in sorted(REVIEW_BUNDLES_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name == "latest_review_bundle.json":
            continue
        bundle = read_latest_json(path.parent, path.name)
        if bundle:
            bundles.append({
                "bundle_id": bundle.get("bundle_id"),
                "stage_id": bundle.get("stage_id"),
                "receipt_path": str(path),
                "created_at": bundle.get("created_at"),
            })
    return {"status": "completed", "review_bundles": bundles, **locked_flags()}


def latest_review_bundle() -> dict[str, Any]:
    bundle = read_latest_json(REVIEW_BUNDLES_DIR, "latest_review_bundle.json")
    return {"status": "completed" if bundle else "empty", "review_bundle": bundle, **locked_flags()}


def get_review_bundle(bundle_id: str) -> dict[str, Any]:
    for path in REVIEW_BUNDLES_DIR.glob("*.json"):
        if path.name == "latest_review_bundle.json":
            continue
        bundle = read_latest_json(path.parent, path.name)
        if bundle and bundle.get("bundle_id") == bundle_id:
            return {"status": "completed", "review_bundle": bundle, **locked_flags()}
    return {"status": "not_found", "bundle_id": bundle_id, **locked_flags()}


def build_pseudo_diff(proposal: dict[str, Any]) -> str:
    paths = proposal.get("affected_files", [])
    lines = ["# PSEUDO-DIFF ONLY - SANDBOX REVIEW", ""]
    for path in paths:
        lines.extend([
            f"--- {path}",
            f"+++ {path}",
            "+ Review planned X Native improvement here.",
            "+ No repo write, patch apply, or shell execution is authorized.",
            "",
        ])
    return "\n".join(lines)


def build_validation_checklist(proposal: dict[str, Any]) -> list[str]:
    commands = proposal.get("validation_commands", [])
    checklist = [f"Run: {command}" for command in commands]
    checklist.append("Confirm all safety flags remain false.")
    checklist.append("Confirm workspace output remains under data/x_native.")
    return checklist


def build_rollback_checklist(proposal: dict[str, Any]) -> list[str]:
    rollback = proposal.get("rollback_plan", "")
    return [
        rollback or "Restore changed X Native files from git.",
        "Delete sandbox-only workspace files if they are no longer useful.",
        "Rerun the X Native full check.",
    ]


def build_codex_prompt(proposal: dict[str, Any]) -> str:
    files = "\n".join(f"- {path}" for path in proposal.get("affected_files", []))
    checks = "\n".join(f"- {command}" for command in proposal.get("validation_commands", []))
    return (
        "TASK: Review this X Native repair bundle and implement only if explicitly authorized.\n\n"
        f"TITLE:\n{proposal.get('title')}\n\n"
        f"PROBLEM:\n{proposal.get('problem_summary')}\n\n"
        f"CURRENT LIMITATION:\n{proposal.get('current_limitation')}\n\n"
        f"PROPOSED FIX:\n{proposal.get('proposed_fix')}\n\n"
        f"AFFECTED FILES:\n{files}\n\n"
        f"VALIDATION:\n{checks}\n\n"
        "HARD SAFETY:\nDo not add repo apply, prompt shell execution, legacy /sessions routing, or old XV7 core imports.\n"
    )
