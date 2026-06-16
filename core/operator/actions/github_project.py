from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable
from typing import Any

import yaml

from core.brain.sandbox_writer import SandboxWriteManager
from core.operator.schema import OperatorActionResult, OperatorSafety


DEFAULT_GITHUB_PUBLISH_PROFILE: dict[str, str] = {
    "github_owner": "otiseduncan",
    "git_user_name": "Otis Duncan",
    "git_user_email": "otiseduncan@gmail.com",
    "sandbox_root_host": "X:\\xoduz-sandbox",
    "sandbox_root_container": "/app/generated-sites",
    "proof_repo_pattern": "xv7-sandbox-export-proof-YYYYMMDD",
    "proof_repo_url": "https://github.com/otiseduncan/xv7-sandbox-export-proof-20260614",
}


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


def _git_repo_exists(project_path: Path) -> bool:
    probe = _run_command(project_path, ["git", "rev-parse", "--is-inside-work-tree"])
    return probe.returncode == 0


def _extract_origin_url(remotes: list[str]) -> str:
    for line in remotes:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "origin":
            return parts[1].strip()
    return ""


def _profile_store_path() -> Path:
    configured = str(os.getenv("XV7_GITHUB_PUBLISH_PROFILE_PATH", "")).strip()
    if configured:
        return Path(configured).expanduser()
    return Path("/app/data/memory/github_publish_profile.json")


def _system_config_candidates() -> list[Path]:
    return [
        Path("/app/config/system.yml"),
        Path(__file__).resolve().parents[3] / "config" / "system.yml",
        Path.cwd() / "config" / "system.yml",
    ]


def _sanitize_publish_profile(raw: dict[str, Any] | None) -> dict[str, str]:
    payload = raw if isinstance(raw, dict) else {}
    profile = dict(DEFAULT_GITHUB_PUBLISH_PROFILE)
    for key in list(profile.keys()):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            profile[key] = value.strip()
    return profile


def _load_publish_profile_from_system_config() -> dict[str, str]:
    for candidate in _system_config_candidates():
        try:
            if not candidate.exists():
                continue
            parsed = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                continue
            section = parsed.get("github_publish_profile")
            if isinstance(section, dict):
                return _sanitize_publish_profile(section)
        except Exception:
            continue
    return dict(DEFAULT_GITHUB_PUBLISH_PROFILE)


def _load_publish_profile_from_store() -> dict[str, str] | None:
    path = _profile_store_path()
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return _sanitize_publish_profile(payload)
    except Exception:
        return None


def _load_durable_publish_profile() -> tuple[dict[str, str], str]:
    source = "defaults"
    profile = _load_publish_profile_from_system_config()
    if profile != DEFAULT_GITHUB_PUBLISH_PROFILE:
        source = "config/system.yml"

    stored = _load_publish_profile_from_store()
    if stored:
        profile = _sanitize_publish_profile({**profile, **stored})
        source = "profile_store"

    env_overrides = {
        "github_owner": str(os.getenv("XV7_GITHUB_OWNER", "")).strip(),
        "git_user_name": str(os.getenv("XV7_GIT_USER_NAME", "")).strip(),
        "git_user_email": str(os.getenv("XV7_GIT_USER_EMAIL", "")).strip(),
        "sandbox_root_host": (
            str(os.getenv("XV7_SANDBOX_ROOT_DISPLAY", "")).strip()
            or str(os.getenv("XV7_SANDBOX_ROOT", "")).strip()
        ),
        "sandbox_root_container": str(
            os.getenv("XV7_SANDBOX_ROOT_CONTAINER", "")
        ).strip(),
        "proof_repo_pattern": str(
            os.getenv("XV7_GITHUB_PROOF_REPO_PATTERN", "")
        ).strip(),
        "proof_repo_url": str(os.getenv("XV7_GITHUB_PROOF_REPO_URL", "")).strip(),
    }
    for key, value in env_overrides.items():
        if value:
            profile[key] = value
            source = "env"

    return profile, source


def _persist_publish_profile(profile: dict[str, str]) -> None:
    path = _profile_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_publish_profile(profile), indent=2), encoding="utf-8"
    )


