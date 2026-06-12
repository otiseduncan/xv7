from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import subprocess

from core.operator.schema import OperatorActionResult, OperatorSafety


GIT_COMMAND_TIMEOUT_SECONDS = 8
KEY_FILE_CANDIDATES = (
    "README.md",
    "docker-compose.yml",
    "core/main.py",
    "public/app.js",
    "public/index.html",
    "package.json",
    "docs/XODUZ_ROADMAP.md",
    "docs/CODE_LANE_INDEX.md",
)
EXCLUDED_TOP_LEVEL = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
}


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=127,
            stdout="",
            stderr="git executable not found",
        )
    except subprocess.TimeoutExpired:
        command = "git " + " ".join(args)
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=124,
            stdout="",
            stderr=(
                "limitation: workspace map git check timed out after "
                f"{GIT_COMMAND_TIMEOUT_SECONDS}s while running {command}"
            ),
        )


def _read_text(path: Path, *, limit: int = 20_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _top_level_folders(repo_root: Path) -> list[str]:
    folders = []
    for path in sorted(repo_root.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_dir() or path.name in EXCLUDED_TOP_LEVEL:
            continue
        folders.append(path.name)
    return folders


def _parse_dirty_files(status_stdout: str) -> list[str]:
    dirty_files: list[str] = []
    for line in status_stdout.splitlines():
        if not line.strip():
            continue
        path_part = line[3:] if len(line) > 3 else line.strip()
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        dirty_files.append(path_part.strip())
    return dirty_files


def _detect_stack(repo_root: Path) -> dict[str, bool]:
    core_main = repo_root / "core" / "main.py"
    core_main_text = _read_text(core_main)
    package_json = repo_root / "package.json"
    return {
        "python": (repo_root / "core").exists()
        or (repo_root / "pyproject.toml").exists(),
        "fastapi": "FastAPI" in core_main_text or "fastapi" in core_main_text.lower(),
        "frontend_static": (repo_root / "public" / "index.html").exists()
        or (repo_root / "public" / "app.js").exists(),
        "node": package_json.exists(),
        "docker": (repo_root / "docker-compose.yml").exists()
        or (repo_root / "compose.yml").exists(),
        "tests": (repo_root / "tests").exists(),
        "docs": (repo_root / "docs").exists(),
    }


def _test_commands(repo_root: Path, stack: dict[str, bool]) -> list[str]:
    commands: list[str] = []
    if stack.get("python") and stack.get("tests"):
        commands.append("python -m pytest tests/ -v --tb=short --asyncio-mode=auto")
    if stack.get("python"):
        commands.append("python -m ruff check core/ tests/")
        commands.append("python -m ruff format --check core/ tests/")
        commands.append("python -m mypy core/ --ignore-missing-imports")
    if stack.get("node") and (repo_root / "public" / "app.test.js").exists():
        commands.append("npm test -- public/app.test.js")
    if stack.get("docker"):
        commands.append("docker compose build")
    return commands


def workspace_map(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    repo_root = repo_root.resolve()
    limitations: list[str] = []

    if not repo_root.exists() or not repo_root.is_dir():
        completed = datetime.now(UTC)
        return OperatorActionResult(
            action_id=action_id,
            action_name="workspace_map",
            status="failed",
            started_at=started,
            completed_at=completed,
            command_or_operation="read-only workspace map",
            target=str(repo_root),
            stdout_summary="",
            stderr_summary="Workspace root does not exist or is not a directory.",
            exit_code=None,
            data={"repo_root": str(repo_root), "limitations": ["invalid repo root"]},
            safety=OperatorSafety(allowed=True),
            receipt_label=f"workspace_map {action_id}",
        )

    branch_proc = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_proc = _run_git(repo_root, ["status", "--porcelain"])

    branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "unknown"
    if branch_proc.returncode != 0:
        limitations.append(branch_proc.stderr.strip() or "git branch unavailable")

    dirty_files = (
        _parse_dirty_files(status_proc.stdout) if status_proc.returncode == 0 else []
    )
    if status_proc.returncode != 0:
        limitations.append(status_proc.stderr.strip() or "git status unavailable")

    folders = _top_level_folders(repo_root)
    stack = _detect_stack(repo_root)
    stack_labels = [name for name, enabled in stack.items() if enabled]
    key_files = [
        {"path": path, "exists": (repo_root / path).exists()}
        for path in KEY_FILE_CANDIDATES
    ]
    present_key_files = [item["path"] for item in key_files if item["exists"]]
    commands = _test_commands(repo_root, stack)
    completed = datetime.now(UTC)

    return OperatorActionResult(
        action_id=action_id,
        action_name="workspace_map",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation=(
            "read-only workspace map; git rev-parse --abbrev-ref HEAD; "
            "git status --porcelain; filesystem top-level scan"
        ),
        target=str(repo_root),
        stdout_summary=(
            f"branch={branch}; dirty_files={len(dirty_files)}; "
            f"stack={','.join(stack_labels) or 'unknown'}; "
            f"key_files={len(present_key_files)}/{len(key_files)}"
        ),
        stderr_summary="; ".join(limitations),
        exit_code=0,
        data={
            "repo_root": str(repo_root),
            "branch": branch,
            "dirty_files": dirty_files[:50],
            "dirty_file_count": len(dirty_files),
            "top_level_folders": folders[:50],
            "detected_stack": stack,
            "detected_stack_labels": stack_labels,
            "key_files": key_files,
            "present_key_files": present_key_files,
            "test_commands": commands,
            "limitations": limitations,
        },
        safety=OperatorSafety(allowed=True),
        receipt_label=f"workspace_map {action_id}",
    )
