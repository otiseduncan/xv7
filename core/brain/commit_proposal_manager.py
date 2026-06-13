from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from core.brain.repo_safety_policy import RepoSafetyPolicy


@dataclass(frozen=True)
class GitStatusEntry:
    """A normalized git porcelain status entry."""

    raw_status: str
    path: str

    @property
    def status_code(self) -> str:
        return self.raw_status[:2].rstrip()

    @property
    def change_line(self) -> str:
        return f"{self.status_code} {self.path}".strip()


class CommitProposalManager:
    """Pure helpers for building safe commit proposal payloads.

    The Git subprocess execution still lives in AnswerContract for now. This manager is
    intentionally limited to deterministic parsing/filtering/payload construction so it
    can be validated before the runtime path is delegated.
    """

    @staticmethod
    def normalize_status_path(path_text: str) -> str:
        """Normalize a git porcelain path and unwrap rename destinations."""

        normalized = str(path_text or "").strip().replace("\\", "/")
        if " -> " in normalized:
            normalized = normalized.split(" -> ", 1)[-1].strip()
        return normalized

    @classmethod
    def parse_status_lines(cls, status_output: str) -> list[GitStatusEntry]:
        """Parse `git status --porcelain` output into normalized entries."""

        entries: list[GitStatusEntry] = []
        for raw_line in str(status_output or "").splitlines():
            line = raw_line.strip()
            if len(line) < 4:
                continue
            path = cls.normalize_status_path(line[3:])
            if not path:
                continue
            entries.append(GitStatusEntry(raw_status=line, path=path))
        return entries

    @staticmethod
    def filter_safe_entries(
        entries: list[GitStatusEntry],
        is_blocked: Callable[[str], bool] = RepoSafetyPolicy.is_blocked_commit_target,
    ) -> tuple[list[str], list[str], list[str]]:
        """Return included files, excluded files, and visible change lines."""

        included_files: list[str] = []
        excluded_files: list[str] = []
        change_lines: list[str] = []
        for entry in entries:
            if is_blocked(entry.path):
                excluded_files.append(entry.path)
                continue
            included_files.append(entry.path)
            change_lines.append(entry.change_line)
        return included_files, excluded_files, change_lines

    @staticmethod
    def proposed_commit_message(included_files: list[str]) -> str:
        if len(included_files) == 1:
            return f"chore: update {Path(included_files[0]).stem}"
        return "chore: local repository changes"

    @staticmethod
    def visible_summary(branch: str, included_files: list[str], excluded_files: list[str]) -> str:
        visible_lines: list[str] = []
        if included_files:
            visible_lines.append(
                f"I prepared a commit proposal for {len(included_files)} file(s) on branch {branch}. "
                "No files were changed, no commit was created, and no push was performed."
            )
        else:
            visible_lines.append(
                "I checked the repository and did not find any safe changes to include in a commit proposal. "
                "No files were changed and no commit was created."
            )
        if excluded_files:
            visible_lines.append(f"Excluded blocked paths: {', '.join(excluded_files[:5])}.")
        return " ".join(visible_lines)

    @classmethod
    def build_status_scan_proposal(
        cls,
        *,
        question: str,
        branch: str,
        status_output: str,
        diff_stat: str = "",
        proposal_id: str | None = None,
        is_blocked: Callable[[str], bool] = RepoSafetyPolicy.is_blocked_commit_target,
    ) -> dict[str, object]:
        """Build the deterministic fallback commit proposal from git status output."""

        entries = cls.parse_status_lines(status_output)
        included_files, excluded_files, change_lines = cls.filter_safe_entries(
            entries, is_blocked=is_blocked
        )
        raw_status_lines = [entry.raw_status for entry in entries]
        return {
            "type": "commit_proposal",
            "proposal_id": proposal_id or f"commit-{uuid4().hex[:12]}",
            "question": question,
            "branch": branch,
            "applied": False,
            "committed": False,
            "push_performed": False,
            "requires_confirmation": True,
            "included_files": included_files,
            "excluded_files": excluded_files,
            "status_lines": raw_status_lines,
            "change_lines": change_lines,
            "diff_stat": diff_stat.strip(),
            "proposed_commit_message": cls.proposed_commit_message(included_files),
            "visible_text": cls.visible_summary(branch, included_files, excluded_files),
        }

    @staticmethod
    def build_no_git_proposal(*, question: str, proposal_id: str | None = None) -> dict[str, object]:
        return {
            "type": "commit_proposal",
            "proposal_id": proposal_id or f"commit-{uuid4().hex[:12]}",
            "question": question,
            "branch": "unknown",
            "applied": False,
            "committed": False,
            "push_performed": False,
            "requires_confirmation": True,
            "included_files": [],
            "excluded_files": [],
            "status_lines": [],
            "change_lines": [],
            "diff_stat": "",
            "proposed_commit_message": "",
            "git_available": False,
            "visible_text": (
                "Git is not available in this environment. "
                "I cannot prepare a commit proposal without a Git workspace. "
                "No commit was created and no push was performed."
            ),
        }
