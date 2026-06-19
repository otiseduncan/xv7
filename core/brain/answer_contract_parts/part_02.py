from __future__ import annotations

import os
import html
import re
import difflib
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from core.brain.artifact_fidelity_manager import ArtifactFidelityManager
from core.brain.artifact_response_service import ArtifactResponseService
from core.brain.answer_decision_service import AnswerDecisionService
from core.brain.artifact_utils import (
    content_sha256,
    safe_slug,
    slugify_artifact_name,
    utc_now_iso,
)
from core.brain.code_artifact_builder import CodeArtifactBuilder
from core.brain.git_runner import run_git
from core.brain.intent_router import IntentRouter
from core.brain.repo_safety_policy import RepoSafetyPolicy
from core.brain.sandbox_writer import SandboxWriteManager
from core.brain.schema import BrainLayer, BrainRecord
from core.operator.slash_commands import get_tool_capability_summary
from core.runtime.model_registry import (
    configured_ollama_base_url_candidates,
    resolve_model_for_runtime_role,
)



AnswerContract = None

@classmethod
def _verify_applied_patch_content(
    cls,
    *,
    proposal: dict[str, Any],
    include_business_name: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = cls._workspace_root()
    target_path = str(proposal.get("target_path") or "").replace("\\", "/")
    expected_content = str(proposal.get("content") or "")
    language = str(proposal.get("language") or "html").lower()
    checks: list[dict[str, str]] = []
    failures: list[str] = []

    def _add(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "status": "passed" if passed else "failed",
                "detail": detail,
            }
        )
        if not passed:
            failures.append(f"{name}: {detail}")

    resolved, resolve_error = cls._resolve_safe_patch_target(
        root=root, target_path=target_path
    )
    _add(
        "safe_target_path",
        resolve_error is None and resolved is not None,
        resolve_error or "target path resolved safely",
    )

    actual_content = ""
    if resolved is not None:
        exists = resolved.exists()
        _add(
            "file_exists",
            exists,
            "file exists on disk" if exists else "file is missing on disk",
        )
        if exists:
            actual_content = resolved.read_text(encoding="utf-8")
            _add(
                "content_non_empty",
                bool(actual_content.strip()),
                "file content is non-empty",
            )
            _add(
                "content_matches_applied_proposal",
                actual_content == expected_content,
                "file content matches applied proposal",
            )
            _add(
                "content_no_markdown_fence",
                "```" not in actual_content,
                "content has no markdown fences",
            )
            _add(
                "content_no_remote_scripts_assets",
                not re.search(
                    r"<script[^>]+src\s*=\s*['\"]https?://",
                    actual_content,
                    flags=re.IGNORECASE,
                )
                and not re.search(
                    r"<(img|link|source)[^>]+(src|href)\s*=\s*['\"]https?://",
                    actual_content,
                    flags=re.IGNORECASE,
                ),
                "content has no remote script or asset URLs",
            )
            if language == "html":
                lowered = actual_content.lower()
                _add(
                    "html_shell",
                    "<!doctype html" in lowered or "<html" in lowered,
                    "html shell markers are present",
                )
            if include_business_name:
                business_name = (
                    cls._extract_business_name_from_html(expected_content) or ""
                )
                if business_name:
                    _add(
                        "business_name_present",
                        business_name.lower() in actual_content.lower(),
                        "business name remains present",
                    )

    status = "failed" if failures else "passed"
    verification = {
        "status": status,
        "verified": status == "passed",
        "checks": checks,
        "failures": failures,
        "verified_at": cls._utc_now_iso(),
        "content_length": len(actual_content) if actual_content else 0,
        "content_sha256": (
            cls._content_sha256(actual_content) if actual_content else ""
        ),
    }
    return verification, {
        "actual_content": actual_content,
        "target_path": target_path,
    }

