from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re

from core.operator.actions.workspace import workspace_map
from core.operator.schema import OperatorActionResult, OperatorSafety


RISK_HIGH_KEYWORDS = (
    "delete",
    "remove",
    "wipe",
    "reset",
    "force",
    "credential",
    "secret",
    "auth",
    "production",
    "deploy",
    "docker",
    "runtime",
)
RISK_LOW_KEYWORDS = ("docs", "document", "readme", "test", "lint", "format")
MUTATION_KEYWORDS = (
    "add",
    "build",
    "change",
    "create",
    "edit",
    "fix",
    "implement",
    "make",
    "patch",
    "refactor",
    "update",
    "wire",
    "write",
)


CODE_LANE_FILES: dict[str, list[str]] = {
    "code-01": [
        "core/operator/actions/workspace.py",
        "core/operator/registry.py",
        "core/operator/actions/__init__.py",
        "tests/test_operator_workspace_map.py",
        "tests/test_operator_registry.py",
        "docs/CODE_01_WORKSPACE_MAP_PROMPT.md",
    ],
    "code-02": [
        "core/operator/actions/patch_plan.py",
        "core/operator/registry.py",
        "core/operator/actions/__init__.py",
        "tests/test_operator_patch_plan.py",
        "tests/test_operator_registry.py",
        "docs/CODE_02_PATCH_PLANNER_PROMPT.md",
    ],
    "code-03": [
        "core/operator/actions/apply_patch.py",
        "core/operator/registry.py",
        "tests/test_operator_apply_patch.py",
        "docs/CODE_03_APPROVED_PATCH_APPLY_PROMPT.md",
    ],
    "code-04": [
        "core/operator/actions/test_runner.py",
        "core/operator/registry.py",
        "tests/test_operator_test_runner.py",
        "docs/CODE_04_TEST_RUNNER_PROMPT.md",
    ],
    "code-05": [
        "core/operator/actions/diff_report.py",
        "core/operator/registry.py",
        "tests/test_operator_diff_report.py",
        "docs/CODE_05_DIFF_REPORT_PROMPT.md",
    ],
}


KEYWORD_FILE_HINTS: tuple[tuple[tuple[str, ...], list[str]], ...] = (
    (("workspace", "repo map", "where are we"), CODE_LANE_FILES["code-01"]),
    (("plan", "planner", "patch plan", "code-02"), CODE_LANE_FILES["code-02"]),
    (("apply", "patch", "approval", "code-03"), CODE_LANE_FILES["code-03"]),
    (("test runner", "run tests", "validation", "code-04"), CODE_LANE_FILES["code-04"]),
    (("diff", "report", "summary", "code-05"), CODE_LANE_FILES["code-05"]),
    (
        ("commit", "git commit", "code-06"),
        [
            "core/operator/actions/commit_helper.py",
            "core/operator/registry.py",
            "tests/test_operator_commit_helper.py",
            "docs/CODE_06_COMMIT_HELPER_PROMPT.md",
        ],
    ),
    (
        ("app builder", "scaffold", "template", "generated app"),
        [
            "core/operator/actions/app_builder.py",
            "core/operator/app_templates.py",
            "tests/test_operator_app_builder.py",
            "docs/CODE_07_APP_BUILDER_MODE_PROMPT.md",
            "docs/CODE_15_APP_TEMPLATE_REGISTRY_PROMPT.md",
        ],
    ),
    (
        ("brain", "memory", "workflow learning", "records"),
        [
            "core/brain/manager.py",
            "core/brain/records.py",
            "tests/test_runtime_brain_records_api.py",
            "docs/CODE_12_MEMORY_TO_WORKFLOW_PROMOTION_PROMPT.md",
        ],
    ),
    (
        ("ui", "button", "panel", "command center", "frontend"),
        [
            "public/app.js",
            "public/index.html",
            "public/styles.css",
            "public/app.test.js",
            "docs/CODE_13_OPERATOR_COMMAND_CENTER_PROMPT.md",
        ],
    ),
    (
        ("bridge", "local bridge", "host scan"),
        [
            "local_bridge/app.py",
            "core/operator/actions/host_scan.py",
            "tests/test_operator_readonly_actions.py",
            "docs/CODE_14_LOCAL_BRIDGE_HEALTH_PROMPT.md",
        ],
    ),
)


DEFAULT_OPERATOR_FILES = [
    "core/operator/registry.py",
    "core/operator/actions/__init__.py",
    "tests/test_operator_registry.py",
]


def _normalize_goal(goal: str) -> str:
    return re.sub(r"\s+", " ", goal.strip())


def _workspace_data(action_id: str, repo_root: Path, workspace: dict | None) -> dict:
    if workspace is not None:
        return workspace
    result = workspace_map(action_id=f"{action_id}-workspace", repo_root=repo_root)
    return result.data


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _likely_files(goal: str, workspace: dict) -> list[str]:
    lowered = goal.lower()
    likely: list[str] = []
    for code_id, files in CODE_LANE_FILES.items():
        if code_id in lowered:
            likely.extend(files)
    for keywords, files in KEYWORD_FILE_HINTS:
        if any(keyword in lowered for keyword in keywords):
            likely.extend(files)
    if not likely:
        likely.extend(DEFAULT_OPERATOR_FILES)

    present = {
        item.get("path")
        for item in workspace.get("key_files", [])
        if isinstance(item, dict) and item.get("exists")
    }
    if "docs/CODE_LANE_INDEX.md" in present:
        likely.append("docs/CODE_LANE_INDEX.md")
    return _dedupe(likely)


