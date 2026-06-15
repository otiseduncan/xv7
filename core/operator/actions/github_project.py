from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
import subprocess
from typing import Any

from core.brain.sandbox_writer import SandboxWriteManager
from core.operator.schema import OperatorActionResult, OperatorSafety


def _command_text(args: list[str]) -> str:
    return " ".join(args)


def _run_command(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=args,
            returncode=127,
            stdout="",
            stderr=f"command not found: {args[0]}",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout="",
            stderr=f"command timed out: {_command_text(args)}",
        )


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _extract_commit_sha(stdout_text: str) -> str:
    match = re.search(r"\[.+\s([0-9a-f]{7,40})\]", str(stdout_text or ""))
    return match.group(1) if match else ""


def _default_file_content(path_text: str, project_name: str) -> str:
    normalized = path_text.replace("\\", "/").lower()
    if normalized == "index.html":
        return (
            "<!doctype html>\n"
            '<html lang="en">\n'
            "  <head>\n"
            '    <meta charset="UTF-8" />\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
            "    <title>EarthX GitHub Proof</title>\n"
            '    <link rel="stylesheet" href="assets/site.css" />\n'
            "  </head>\n"
            "  <body>\n"
            '    <main class="hero">\n'
            f"      <h1>{project_name}</h1>\n"
            "      <p>Real sandbox build and GitHub push proof.</p>\n"
            "    </main>\n"
            '    <script src="assets/app.js"></script>\n'
            "  </body>\n"
            "</html>\n"
        )
    if normalized == "assets/site.css":
        return (
            "body {\n"
            "  margin: 0;\n"
            "  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;\n"
            "  background: #04060d;\n"
            "  color: #eaf6ff;\n"
            "}\n"
            ".hero {\n"
            "  min-height: 100vh;\n"
            "  display: grid;\n"
            "  place-content: center;\n"
            "  gap: 0.6rem;\n"
            "  text-align: center;\n"
            "}\n"
        )
    if normalized == "assets/app.js":
        return "window.__earthxGithubProof = 'ready';\n"
    if normalized == "readme.md":
        return (
            f"# {project_name}\n\n"
            "Sandbox-built GitHub proof project created by Operator workflow.\n"
        )
    return "\n"


def _result(
    *,
    action_id: str,
    status: str,
    started_at: datetime,
    project_path: Path,
    stdout_summary: str,
    stderr_summary: str,
    exit_code: int | None,
    data: dict[str, Any],
) -> OperatorActionResult:
    completed_at = datetime.now(UTC)
    return OperatorActionResult(
        action_id=action_id,
        action_name="operator_github_proof_project",
        mode="operator",
        status=status,  # type: ignore[arg-type]
        started_at=started_at,
        completed_at=completed_at,
        command_or_operation="sandbox project create + git init/commit + optional github create/push",
        target=str(project_path),
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        exit_code=exit_code,
        data=data,
        safety=OperatorSafety(
            allowed=status != "denied",
            read_only=False,
            mutates_files=True,
            mutates_git=True,
            requires_approval=False,
            denial_reason=stderr_summary if status == "denied" else None,
        ),
        receipt_label=f"operator_github_proof_project {action_id}",
    )


