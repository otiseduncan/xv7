from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal


def list_runtime_brain_records(
    *,
    entries: list[tuple[Any, str, Any]],
    layer: Any | None,
    include_archived: bool,
    pending_only: bool,
    learned_only: bool,
    relevance: Literal[
        "current",
        "historical",
        "superseded",
        "expired",
        "needs_review",
    ]
    | None,
    history_only: bool,
    review_only: bool,
    serialize_brain_record: Callable[..., dict[str, Any]],
    status_label: Callable[[Any], str],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for record, source, path in entries:
        if layer is not None and record.layer != layer:
            continue
        if pending_only and record.status not in {"pending", "pending_review"}:
            continue
        if not include_archived and record.status not in {
            "active",
            "pending",
            "pending_review",
        }:
            continue
        if learned_only:
            tags = {str(tag).lower() for tag in record.tags}
            if "learned-rule" not in tags and "otis-learning" not in tags:
                continue

        serialized = serialize_brain_record(record=record, source=source, path=path)
        effective_relevance = serialized.get(
            "effective_relevance_state", record.relevance_state
        )
        stored_relevance = str(
            serialized.get("relevance_state", record.relevance_state)
        )
        status = serialized.get("status_label", status_label(record.status))

        if relevance is not None and effective_relevance != relevance:
            continue
        if history_only and not (
            stored_relevance in {"historical", "superseded", "expired"}
            or effective_relevance in {"historical", "superseded", "expired"}
        ):
            continue
        if review_only and not (
            status == "pending"
            or stored_relevance == "needs_review"
            or effective_relevance == "needs_review"
            or bool(serialized.get("hygiene_recommendations"))
            or any(
                str(flag).lower()
                in {
                    "old_phase_reference",
                    "completed_milestone",
                    "mixed_historical_and_operational",
                    "mixed_historical_and_current",
                }
                for flag in (serialized.get("hygiene_flags") or [])
            )
        ):
            continue

        records.append(serialized)

    return {"count": len(records), "records": records}


def build_runtime_brain_record_updates(
    *,
    payload: Any,
    summary_from_body: Callable[[str], str],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    if payload.layer is not None:
        updates["layer"] = payload.layer
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.body is not None:
        cleaned_body = payload.body.strip()
        updates["body"] = cleaned_body
        updates["summary"] = summary_from_body(cleaned_body)
    if payload.tags is not None:
        updates["tags"] = [
            tag
            for tag in {
                str(tag).strip()
                for tag in payload.tags
                if isinstance(tag, str) and tag.strip()
            }
        ]
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.relevance_state is not None:
        updates["relevance_state"] = payload.relevance_state
    if payload.superseded_by is not None:
        updates["superseded_by"] = payload.superseded_by.strip() or None
    if payload.valid_from is not None:
        updates["valid_from"] = payload.valid_from.strip() or None
    if payload.valid_until is not None:
        updates["valid_until"] = payload.valid_until.strip() or None
    if payload.applies_when is not None:
        updates["applies_when"] = payload.applies_when.strip() or None
    if payload.review_reason is not None:
        updates["review_reason"] = payload.review_reason.strip() or None
    if payload.last_reviewed_at is not None:
        updates["last_reviewed_at"] = payload.last_reviewed_at.strip() or None

    return updates


def serialize_refreshed_record_or_raise(
    *,
    loader: Any,
    record_id: str,
    missing_message: str,
    serialize_brain_record: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    refreshed = loader.get_record_with_source(record_id)
    if refreshed is None:
        raise RuntimeError(missing_message)
    saved_record, source, path = refreshed
    return serialize_brain_record(record=saved_record, source=source, path=path)


def mark_record_current(record: Any) -> Any:
    return record.model_copy(
        update={
            "status": "active",
            "relevance_state": "current",
            "superseded_by": None,
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def mark_record_historical(record: Any) -> Any:
    return record.model_copy(
        update={
            "relevance_state": "historical",
            "review_reason": record.review_reason or "Marked historical by operator.",
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def mark_record_superseded(
    record: Any, *, superseded_by: str | None, review_reason: str | None
) -> Any:
    return record.model_copy(
        update={
            "relevance_state": "superseded",
            "status": "disabled",
            "superseded_by": superseded_by,
            "review_reason": review_reason or "Superseded by newer record.",
            "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