def _inspect_repo(
    project_path: Path,
    run_command: Callable[[list[str]], subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    probe = run_command(["git", "rev-parse", "--is-inside-work-tree"])
    if probe.returncode != 0:
        return {
            "is_git_repo": False,
            "branch": "",
            "latest_commit": "",
            "remotes": [],
            "origin_url": "",
            "status_short_branch": "",
            "status_lines": [],
        }

    branch_proc = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    commit_proc = run_command(["git", "rev-parse", "--short", "HEAD"])
    remotes_proc = run_command(["git", "remote", "-v"])
    status_proc = run_command(["git", "status", "--short", "--branch"])

    remote_lines = [
        line.strip()
        for line in (remotes_proc.stdout or "").splitlines()
        if line.strip()
    ]
    status_short_branch = (status_proc.stdout or "").strip()
    status_lines = [
        line.strip() for line in status_short_branch.splitlines() if line.strip()
    ]
    origin_url = _extract_origin_url(remote_lines)
    return {
        "is_git_repo": True,
        "branch": (branch_proc.stdout or "").strip(),
        "latest_commit": (commit_proc.stdout or "").strip(),
        "remotes": remote_lines,
        "origin_url": origin_url,
        "status_short_branch": status_short_branch,
        "status_lines": status_lines,
    }


def _read_git_config(
    run_command: Callable[[list[str]], subprocess.CompletedProcess[str]],
    key: str,
    *,
    use_global: bool = False,
) -> str:
    command = ["git", "config"]
    if use_global:
        command.append("--global")
    command.extend(["--get", key])
    proc = run_command(command)
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _configured_identity_from_env(
    profile: dict[str, str] | None = None,
) -> tuple[str, str]:
    name = (
        str(os.getenv("XV7_GIT_USER_NAME", "")).strip()
        or str(os.getenv("GIT_AUTHOR_NAME", "")).strip()
        or str(os.getenv("GIT_COMMITTER_NAME", "")).strip()
    )
    email = (
        str(os.getenv("XV7_GIT_USER_EMAIL", "")).strip()
        or str(os.getenv("GIT_AUTHOR_EMAIL", "")).strip()
        or str(os.getenv("GIT_COMMITTER_EMAIL", "")).strip()
    )
    if not name and isinstance(profile, dict):
        name = str(profile.get("git_user_name") or "").strip()
    if not email and isinstance(profile, dict):
        email = str(profile.get("git_user_email") or "").strip()
    return name, email


def _ensure_git_identity(
    run_command: Callable[[list[str]], subprocess.CompletedProcess[str]],
    profile: dict[str, str] | None = None,
) -> tuple[bool, str, str, str]:
    local_name = _read_git_config(run_command, "user.name", use_global=False)
    local_email = _read_git_config(run_command, "user.email", use_global=False)
    if local_name and local_email:
        return True, local_name, local_email, ""

    global_name = _read_git_config(run_command, "user.name", use_global=True)
    global_email = _read_git_config(run_command, "user.email", use_global=True)
    if global_name and global_email:
        return True, global_name, global_email, ""

    env_name, env_email = _configured_identity_from_env(profile)
    if env_name and env_email:
        set_name = run_command(["git", "config", "user.name", env_name])
        if set_name.returncode != 0:
            return (
                False,
                "",
                "",
                (set_name.stderr or "").strip() or "failed to set git user.name",
            )
        set_email = run_command(["git", "config", "user.email", env_email])
        if set_email.returncode != 0:
            return (
                False,
                "",
                "",
                (set_email.stderr or "").strip() or "failed to set git user.email",
            )
        return True, env_name, env_email, ""

    return (
        False,
        "",
        "",
        "Git author identity is not configured for this sandbox project. "
        "Set XV7_GIT_USER_NAME and XV7_GIT_USER_EMAIL (or git user.name/user.email) and retry.",
    )


def _command_exists(
    run_command: Callable[[list[str]], subprocess.CompletedProcess[str]],
    command: str,
) -> bool:
    proc = run_command([command, "--version"])
    return proc.returncode == 0


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
    publish_profile, profile_source = _load_durable_publish_profile()
    try:
        _persist_publish_profile(publish_profile)
    except Exception:
        pass

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

    write_project_files = bool(request.get("write_project_files", True))
    files = request.get("requested_files")
    if not isinstance(files, list) or not files:
        files = ["index.html", "assets/site.css", "assets/app.js", "README.md"]

    changed_files: list[str] = []
    if write_project_files:
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

    commands_run: list[str] = []

    def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
        commands_run.append(_command_text(args))
        return _run_command(project_path, args)

    def run_or_fail(
        command: list[str],
    ) -> tuple[bool, subprocess.CompletedProcess[str]]:
        proc = run_command(command)
        return proc.returncode == 0, proc

    def fail_result(
        *,
        proc: subprocess.CompletedProcess[str],
        failed_command: str,
        commit_created: bool,
        commit_sha: str,
        push_performed: bool,
        pushed: bool,
        repo_before: dict[str, Any],
        github_repo_url: str = "",
        remote_url: str = "",
    ) -> OperatorActionResult:
        return _result(
            action_id=action_id,
            status="failed",
            started_at=started_at,
            project_path=project_path,
            stdout_summary=(proc.stdout or "")[:500],
            stderr_summary=(proc.stderr or "")[:500],
            exit_code=proc.returncode,
            data={
                "project_path": str(project_path),
                "sandbox_root": str(sandbox_root),
                "publish_profile": publish_profile,
                "publish_profile_source": profile_source,
                "changed_files": changed_files,
                "commands": commands_run,
                "commands_run": commands_run,
                "failed_command": failed_command,
                "commit_sha": commit_sha,
                "commit_created": commit_created,
                "push_performed": push_performed,
                "pushed": pushed,
                "repo_before": repo_before,
                "github_repo_url": github_repo_url,
                "remote_url": remote_url,
            },
        )

    inspect_before = _inspect_repo(project_path, run_command)

    initialize_git = bool(request.get("initialize_git", True))
    if initialize_git and not bool(inspect_before.get("is_git_repo", False)):
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
                        "commands": commands_run,
                        "commands_run": commands_run,
                        "failed_command": failed,
                        "commit_created": False,
                        "push_performed": False,
                    },
                )
            run_or_fail(["git", "branch", "-M", "main"])
            inspect_before = _inspect_repo(project_path, run_command)

    commit_message = str(request.get("commit_message") or "build GitHub proof project")
    commit_created = False
    commit_sha = str(inspect_before.get("latest_commit") or "")
    github_repo_url = ""
    remote_url = str(inspect_before.get("origin_url") or "")
    if changed_files:
        identity_ok, _, _, identity_error = _ensure_git_identity(
            run_command,
            publish_profile,
        )
        if not identity_ok:
            proc_identity = subprocess.CompletedProcess(
                args=["git", "config", "user.name/user.email"],
                returncode=2,
                stdout="",
                stderr=identity_error,
            )
            result = fail_result(
                proc=proc_identity,
                failed_command="git config user.name/user.email",
                commit_created=False,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
            )
            result.data["git_identity_missing"] = True
            return result

        ok_add, proc_add = run_or_fail(["git", "add", "."])
        if not ok_add:
            failed = _command_text(
                proc_add.args
                if isinstance(proc_add.args, list)
                else ["git", "add", "."]
            )
            return fail_result(
                proc=proc_add,
                failed_command=failed,
                commit_created=False,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
            )

        ok_commit, proc_commit = run_or_fail(["git", "commit", "-m", commit_message])
        if not ok_commit:
            nothing_to_commit = (
                "nothing to commit" in (proc_commit.stdout or "").lower()
                or "nothing to commit" in (proc_commit.stderr or "").lower()
            )
            if not nothing_to_commit:
                failed = _command_text(
                    proc_commit.args
                    if isinstance(proc_commit.args, list)
                    else ["git", "commit", "-m", commit_message]
                )
                return fail_result(
                    proc=proc_commit,
                    failed_command=failed,
                    commit_created=False,
                    commit_sha=commit_sha,
                    push_performed=False,
                    pushed=False,
                    repo_before=inspect_before,
                    github_repo_url=github_repo_url,
                    remote_url=remote_url,
                )
        else:
            commit_created = True
            commit_sha = _extract_commit_sha(proc_commit.stdout) or commit_sha
            inspect_before = _inspect_repo(project_path, run_command)
            remote_url = str(inspect_before.get("origin_url") or remote_url)
    create_repo = bool(request.get("create_github_repo", False))
    push = bool(request.get("push", False))
    pushed = False
    repo_name = (
        str(request.get("github_repo_name") or project_name).strip() or project_name
    )

    needs_origin = bool(push or create_repo) and not remote_url
    if needs_origin:
        if push and not create_repo:
            proc_missing_remote = subprocess.CompletedProcess(
                args=["git", "remote", "-v"],
                returncode=2,
                stdout="",
                stderr=(
                    "The sandbox project is ready locally, but it has no GitHub remote. "
                    f"Tell me the repo target or say create a new GitHub repo named {repo_name}."
                ),
            )
            result = fail_result(
                proc=proc_missing_remote,
                failed_command="git remote -v",
                commit_created=commit_created,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
            )
            result.data["missing_remote"] = True
            result.data["suggested_repo_name"] = repo_name
            return result

        if create_repo and not _command_exists(run_command, "gh"):
            proc_gh_missing = subprocess.CompletedProcess(
                args=["gh", "--version"],
                returncode=127,
                stdout="",
                stderr=(
                    "GitHub CLI is not installed in the runtime. "
                    "I can still push using an existing git remote/SSH, or you need to install/configure gh for repo creation."
                ),
            )
            result = fail_result(
                proc=proc_gh_missing,
                failed_command="gh --version",
                commit_created=commit_created,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
            )
            result.data["gh_missing"] = True
            result.data["gh_required_for_repo_creation"] = True
            return result

        ok_auth, proc_auth = run_or_fail(["gh", "auth", "status"])
        if not ok_auth:
            failed = _command_text(
                proc_auth.args
                if isinstance(proc_auth.args, list)
                else ["gh", "auth", "status"]
            )
            return fail_result(
                proc=proc_auth,
                failed_command=failed,
                commit_created=commit_created,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
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
        ok_gh, proc_gh = run_or_fail(gh_command)
        if not ok_gh:
            stderr_text = (proc_gh.stderr or "").lower()
            stdout_text = (proc_gh.stdout or "").lower()
            repo_exists = (
                "already exists" in stderr_text or "already exists" in stdout_text
            )
            if repo_exists:
                view_command = [
                    "gh",
                    "repo",
                    "view",
                    repo_name,
                    "--json",
                    "url",
                    "-q",
                    ".url",
                ]
                ok_view, proc_view = run_or_fail(view_command)
                if not ok_view:
                    failed = _command_text(
                        proc_view.args
                        if isinstance(proc_view.args, list)
                        else view_command
                    )
                    return fail_result(
                        proc=proc_view,
                        failed_command=failed,
                        commit_created=commit_created,
                        commit_sha=commit_sha,
                        push_performed=False,
                        pushed=False,
                        repo_before=inspect_before,
                        github_repo_url=github_repo_url,
                        remote_url=remote_url,
                    )
                github_repo_url = (proc_view.stdout or "").strip()
                add_remote_cmd = ["git", "remote", "add", "origin", github_repo_url]
                ok_remote, proc_remote = run_or_fail(add_remote_cmd)
                if not ok_remote:
                    exists_origin = (
                        "remote origin already exists"
                        in (proc_remote.stderr or "").lower()
                    )
                    if not exists_origin:
                        failed = _command_text(
                            proc_remote.args
                            if isinstance(proc_remote.args, list)
                            else add_remote_cmd
                        )
                        return fail_result(
                            proc=proc_remote,
                            failed_command=failed,
                            commit_created=commit_created,
                            commit_sha=commit_sha,
                            push_performed=False,
                            pushed=False,
                            repo_before=inspect_before,
                            github_repo_url=github_repo_url,
                            remote_url=remote_url,
                        )
                    set_url_cmd = [
                        "git",
                        "remote",
                        "set-url",
                        "origin",
                        github_repo_url,
                    ]
                    ok_set, proc_set = run_or_fail(set_url_cmd)
                    if not ok_set:
                        failed = _command_text(
                            proc_set.args
                            if isinstance(proc_set.args, list)
                            else set_url_cmd
                        )
                        return fail_result(
                            proc=proc_set,
                            failed_command=failed,
                            commit_created=commit_created,
                            commit_sha=commit_sha,
                            push_performed=False,
                            pushed=False,
                            repo_before=inspect_before,
                            github_repo_url=github_repo_url,
                            remote_url=remote_url,
                        )
            else:
                failed = _command_text(
                    proc_gh.args if isinstance(proc_gh.args, list) else gh_command
                )
                return fail_result(
                    proc=proc_gh,
                    failed_command=failed,
                    commit_created=commit_created,
                    commit_sha=commit_sha,
                    push_performed=False,
                    pushed=False,
                    repo_before=inspect_before,
                    github_repo_url=github_repo_url,
                    remote_url=remote_url,
                )
        else:
            view_command = [
                "gh",
                "repo",
                "view",
                repo_name,
                "--json",
                "url",
                "-q",
                ".url",
            ]
            proc_view = run_command(view_command)
            if proc_view.returncode == 0:
                github_repo_url = (proc_view.stdout or "").strip()

        inspect_before = _inspect_repo(project_path, run_command)
        remote_url = str(inspect_before.get("origin_url") or remote_url)

    if create_repo and remote_url and not github_repo_url:
        view_command = ["gh", "repo", "view", repo_name, "--json", "url", "-q", ".url"]
        proc_view = run_command(view_command)
        if proc_view.returncode == 0:
            github_repo_url = (proc_view.stdout or "").strip()

    if push:
        if not remote_url:
            proc_missing = subprocess.CompletedProcess(
                args=["git", "push", "-u", "origin", "main"],
                returncode=2,
                stdout="",
                stderr="origin remote is not configured",
            )
            failed = _command_text(
                proc_missing.args
                if isinstance(proc_missing.args, list)
                else ["git", "push", "-u", "origin", "main"]
            )
            return fail_result(
                proc=proc_missing,
                failed_command=failed,
                commit_created=commit_created,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
            )

        branch_to_push = str(inspect_before.get("branch") or "main") or "main"
        push_command = ["git", "push", "-u", "origin", branch_to_push]
        ok_push, proc_push = run_or_fail(push_command)
        if not ok_push:
            failed = _command_text(
                proc_push.args if isinstance(proc_push.args, list) else push_command
            )
            return fail_result(
                proc=proc_push,
                failed_command=failed,
                commit_created=commit_created,
                commit_sha=commit_sha,
                push_performed=False,
                pushed=False,
                repo_before=inspect_before,
                github_repo_url=github_repo_url,
                remote_url=remote_url,
            )
        pushed = True

    inspect_after = _inspect_repo(project_path, run_command)
    remote_url = str(inspect_after.get("origin_url") or remote_url)

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
            "publish_profile": publish_profile,
            "publish_profile_source": profile_source,
            "changed_files": changed_files,
            "commands": commands_run,
            "commands_run": commands_run,
            "failed_command": "",
            "commit_sha": commit_sha,
            "commit_created": commit_created,
            "push_performed": pushed,
            "pushed": pushed,
            "repo_before": inspect_before,
            "repo_after": inspect_after,
            "github_repo_url": github_repo_url,
            "remote_url": remote_url,
            "branch": str(inspect_after.get("branch") or ""),
            "remotes": inspect_after.get("remotes", []),
            "status_short_branch_before": str(
                inspect_before.get("status_short_branch") or ""
            ),
            "status_short_branch_after": str(
                inspect_after.get("status_short_branch") or ""
            ),
            "status_lines": inspect_after.get("status_lines", []),
        },
    )