@classmethod
def _applied_patch_with_runtime_fields(
    cls,
    *,
    proposal: dict[str, Any],
    verification: dict[str, Any] | None = None,
    targeted_validation: dict[str, Any] | None = None,
    preview_path: str | None = None,
) -> dict[str, Any]:
    content = str(proposal.get("content") or "")
    updated = {
        **proposal,
        "applied": bool(proposal.get("applied", False)),
        "applied_at": str(proposal.get("applied_at") or cls._utc_now_iso()),
        "content_length": len(content),
        "content_sha256": cls._content_sha256(content) if content else "",
        "source_artifact_id": str(proposal.get("source_artifact_id") or ""),
        "validation_status": str(
            (proposal.get("validation") or {}).get("status") or "failed"
        ),
        "tests_run": bool(proposal.get("tests_run", False)),
        "commit_created": bool(proposal.get("commit_created", False)),
        "push_performed": bool(proposal.get("push_performed", False)),
    }
    if verification is not None:
        updated["post_apply_verification"] = verification
    if targeted_validation is not None:
        updated["targeted_validation"] = targeted_validation
    if preview_path:
        updated["preview_path"] = preview_path
    return updated

@classmethod
def _build_unified_diff(
    cls,
    *,
    target_path: str,
    before_content: str | None,
    after_content: str,
) -> str:
    before_lines = (
        [] if before_content is None else before_content.splitlines(keepends=True)
    )
    after_lines = after_content.splitlines(keepends=True)
    from_file = "/dev/null" if before_content is None else f"a/{target_path}"
    to_file = f"b/{target_path}"
    diff = difflib.unified_diff(
        before_lines, after_lines, fromfile=from_file, tofile=to_file, n=3
    )
    text = "".join(diff).strip()
    return text or f"--- {from_file}\n+++ {to_file}\n"

@classmethod
def _extract_patch_proposal_from_metadata(
    cls, metadata: dict[str, Any]
) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    proposal = metadata.get("artifact_patch_proposal")
    if not isinstance(proposal, dict):
        return None
    if str(proposal.get("type") or "") != "artifact_patch_proposal":
        return None
    target_path = str(proposal.get("target_path") or "").strip()
    content = proposal.get("content")
    if not target_path or not isinstance(content, str):
        return None
    return proposal

