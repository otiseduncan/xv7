from __future__ import annotations

from typing import Any
from uuid import uuid4

from receipts import PROMPTS_DIR, locked_flags, read_latest_json, utc_iso, write_json
from review_bundles import get_review_bundle, latest_review_bundle


def create_prompt_from_latest() -> dict[str, Any]:
    latest = latest_review_bundle().get("review_bundle")
    if not latest:
        return {"status": "empty", "message": "No review bundle exists yet.", **locked_flags()}
    return create_prompt_from_bundle(latest["bundle_id"])


def create_prompt_from_bundle(bundle_id: str) -> dict[str, Any]:
    bundle = get_review_bundle(bundle_id).get("review_bundle")
    if not bundle:
        return {"status": "not_found", "bundle_id": bundle_id, **locked_flags()}
    prompt = build_prompt(bundle)
    paths = write_json(PROMPTS_DIR, f"prompt_{prompt['prompt_id']}", prompt, "latest_prompt.json")
    prompt.update({"receipt_path": paths["path"], "latest_receipt_path": paths.get("latest_path")})
    write_json(PROMPTS_DIR, f"prompt_{prompt['prompt_id']}", prompt, "latest_prompt.json")
    return {"status": "prompt_created", "prompt": prompt, **locked_flags()}


def latest_prompt() -> dict[str, Any]:
    prompt = read_latest_json(PROMPTS_DIR, "latest_prompt.json")
    return {"status": "completed" if prompt else "empty", "prompt": prompt, **locked_flags()}


def list_prompts() -> dict[str, Any]:
    prompts = []
    for path in sorted(PROMPTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name == "latest_prompt.json":
            continue
        prompt = read_latest_json(path.parent, path.name)
        if prompt:
            prompts.append({
                "prompt_id": prompt.get("prompt_id"),
                "source_bundle_id": prompt.get("source_bundle_id"),
                "created_at": prompt.get("created_at"),
                "receipt_path": str(path),
            })
    return {"status": "completed", "prompts": prompts, **locked_flags()}


def build_prompt(bundle: dict[str, Any]) -> dict[str, Any]:
    proposal = bundle.get("planner_proposal", {})
    prompt_id = str(uuid4())
    expected_files = bundle.get("intended_files") or proposal.get("affected_files", [])
    validation = bundle.get("validation_checklist") or proposal.get("validation_commands", [])
    return {
        "kind": "x_native_codex_prompt_v0",
        "created_at": utc_iso(),
        "prompt_id": prompt_id,
        "source_bundle_id": bundle.get("bundle_id"),
        "codex_prompt": render_codex_prompt(bundle, expected_files, validation),
        "guardrails_summary": guardrails_summary(),
        "expected_files": expected_files,
        "expected_validation": validation,
        "stop_conditions": stop_conditions(),
        "human_authorization_required": True,
        **locked_flags(),
    }


def render_codex_prompt(bundle: dict[str, Any], expected_files: list[str], validation: list[str]) -> str:
    proposal = bundle.get("planner_proposal", {})
    files = "\n".join(f"- {path}" for path in expected_files) or "- No files declared"
    checks = "\n".join(f"- {item}" for item in validation) or "- Report validation not run"
    return (
        "You are working in the XV7 repo on branch x-native-baseline.\n\n"
        "MISSION: Implement only the X Native repair described by this review bundle.\n\n"
        f"SOURCE REVIEW BUNDLE: {bundle.get('bundle_id')}\n"
        f"TITLE: {proposal.get('title')}\n\n"
        f"PROBLEM:\n{proposal.get('problem_summary')}\n\n"
        f"PROPOSED FIX:\n{proposal.get('proposed_fix')}\n\n"
        f"EXPECTED FILES:\n{files}\n\n"
        f"VALIDATION:\n{checks}\n\n"
        "HARD GUARDRAILS:\n"
        "- Touch only X Native allowed paths.\n"
        "- Do not use legacy /sessions routes or old XV7 core imports.\n"
        "- Do not add repo apply endpoints or prompt shell execution.\n"
        "- Keep execution_allowed=false, apply_allowed=false, repo_write=false.\n\n"
        "FINAL REPORT REQUIRED:\n"
        "- branch\n- commit hash\n- files changed\n- validation results\n"
        "- denied paths touched yes/no\n- legacy routes used yes/no\n- remaining dirty files\n"
    )


def guardrails_summary() -> list[str]:
    return [
        "Review-only prompt material.",
        "Human authorization remains external.",
        "No repo apply, shell execution, or sandbox promotion is allowed.",
        "Legacy XV7 session/core routes remain forbidden.",
    ]


def stop_conditions() -> list[str]:
    return [
        "Stop if a denied path must be edited.",
        "Stop if legacy /sessions routing or old core imports appear necessary.",
        "Stop if an apply/write path to repo files would be created.",
        "Stop if validation cannot run without changing legacy code.",
    ]
