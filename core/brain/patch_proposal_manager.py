from __future__ import annotations

import difflib
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class PatchProposalManager:
    """Pure helpers for artifact patch proposal metadata and receipts.

    Runtime file IO and git execution stay in AnswerContract for now. This manager
    only handles deterministic payload shaping and session metadata extraction so it
    can be validated before delegation.
    """

    @staticmethod
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def content_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def build_unified_diff(
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
            before_lines,
            after_lines,
            fromfile=from_file,
            tofile=to_file,
            n=3,
        )
        text = "".join(diff).strip()
        return text or f"--- {from_file}\n+++ {to_file}\n"

    @staticmethod
    def extract_patch_proposal_from_metadata(
        metadata: dict[str, Any],
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
    def latest_pending_patch_proposal(
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
                proposal = cls.extract_patch_proposal_from_metadata(metadata)
                if proposal is None:
                    continue
                if proposal.get("applied") is True:
                    continue
                return proposal

        if isinstance(session_metadata, dict):
            payload = session_metadata.get("last_assistant_payload")
            if isinstance(payload, dict):
                proposal = cls.extract_patch_proposal_from_metadata(payload)
                if proposal is not None and proposal.get("applied") is not True:
                    return proposal
        return None

    @classmethod
    def latest_applied_patch_proposal(
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
                proposal = cls.extract_patch_proposal_from_metadata(metadata)
                if proposal is None:
                    continue
                if proposal.get("applied") is True:
                    return proposal

        if isinstance(session_metadata, dict):
            payload = session_metadata.get("last_assistant_payload")
            if isinstance(payload, dict):
                proposal = cls.extract_patch_proposal_from_metadata(payload)
                if proposal is not None and proposal.get("applied") is True:
                    return proposal
        return None

    @classmethod
    def applied_patch_with_runtime_fields(
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
            "applied_at": str(proposal.get("applied_at") or cls.utc_now_iso()),
            "content_length": len(content),
            "content_sha256": cls.content_sha256(content) if content else "",
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
    def build_patch_proposal_payload(
        cls,
        *,
        question: str,
        target_path: str,
        content: str,
        language: str,
        source_artifact_id: str | None = None,
        before_content: str | None = None,
        proposal_id: str | None = None,
        validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        diff = cls.build_unified_diff(
            target_path=target_path,
            before_content=before_content,
            after_content=content,
        )
        operation = "create" if before_content is None else "update"
        return {
            "type": "artifact_patch_proposal",
            "proposal_id": proposal_id or f"patch-{uuid4().hex[:12]}",
            "question": question,
            "target_path": target_path,
            "operation": operation,
            "language": language,
            "content": content,
            "content_length": len(content),
            "content_sha256": cls.content_sha256(content) if content else "",
            "source_artifact_id": source_artifact_id or "",
            "validation": validation or {"status": "not_run"},
            "diff": diff,
            "applied": False,
            "requires_confirmation": True,
        }
