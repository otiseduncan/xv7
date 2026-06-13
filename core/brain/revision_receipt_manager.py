from __future__ import annotations

from typing import Any
from uuid import uuid4


class RevisionReceiptManager:
    """Pure helpers for revision ids, counters, and receipt payloads."""

    @staticmethod
    def new_revision_id() -> str:
        return f"rev-{uuid4().hex[:12]}"

    @staticmethod
    def next_revision_number(artifact: dict[str, Any] | None) -> int:
        if not isinstance(artifact, dict):
            return 1

        raw_revision_number = artifact.get("revision_number")
        try:
            if isinstance(raw_revision_number, int):
                current = raw_revision_number
            elif isinstance(raw_revision_number, str):
                current = int(raw_revision_number)
            else:
                current = 0
        except ValueError:
            current = 0
        return max(current + 1, 1)

    @staticmethod
    def has_content_change(previous_content: str, revised_content: str) -> bool:
        return str(previous_content or "") != str(revised_content or "")

    @classmethod
    def build_revision_receipt(
        cls,
        *,
        previous_artifact: dict[str, Any] | None,
        revised_artifact: dict[str, Any],
        previous_content: str,
        revised_content: str,
        revision_id: str | None = None,
    ) -> dict[str, Any]:
        previous_artifact = (
            previous_artifact if isinstance(previous_artifact, dict) else {}
        )
        resolved_revision_id = revision_id or cls.new_revision_id()
        return {
            "artifact_id": revised_artifact.get("artifact_id")
            or previous_artifact.get("artifact_id"),
            "filename": revised_artifact.get("filename")
            or previous_artifact.get("filename"),
            "language": revised_artifact.get("language")
            or previous_artifact.get("language"),
            "revision_id": resolved_revision_id,
            "previous_revision_id": previous_artifact.get("revision_id"),
            "revision_number": cls.next_revision_number(previous_artifact),
            "changed": cls.has_content_change(previous_content, revised_content),
        }

    @staticmethod
    def visible_revision_summary(
        *,
        filename: str,
        revision_number: int,
        changed: bool,
    ) -> str:
        if changed:
            return (
                f"Updated {filename}. Revision {revision_number} is ready for review."
            )
        return (
            f"I reviewed {filename}, but the requested change did not alter the artifact content. "
            f"Revision {revision_number} was recorded for traceability."
        )
