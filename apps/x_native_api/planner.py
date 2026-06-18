from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def planner_keywords(raw_text: str) -> bool:
    lower = raw_text.lower()
    keywords = (
        "inspect",
        "diagnosis",
        "diagnose",
        "repair",
        "patch",
        "improve",
        "improvement",
        "production readiness",
        "next fix",
        "next repair",
        "propose",
        "stage",
        "plan",
    )
    return any(keyword in lower for keyword in keywords)


def should_stage_plan(raw_text: str) -> bool:
    lower = raw_text.lower()
    return any(word in lower for word in ("propose", "repair", "patch", "stage", "fix", "write", "create", "improve"))


def build_repair_proposal(
    raw_text: str,
    state: dict[str, Any],
    *,
    staged: bool = False,
    stage_id: str | None = None,
    receipt_path: str | None = None,
) -> dict[str, Any]:
    plan_id = stage_id or str(uuid4())
    branch = state.get("branch") or "unknown"
    dirty_files = state.get("dirty_files") or ""
    git_unavailable = str(dirty_files).startswith("git metadata unavailable") or str(dirty_files).startswith("git status unavailable")
    data_root = state.get("data_root") or "data/x_native"
    affected_files = [
        "apps/x_native_api/planner.py",
        "apps/x_native_api/review_bundles.py",
        "apps/x_native_api/main.py",
        "apps/x_native_ui/public/index.html",
        "docs/X_NATIVE_BASELINE.md",
        "docs/X_NATIVE_PLANNER.md",
        "docs/X_NATIVE_NEXT_HUMAN_DECISIONS.md",
        "data/x_native/workspace",
    ]
    probable_cause = (
        "X Native can diagnose and stage, but the useful planning loop is still shallow: "
        "the UI needs clearer action flow, planner output needs quality structure, "
        "diagnostic wording should treat legacy-core isolation as healthy, and drafts "
        "need a sandbox workspace before any future repo write path exists."
    )
    if dirty_files and not git_unavailable:
        probable_cause += f" Current branch {branch} also has uncommitted source changes, so repo apply must remain locked."
    elif git_unavailable:
        probable_cause += " Git metadata is unavailable inside the container, which is acceptable for runtime planning but not for git-dependent operations."
    return {
        "kind": "x_native_planner_v0",
        "created_at": utc_iso(),
        "request": raw_text,
        "problem_summary": (
            "X Native needs reviewable Planner v1 bundles so Otis can inspect proposed repairs, validation, "
            "rollback, and safety state before any future authority decision."
        ),
        "current_limitation": (
            "Planner v0 can stage a proposal and create sandbox drafts, but it does not yet package the plan "
            "into a review artifact with intended paths, pseudo-diff, validation checklist, rollback checklist, "
            "and explicit human-decision fields."
        ),
        "probable_cause": probable_cause,
        "proposed_next_repair": (
            "Create a sandbox-only review bundle for each production-readiness or repair request, expose it "
            "through API/UI controls, and keep all repo apply/write authority locked."
        ),
        "proposed_fix": (
            "Keep old XV7 isolated, improve diagnostics wording, add structured planner proposals, "
            "surface those proposals in the UI, create sandbox-only workspace drafts under "
            f"{data_root}/workspace, and keep the next milestone focused on review quality before any repo write capability is considered."
        ),
        "affected_files": affected_files,
        "validation_commands": [
            "python -m py_compile apps/x_native_api/main.py apps/x_native_api/planner.py",
            "docker compose -f docker-compose.x-native.yml up -d --build",
            "Invoke-RestMethod http://localhost:3101/health",
            "Invoke-RestMethod http://localhost:3101/x-native/state",
        ],
        "rollback_plan": (
            "Remove the planner module and workspace endpoints, restore apps/x_native_api/main.py "
            "and apps/x_native_ui/public/index.html from git, and delete sandbox-only files under data/x_native/workspace."
        ),
        "risk": "low_to_medium_sandbox_only",
        "stage_id": plan_id if staged else None,
        "receipt_path": receipt_path,
        "staged": staged,
        "execution_allowed": False,
        "apply_allowed": False,
        "repo_write": False,
        "promoted_to_repo": False,
        "sandbox_only": True,
    }
