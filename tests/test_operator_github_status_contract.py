from __future__ import annotations

from pathlib import Path

from core.operator.actions.github_project import _inspect_repo


class Proc:
    def __init__(self, args, returncode, stdout="", stderr=""):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_inspect_repo_uses_short_branch_status_contract(tmp_path: Path) -> None:
    calls = []

    def run_command(args):
        calls.append(args)
        if args == ["git", "rev-parse", "--is-inside-work-tree"]:
            return Proc(args, 0, stdout="true\n")
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return Proc(args, 0, stdout="main\n")
        if args == ["git", "rev-parse", "--short", "HEAD"]:
            return Proc(args, 0, stdout="abc1234\n")
        if args == ["git", "remote", "-v"]:
            return Proc(args, 0, stdout="")
        if args == ["git", "status", "--short", "--branch"]:
            return Proc(args, 0, stdout="## main\n")
        return Proc(args, 1, stderr="unexpected command")

    repo_state = _inspect_repo(tmp_path, run_command)

    assert ["git", "status", "--short", "--branch"] in calls
    assert ["git", "status", "--porcelain"] not in calls
    assert repo_state["branch"] == "main"
    assert repo_state["latest_commit"] == "abc1234"
    assert repo_state["status_short_branch"] == "## main"
    assert repo_state["status_lines"] == ["## main"]
