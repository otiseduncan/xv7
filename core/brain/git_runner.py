from __future__ import annotations

import subprocess
from pathlib import Path


def run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command under *repo_root* and return the CompletedProcess."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=8,
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
            stderr=f"git command timed out after 8s while running {command}",
        )