@classmethod
def _latest_pending_patch_proposal(
    cls,
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(session_messages, list):
        for message in reversed(session_messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role") or "").lower() != "assistant":
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            proposal = cls._extract_patch_proposal_from_metadata(metadata)
            if proposal is None:
                continue
            if proposal.get("applied") is True:
                continue
            return proposal

    if isinstance(session_metadata, dict):
        payload = session_metadata.get("last_assistant_payload")
        if isinstance(payload, dict):
            proposal = cls._extract_patch_proposal_from_metadata(payload)
            if proposal is not None and proposal.get("applied") is not True:
                return proposal
    return None

@classmethod
def _latest_applied_patch_proposal(
    cls,
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(session_messages, list):
        for message in reversed(session_messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role") or "").lower() != "assistant":
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            proposal = cls._extract_patch_proposal_from_metadata(metadata)
            if proposal is None:
                continue
            if proposal.get("applied") is True:
                return proposal

    if isinstance(session_metadata, dict):
        payload = session_metadata.get("last_assistant_payload")
        if isinstance(payload, dict):
            proposal = cls._extract_patch_proposal_from_metadata(payload)
            if proposal is not None and proposal.get("applied") is True:
                return proposal
    return None

@classmethod
def _extract_commit_proposal_from_metadata(
    cls, metadata: dict[str, Any]
) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    proposal = metadata.get("commit_proposal")
    if not isinstance(proposal, dict):
        return None
    if str(proposal.get("type") or "") != "commit_proposal":
        return None
    proposal_id = str(proposal.get("proposal_id") or "").strip()
    if not proposal_id:
        return None
    return proposal

@classmethod
def _latest_pending_commit_proposal(
    cls,
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(session_messages, list):
        for message in reversed(session_messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role") or "").lower() != "assistant":
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            proposal = cls._extract_commit_proposal_from_metadata(metadata)
            if proposal is None:
                continue
            if proposal.get("committed") is True:
                continue
            return proposal

    if isinstance(session_metadata, dict):
        payload = session_metadata.get("last_assistant_payload")
        if isinstance(payload, dict):
            proposal = cls._extract_commit_proposal_from_metadata(payload)
            if proposal is not None and proposal.get("committed") is not True:
                return proposal
    return None

@classmethod
def _build_commit_proposal(
    cls,
    *,
    question: str,
    session_messages: list[Any] | None = None,
    session_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = cls._workspace_root()
    proposal_id = f"commit-{uuid4().hex[:12]}"

    # Check git availability using --git-dir which works on repos with no commits.
    # (rev-parse --abbrev-ref HEAD fails with exit 128 on a fresh unborn repo.)
    git_dir_proc = cls._run_git(root, ["rev-parse", "--git-dir"])
    git_available = git_dir_proc.returncode == 0

    if git_available:
        # symbolic-ref works on fresh repos; rev-parse --abbrev-ref HEAD doesn't.
        sym_proc = cls._run_git(root, ["symbolic-ref", "--short", "HEAD"])
        if sym_proc.returncode == 0:
            branch = sym_proc.stdout.strip()
        else:
            abbrev_proc = cls._run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
            branch = (
                abbrev_proc.stdout.strip()
                if abbrev_proc.returncode == 0
                else "unknown"
            )
    else:
        branch = "unknown"

    # Applied-patch-aware path: prefer the applied patch from session state over
    # generic git-status scan so that container/host path issues are diagnosed
    # precisely rather than silently returning an empty proposal.
    applied_patch = cls._latest_applied_patch_proposal(
        session_messages, session_metadata
    )
    if applied_patch is not None:
        target_path = str(applied_patch.get("target_path") or "").replace("\\", "/")
        if target_path:
            target_abs = (root / Path(target_path)).resolve()
            file_exists = target_abs.exists()

            if not git_available:
                # Running inside a container with no .git — clear diagnostic
                if file_exists:
                    return {
                        "type": "commit_proposal",
                        "proposal_id": proposal_id,
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
                        "source_applied_patch": target_path,
                        "git_available": False,
                        "container_path_mismatch": True,
                        "visible_text": (
                            f"The applied patch target {target_path} exists in the runtime container, "
                            "but Git is not available in this environment. "
                            "I cannot prepare a host commit from inside the container. "
                            "The file was written correctly but committing must be done from the host workspace."
                        ),
                    }
                return {
                    "type": "commit_proposal",
                    "proposal_id": proposal_id,
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
                    "source_applied_patch": target_path,
                    "git_available": False,
                    "visible_text": (
                        f"The applied patch target {target_path} does not exist on disk "
                        "and Git is not available in this environment. "
                        "No commit was created and no push was performed."
                    ),
                }

            # Git is available — check file presence
            if not file_exists:
                return {
                    "type": "commit_proposal",
                    "proposal_id": proposal_id,
                    "question": question,
                    "branch": branch,
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
                    "source_applied_patch": target_path,
                    "visible_text": (
                        f"The applied patch target {target_path} does not exist on disk. "
                        "No commit was created and no push was performed."
                    ),
                }

            # Check whether this specific path is gitignored
            ignore_proc = cls._run_git(
                root, ["check-ignore", "-v", "--", target_path]
            )
            if ignore_proc.returncode == 0:
                return {
                    "type": "commit_proposal",
                    "proposal_id": proposal_id,
                    "question": question,
                    "branch": branch,
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
                    "source_applied_patch": target_path,
                    "ignored_paths": [target_path],
                    "visible_text": (
                        f"The applied patch target {target_path} is excluded by .gitignore. "
                        "I cannot prepare a commit for an ignored path. "
                        "No commit was created and no push was performed."
                    ),
                }

            # Check git status for this specific file
            status_proc = cls._run_git(
                root, ["status", "--porcelain", "--", target_path]
            )
            status_line = status_proc.stdout.strip()
            if not status_line:
                return {
                    "type": "commit_proposal",
                    "proposal_id": proposal_id,
                    "question": question,
                    "branch": branch,
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
                    "source_applied_patch": target_path,
                    "no_diff": True,
                    "visible_text": (
                        f"The applied patch target exists, but Git does not show a diff for {target_path}, "
                        "so there is nothing to commit."
                    ),
                }

            # File is untracked or modified — build proposal from it
            applied_target_stem = Path(target_path).stem
            proposed_message = f"feat: add {applied_target_stem} generated site"
            return {
                "type": "commit_proposal",
                "proposal_id": proposal_id,
                "question": question,
                "branch": branch,
                "applied": False,
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
                "included_files": [target_path],
                "excluded_files": [],
                "status_lines": [status_line],
                "change_lines": [f"{status_line[:2].rstrip()} {target_path}"],
                "diff_stat": "",
                "proposed_commit_message": proposed_message,
                "source_applied_patch": target_path,
                "visible_text": (
                    f"I prepared a commit proposal for {target_path} on branch {branch}. "
                    "No files were changed, no commit was created, and no push was performed."
                ),
            }

    # No applied patch in session — fall back to generic git status scan
    if not git_available:
        return {
            "type": "commit_proposal",
            "proposal_id": proposal_id,
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

    status_proc = cls._run_git(
        root, ["status", "--porcelain", "--untracked-files=all"]
    )
    diff_stat_proc = cls._run_git(root, ["diff", "--stat"])

    raw_status_lines = [
        line.strip() for line in status_proc.stdout.splitlines() if line.strip()
    ]
    included_files: list[str] = []
    excluded_files: list[str] = []
    change_lines: list[str] = []
    for line in raw_status_lines:
        if len(line) < 4:
            continue
        path_text = line[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[-1].strip()
        normalized_path = path_text.replace("\\", "/")
        if cls._is_blocked_commit_target(normalized_path):
            excluded_files.append(normalized_path)
            continue
        included_files.append(normalized_path)
        change_lines.append(f"{line[:2]} {normalized_path}")

    proposed_commit_message = (
        f"chore: update {Path(included_files[0]).stem}"
        if len(included_files) == 1
        else "chore: local repository changes"
    )
    visible_lines = []
    if included_files:
        visible_lines.append(
            f"I prepared a commit proposal for {len(included_files)} file(s) on branch {branch}. No files were changed, no commit was created, and no push was performed."
        )
    else:
        visible_lines.append(
            "I checked the repository and did not find any safe changes to include in a commit proposal. No files were changed and no commit was created."
        )
    if excluded_files:
        visible_lines.append(
            f"Excluded blocked paths: {', '.join(excluded_files[:5])}."
        )

    return {
        "type": "commit_proposal",
        "proposal_id": proposal_id,
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
        "diff_stat": (
            diff_stat_proc.stdout.strip() if diff_stat_proc.returncode == 0 else ""
        ),
        "proposed_commit_message": proposed_commit_message,
        "visible_text": " ".join(visible_lines),
    }

@classmethod
def _apply_commit_proposal(
    cls,
    *,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    root = cls._workspace_root()
    included_files = [
        str(path).replace("\\", "/")
        for path in proposal.get("included_files") or []
        if str(path).strip()
    ]
    if not included_files:
        return {
            "visible_text": "I cannot commit this proposal because there are no safe files to stage.",
            "commit_proposal": {
                **proposal,
                "applied": False,
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
            },
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                "context_receipts": [],
                "record_ids": [],
            },
            "provenance": {
                "commit_proposal": "apply_blocked",
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
                "failure_reason": "no_safe_files",
            },
        }

    add_proc = cls._run_git(root, ["add", "-A", "--", *included_files])
    if add_proc.returncode != 0:
        return {
            "visible_text": "I could not stage the proposed files for commit.",
            "commit_proposal": {
                **proposal,
                "applied": False,
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
            },
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                "context_receipts": [],
                "record_ids": [],
            },
            "provenance": {
                "commit_proposal": "stage_failed",
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
                "failure_reason": add_proc.stderr.strip() or "git add failed",
            },
        }

    commit_message = str(
        proposal.get("proposed_commit_message") or "chore: local repository changes"
    )
    commit_proc = cls._run_git(root, ["commit", "-m", commit_message])
    if commit_proc.returncode != 0:
        return {
            "visible_text": commit_proc.stderr.strip()
            or "I could not create the local commit.",
            "commit_proposal": {
                **proposal,
                "applied": False,
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
            },
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
                "context_receipts": [],
                "record_ids": [],
            },
            "provenance": {
                "commit_proposal": "commit_failed",
                "committed": False,
                "push_performed": False,
                "requires_confirmation": True,
                "failure_reason": commit_proc.stderr.strip() or "git commit failed",
            },
        }

    sha_proc = cls._run_git(root, ["rev-parse", "--short", "HEAD"])
    commit_sha = sha_proc.stdout.strip() if sha_proc.returncode == 0 else "unknown"
    committed_proposal = {
        **proposal,
        "applied": True,
        "committed": True,
        "committed_at": cls._utc_now_iso(),
        "commit_sha": commit_sha,
        "push_performed": False,
        "requires_confirmation": True,
    }
    return {
        "visible_text": (
            f"Committed the approved local changes on branch {committed_proposal.get('branch', 'unknown')} as {commit_sha}. "
            "No push was performed."
        ),
        "commit_proposal": committed_proposal,
        "context_receipt": {
            "compact": "Memory: -; Knowledge: -; Focus: -; Proof: commit-proposal-apply",
            "context_receipts": [],
            "record_ids": [],
        },
        "provenance": {
            "commit_proposal": "committed",
            "committed": True,
            "push_performed": False,
            "requires_confirmation": True,
            "commit_sha": commit_sha,
        },
    }

@classmethod
def _build_patch_proposal_from_artifact(
    cls,
    *,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    root = cls._workspace_root()
    language = str(artifact.get("language") or "html").lower()
    filename = cls._sanitize_filename(
        str(artifact.get("filename") or "index.html"), language
    )
    target_path = cls._proposed_patch_target_path(artifact=artifact)
    resolved_target = (root / Path(target_path)).resolve()
    source_artifact_id = str(
        artifact.get("revision_id") or artifact.get("artifact_id") or "artifact"
    )
    current_content = str(artifact.get("content") or "")
    existing_content = (
        resolved_target.read_text(encoding="utf-8")
        if resolved_target.exists()
        else None
    )
    operation = "update" if existing_content is not None else "create"
    business_name = cls._extract_business_name_from_html(current_content) or ""
    validation_status, checks, failures = cls._validate_patch_proposal(
        root=root,
        target_path=target_path,
        content=current_content,
        language=language,
        business_name=business_name,
        operation=operation,
    )
    proposal_id = f"patch-{uuid4().hex[:12]}"
    diff_text = cls._build_unified_diff(
        target_path=target_path,
        before_content=existing_content,
        after_content=current_content,
    )

    return {
        "type": "artifact_patch_proposal",
        "proposal_id": proposal_id,
        "source_artifact_id": source_artifact_id,
        "filename": filename,
        "target_path": target_path,
        "operation": operation,
        "language": language,
        "applied": False,
        "requires_confirmation": True,
        "content": current_content,
        "diff": diff_text,
        "validation": {
            "status": validation_status,
            "checks": checks,
            "failures": failures,
        },
    }

def install_answer_contract_part_02(contract_cls):
    global AnswerContract
    AnswerContract = contract_cls
    setattr(contract_cls, "_verify_applied_patch_content", _verify_applied_patch_content)
    setattr(contract_cls, "_applied_patch_with_runtime_fields", _applied_patch_with_runtime_fields)
    setattr(contract_cls, "_build_unified_diff", _build_unified_diff)
    setattr(contract_cls, "_extract_patch_proposal_from_metadata", _extract_patch_proposal_from_metadata)
    setattr(contract_cls, "_latest_pending_patch_proposal", _latest_pending_patch_proposal)
    setattr(contract_cls, "_latest_applied_patch_proposal", _latest_applied_patch_proposal)
    setattr(contract_cls, "_extract_commit_proposal_from_metadata", _extract_commit_proposal_from_metadata)
    setattr(contract_cls, "_latest_pending_commit_proposal", _latest_pending_commit_proposal)
    setattr(contract_cls, "_build_commit_proposal", _build_commit_proposal)
    setattr(contract_cls, "_apply_commit_proposal", _apply_commit_proposal)
    setattr(contract_cls, "_build_patch_proposal_from_artifact", _build_patch_proposal_from_artifact)