def _mutation_required(goal: str) -> bool:
    lowered = goal.lower()
    return any(keyword in lowered for keyword in MUTATION_KEYWORDS)


def _risk(goal: str, files: list[str], mutation_required: bool) -> tuple[str, str]:
    lowered = goal.lower()
    if any(keyword in lowered for keyword in RISK_HIGH_KEYWORDS):
        return (
            "high",
            "Goal mentions high-risk runtime, destructive, credential, deployment, or Docker behavior.",
        )
    if any(path.startswith(("core/", "local_bridge/")) for path in files):
        return (
            "medium",
            "Plan likely touches runtime/operator code and requires targeted tests.",
        )
    if not mutation_required or any(
        keyword in lowered for keyword in RISK_LOW_KEYWORDS
    ):
        return "low", "Plan is read-only or docs/test focused."
    return "medium", "Plan requires repository changes and approval before mutation."


def _proposed_changes(
    goal: str, files: list[str], mutation_required: bool
) -> list[str]:
    lowered = goal.lower()
    changes: list[str] = []
    if "code-02" in lowered or "patch plan" in lowered or "planner" in lowered:
        changes.extend(
            [
                "Add a read-only patch_plan operator action that turns a user goal into a structured implementation plan.",
                "Register and export patch_plan without allowing file mutations.",
                "Add tests for likely files, risk, approval requirement, registry exposure, and read-only safety.",
            ]
        )
    elif "workspace" in lowered:
        changes.extend(
            [
                "Inspect existing workspace map behavior before changing it.",
                "Adjust workspace map output only after confirming expected files and tests.",
            ]
        )
    elif "app builder" in lowered:
        changes.extend(
            [
                "Define the app-builder entry point and supported template boundaries.",
                "Add tests before any scaffold-writing action is allowed.",
            ]
        )
    else:
        changes.extend(
            [
                "Inspect the likely files before editing.",
                "Prepare the smallest safe patch for the requested behavior.",
                "Run targeted tests first, then the broader backend/frontend gate if needed.",
            ]
        )

    if not mutation_required:
        changes.append(
            "Keep this as plan-only unless the operator explicitly approves a later mutation step."
        )
    if "docs/CODE_LANE_INDEX.md" in files:
        changes.append(
            "Update CODE lane index/status only after implementation is verified."
        )
    return changes


def _tests_to_run(files: list[str], workspace: dict) -> list[str]:
    tests: list[str] = []
    if "tests/test_operator_patch_plan.py" in files:
        tests.append(
            "python -m pytest tests/test_operator_patch_plan.py tests/test_operator_registry.py -v --tb=short --asyncio-mode=auto"
        )
    elif any(path.startswith("tests/") for path in files):
        targets = " ".join(path for path in files if path.startswith("tests/"))
        tests.append(f"python -m pytest {targets} -v --tb=short --asyncio-mode=auto")

    if any(path.startswith("core/") for path in files):
        tests.extend(
            [
                "python -m ruff check core/ tests/",
                "python -m ruff format --check core/ tests/",
            ]
        )
    if any(path.startswith("public/") for path in files):
        tests.append("npm test -- public/app.test.js")

    for command in workspace.get("test_commands", []):
        if command not in tests and len(tests) < 6:
            tests.append(command)
    return tests


def _questions(goal: str, files: list[str]) -> list[str]:
    if not goal:
        return [
            "What should be planned? Provide the feature, bug, or CODE lane target."
        ]
    if len(goal.split()) <= 2 and not any(
        goal.lower().startswith(f"code-{n:02d}") for n in range(1, 22)
    ):
        return ["The goal is short. Confirm the desired behavior before patching."]
    if not files:
        return [
            "No likely files were identified. Run workspace_map and inspect the repo first."
        ]
    return []


def patch_plan(
    *,
    action_id: str,
    repo_root: Path,
    goal: str,
    workspace: dict | None = None,
) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    normalized_goal = _normalize_goal(goal)
    workspace_info = _workspace_data(action_id, repo_root, workspace)
    files = _likely_files(normalized_goal, workspace_info)
    mutation = _mutation_required(normalized_goal)
    risk, risk_reason = _risk(normalized_goal, files, mutation)
    tests = _tests_to_run(files, workspace_info)
    questions = _questions(normalized_goal, files)
    completed = datetime.now(UTC)

    return OperatorActionResult(
        action_id=action_id,
        action_name="patch_plan",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="read-only patch planning; no files written",
        target=str(repo_root),
        stdout_summary=(
            f"risk={risk}; likely_files={len(files)}; tests={len(tests)}; "
            f"approval_required={mutation}"
        ),
        stderr_summary="",
        exit_code=0,
        data={
            "goal": normalized_goal,
            "mode": "plan_only",
            "mutation_required": mutation,
            "approval_required": mutation,
            "approval_reason": (
                "Repository mutation must be explicitly approved before apply_patch."
                if mutation
                else "No mutation requested by this planning action."
            ),
            "risk": risk,
            "risk_reason": risk_reason,
            "likely_files": files,
            "proposed_changes": _proposed_changes(normalized_goal, files, mutation),
            "tests_to_run": tests,
            "questions": questions,
            "workspace_summary": {
                "branch": workspace_info.get("branch", "unknown"),
                "dirty_file_count": workspace_info.get("dirty_file_count", 0),
                "detected_stack_labels": workspace_info.get(
                    "detected_stack_labels", []
                ),
                "limitations": workspace_info.get("limitations", []),
            },
        },
        safety=OperatorSafety(allowed=True),
        receipt_label=f"patch_plan {action_id}",
    )