def operator_github_proof_project(
    *,
    action_id: str,
    repo_root: Path,
    request: dict[str, Any],
) -> OperatorActionResult:
    started_at = datetime.now(UTC)
    sandbox_root = SandboxWriteManager.sandbox_root().resolve()

    project_name = str(request.get("project_name") or "github-proof-project").strip()
    requested_path = str(request.get("project_path") or "").strip()
    if requested_path:
        project_path = Path(requested_path).resolve()
    else:
        project_path = (sandbox_root / project_name).resolve()

    if not _inside(sandbox_root, project_path):
        return _result(
            action_id=action_id,
            status="denied",
            started_at=started_at,
            project_path=project_path,
            stdout_summary="",
            stderr_summary=(
                "Target path is outside the approved sandbox root. "
                f"sandbox_root={sandbox_root}; target={project_path}"
            ),
            exit_code=None,
            data={
                "project_path": str(project_path),
                "sandbox_root": str(sandbox_root),
                "changed_files": [],
                "commands": [],
                "commit_created": False,
                "push_performed": False,
            },
        )

    files = request.get("requested_files")
    if not isinstance(files, list) or not files:
        files = ["index.html", "assets/site.css", "assets/app.js", "README.md"]

    changed_files: list[str] = []
    for relative in [str(item).replace("\\", "/") for item in files]:
        target = (project_path / relative).resolve()
        if not _inside(project_path, target):
            return _result(
                action_id=action_id,
                status="denied",
                started_at=started_at,
                project_path=project_path,
                stdout_summary="",
                stderr_summary=f"Blocked unsafe file target: {relative}",
                exit_code=None,
                data={
                    "project_path": str(project_path),
                    "sandbox_root": str(sandbox_root),
                    "changed_files": changed_files,
                    "commands": [],
                    "commit_created": False,
                    "push_performed": False,
                },
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _default_file_content(relative, project_name), encoding="utf-8"
        )
        changed_files.append(target.relative_to(project_path).as_posix())

    commands: list[str] = []

    def run_or_fail(
        command: list[str],
    ) -> tuple[bool, subprocess.CompletedProcess[str]]:
        commands.append(_command_text(command))
        proc = _run_command(project_path, command)
        return proc.returncode == 0, proc

    initialize_git = bool(request.get("initialize_git", True))
    if initialize_git:
        ok_init, proc_init = run_or_fail(["git", "init", "-b", "main"])
        if not ok_init:
            ok_fallback, proc_fallback = run_or_fail(["git", "init"])
            if not ok_fallback:
                failed = _command_text(
                    proc_fallback.args
                    if isinstance(proc_fallback.args, list)
                    else ["git", "init"]
                )
                return _result(
                    action_id=action_id,
                    status="failed",
                    started_at=started_at,
                    project_path=project_path,
                    stdout_summary=proc_fallback.stdout[:500],
                    stderr_summary=proc_fallback.stderr[:500],
                    exit_code=proc_fallback.returncode,
                    data={
                        "project_path": str(project_path),
                        "sandbox_root": str(sandbox_root),
                        "changed_files": changed_files,
                        "commands": commands,
                        "failed_command": failed,
                        "commit_created": False,
                        "push_performed": False,
                    },
                )
            run_or_fail(["git", "branch", "-M", "main"])

    ok_add, proc_add = run_or_fail(["git", "add", "."])
    if not ok_add:
        failed = _command_text(
            proc_add.args if isinstance(proc_add.args, list) else ["git", "add", "."]
        )
        return _result(
            action_id=action_id,
            status="failed",
            started_at=started_at,
            project_path=project_path,
            stdout_summary=proc_add.stdout[:500],
            stderr_summary=proc_add.stderr[:500],
            exit_code=proc_add.returncode,
            data={
                "project_path": str(project_path),
                "sandbox_root": str(sandbox_root),
                "changed_files": changed_files,
                "commands": commands,
                "failed_command": failed,
                "commit_created": False,
                "push_performed": False,
            },
        )

    commit_message = str(request.get("commit_message") or "build GitHub proof project")
    ok_commit, proc_commit = run_or_fail(["git", "commit", "-m", commit_message])
    if not ok_commit:
        failed = _command_text(
            proc_commit.args
            if isinstance(proc_commit.args, list)
            else ["git", "commit", "-m", commit_message]
        )
        return _result(
            action_id=action_id,
            status="failed",
            started_at=started_at,
            project_path=project_path,
            stdout_summary=proc_commit.stdout[:500],
            stderr_summary=proc_commit.stderr[:500],
            exit_code=proc_commit.returncode,
            data={
                "project_path": str(project_path),
                "sandbox_root": str(sandbox_root),
                "changed_files": changed_files,
                "commands": commands,
                "failed_command": failed,
                "commit_created": False,
                "push_performed": False,
            },
        )

    commit_sha = _extract_commit_sha(proc_commit.stdout)
    create_repo = bool(request.get("create_github_repo", False))
    push = bool(request.get("push", False))
    pushed = False

    if create_repo:
        repo_name = (
            str(request.get("github_repo_name") or project_name).strip() or project_name
        )
        gh_command = [
            "gh",
            "repo",
            "create",
            repo_name,
            "--source",
            ".",
            "--remote",
            "origin",
            "--public",
        ]
        if push:
            gh_command.append("--push")
        ok_gh, proc_gh = run_or_fail(gh_command)
        if not ok_gh:
            failed = _command_text(
                proc_gh.args if isinstance(proc_gh.args, list) else gh_command
            )
            return _result(
                action_id=action_id,
                status="failed",
                started_at=started_at,
                project_path=project_path,
                stdout_summary=proc_gh.stdout[:500],
                stderr_summary=proc_gh.stderr[:500],
                exit_code=proc_gh.returncode,
                data={
                    "project_path": str(project_path),
                    "sandbox_root": str(sandbox_root),
                    "changed_files": changed_files,
                    "commands": commands,
                    "failed_command": failed,
                    "commit_sha": commit_sha,
                    "commit_created": True,
                    "push_performed": False,
                    "pushed": False,
                },
            )
        pushed = push
    elif push:
        ok_push, proc_push = run_or_fail(["git", "push", "-u", "origin", "main"])
        if not ok_push:
            failed = _command_text(
                proc_push.args
                if isinstance(proc_push.args, list)
                else ["git", "push", "-u", "origin", "main"]
            )
            return _result(
                action_id=action_id,
                status="failed",
                started_at=started_at,
                project_path=project_path,
                stdout_summary=proc_push.stdout[:500],
                stderr_summary=proc_push.stderr[:500],
                exit_code=proc_push.returncode,
                data={
                    "project_path": str(project_path),
                    "sandbox_root": str(sandbox_root),
                    "changed_files": changed_files,
                    "commands": commands,
                    "failed_command": failed,
                    "commit_sha": commit_sha,
                    "commit_created": True,
                    "push_performed": False,
                    "pushed": False,
                },
            )
        pushed = True

    return _result(
        action_id=action_id,
        status="success",
        started_at=started_at,
        project_path=project_path,
        stdout_summary=f"created project at {project_path}",
        stderr_summary="",
        exit_code=0,
        data={
            "project_path": str(project_path),
            "sandbox_root": str(sandbox_root),
            "changed_files": changed_files,
            "commands": commands,
            "failed_command": "",
            "commit_sha": commit_sha,
            "commit_created": True,
            "push_performed": pushed,
            "pushed": pushed,
        },
    )
