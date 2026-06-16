from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends

from core.api.brain_records import status_label as _status_label
from core.api.brain_records import summary_from_body as _summary_from_body
from core.api.schemas import (
    BrainRecordApplyRecommendationRequest,
    BrainRecordRelevanceUpdateRequest,
    BrainRecordSplitRequest,
    BrainRecordUpdateRequest,
)
from core.brain.schema import BrainLayer
from core.runtime.auth import require_api_key

router = APIRouter()

_brain_context_manager_getter: Callable[[], Any] | None = None
_list_runtime_brain_records: Any = None
_serialize_brain_record: Any = None
_build_runtime_brain_record_updates: Any = None
_serialize_refreshed_record_or_raise: Any = None
_mark_record_current: Any = None
_mark_record_historical: Any = None
_mark_record_superseded: Any = None
_split_record_to_current_operational: Any = None


def configure_brain_record_routes(
    *,
    brain_context_manager_getter: Callable[[], Any],
    list_runtime_brain_records: Any,
    serialize_brain_record: Any,
    build_runtime_brain_record_updates: Any,
    serialize_refreshed_record_or_raise: Any,
    mark_record_current: Any,
    mark_record_historical: Any,
    mark_record_superseded: Any,
    split_record_to_current_operational: Any,
) -> None:
    global _brain_context_manager_getter
    global _list_runtime_brain_records
    global _serialize_brain_record
    global _build_runtime_brain_record_updates
    global _serialize_refreshed_record_or_raise
    global _mark_record_current
    global _mark_record_historical
    global _mark_record_superseded
    global _split_record_to_current_operational

    _brain_context_manager_getter = brain_context_manager_getter
    _list_runtime_brain_records = list_runtime_brain_records
    _serialize_brain_record = serialize_brain_record
    _build_runtime_brain_record_updates = build_runtime_brain_record_updates
    _serialize_refreshed_record_or_raise = serialize_refreshed_record_or_raise
    _mark_record_current = mark_record_current
    _mark_record_historical = mark_record_historical
    _mark_record_superseded = mark_record_superseded
    _split_record_to_current_operational = split_record_to_current_operational


def _brain_manager() -> Any:
    if _brain_context_manager_getter is None:
        raise RuntimeError("brain record routes are not configured")
    return _brain_context_manager_getter()


@router.get("/runtime/brain/records")
async def runtime_brain_records(
    layer: BrainLayer | None = None,
    include_archived: bool = True,
    pending_only: bool = False,
    learned_only: bool = False,
    relevance: Literal[
        "current",
        "historical",
        "superseded",
        "expired",
        "needs_review",
    ]
    | None = None,
    history_only: bool = False,
    review_only: bool = False,
) -> dict[str, Any]:
    return _list_runtime_brain_records(
        entries=_brain_manager().loader.load_records_with_source(),
        layer=layer,
        include_archived=include_archived,
        pending_only=pending_only,
        learned_only=learned_only,
        relevance=relevance,
        history_only=history_only,
        review_only=review_only,
        serialize_brain_record=_serialize_brain_record,
        status_label=_status_label,
    )


@router.put(
    "/runtime/brain/records/{record_id}",
    dependencies=[Depends(require_api_key)],
)
async def update_runtime_brain_record(
    record_id: str,
    payload: BrainRecordUpdateRequest,
) -> dict[str, Any]:
    found = _brain_manager().loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")

    record, _, _ = found
    updates = _build_runtime_brain_record_updates(
        payload=payload,
        summary_from_body=_summary_from_body,
    )

    updated = record.model_copy(update=updates)
    _brain_manager().loader.save_runtime_override(updated)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=record_id,
        missing_message=f"Updated record not found after save: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/deactivate",
    dependencies=[Depends(require_api_key)],
)
async def deactivate_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = _brain_manager().loader.archive_record(record_id)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Deactivated record not found after save: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/set-active",
    dependencies=[Depends(require_api_key)],
)
async def set_active_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = _brain_manager().loader.set_record_active(record_id)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Activated record not found after save: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/approve",
    dependencies=[Depends(require_api_key)],
)
async def approve_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = _brain_manager().loader.approve_record(record_id)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Approved record not found after save: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/reject",
    dependencies=[Depends(require_api_key)],
)
async def reject_runtime_brain_record(record_id: str) -> dict[str, Any]:
    updated = _brain_manager().loader.reject_record(record_id)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Rejected record not found after save: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/mark-current",
    dependencies=[Depends(require_api_key)],
)
async def mark_current_runtime_brain_record(record_id: str) -> dict[str, Any]:
    found = _brain_manager().loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found
    updated = _mark_record_current(record)
    _brain_manager().loader.save_runtime_override(updated)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Record not found after update: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/mark-historical",
    dependencies=[Depends(require_api_key)],
)
async def mark_historical_runtime_brain_record(record_id: str) -> dict[str, Any]:
    found = _brain_manager().loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found
    updated = _mark_record_historical(record)
    _brain_manager().loader.save_runtime_override(updated)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Record not found after update: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/mark-superseded",
    dependencies=[Depends(require_api_key)],
)
async def mark_superseded_runtime_brain_record(
    record_id: str,
    payload: BrainRecordRelevanceUpdateRequest,
) -> dict[str, Any]:
    if payload.relevance_state != "superseded":
        raise ValueError("mark-superseded requires relevance_state='superseded'.")

    found = _brain_manager().loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found

    updated = _mark_record_superseded(
        record,
        superseded_by=payload.superseded_by,
        review_reason=payload.review_reason,
    )
    _brain_manager().loader.save_runtime_override(updated)
    return _serialize_refreshed_record_or_raise(
        loader=_brain_manager().loader,
        record_id=updated.record_id,
        missing_message=f"Record not found after update: {record_id}",
        serialize_brain_record=_serialize_brain_record,
    )


@router.post(
    "/runtime/brain/records/{record_id}/apply-recommendation",
    dependencies=[Depends(require_api_key)],
)
async def apply_runtime_brain_record_recommendation(
    record_id: str,
    payload: BrainRecordApplyRecommendationRequest,
) -> dict[str, Any]:
    found = _brain_manager().loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found

    if not payload.approve:
        return {
            "record_id": record_id,
            "applied": False,
            "recommendation_type": payload.recommendation_type,
            "status": "rejected",
        }

    if payload.recommendation_type == "mark_historical_via_runtime_override":
        updated = record.model_copy(
            update={
                "relevance_state": "historical",
                "review_reason": "Approved hygiene recommendation: historical.",
                "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _brain_manager().loader.save_runtime_override(updated)
        refreshed = _brain_manager().loader.get_record_with_source(record_id)
        if refreshed is None:
            raise RuntimeError(f"Record not found after update: {record_id}")
        saved_record, source, path = refreshed
        return {
            "record": _serialize_brain_record(
                record=saved_record,
                source=source,
                path=path,
            ),
            "applied": True,
            "recommendation_type": payload.recommendation_type,
            "status": "applied",
        }

    if payload.recommendation_type == "split_record":
        historical, created = _split_record_to_current_operational(
            record=record,
            operational_title=payload.operational_title,
            operational_summary=payload.operational_summary,
            operational_body=payload.operational_body,
            tags=payload.tags,
            layer=payload.layer,
            review_reason="Approved hygiene recommendation: split applied.",
            applies_when=None,
            valid_from=None,
            valid_until=None,
        )
        historical_refreshed = _brain_manager().loader.get_record_with_source(
            historical.record_id
        )
        created_refreshed = _brain_manager().loader.get_record_with_source(
            created.record_id
        )
        if historical_refreshed is None or created_refreshed is None:
            raise RuntimeError(f"Split records not found after update: {record_id}")
        historical_record, historical_source, historical_path = historical_refreshed
        created_record, created_source, created_path = created_refreshed
        return {
            "record": _serialize_brain_record(
                record=historical_record,
                source=historical_source,
                path=historical_path,
            ),
            "created_record": _serialize_brain_record(
                record=created_record,
                source=created_source,
                path=created_path,
            ),
            "applied": True,
            "recommendation_type": payload.recommendation_type,
            "status": "applied",
        }

    raise ValueError(f"Unsupported recommendation type: {payload.recommendation_type}")


@router.post(
    "/runtime/brain/records/{record_id}/split",
    dependencies=[Depends(require_api_key)],
)
async def split_runtime_brain_record(
    record_id: str,
    payload: BrainRecordSplitRequest,
) -> dict[str, Any]:
    found = _brain_manager().loader.get_record_with_source(record_id)
    if found is None:
        raise ValueError(f"Record not found: {record_id}")
    record, _, _ = found

    historical, created = _split_record_to_current_operational(
        record=record,
        operational_title=payload.operational_title,
        operational_summary=payload.operational_summary,
        operational_body=payload.operational_body,
        tags=payload.tags,
        layer=payload.layer,
        review_reason=payload.review_reason,
        applies_when=payload.applies_when,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )

    historical_refreshed = _brain_manager().loader.get_record_with_source(
        historical.record_id
    )
    created_refreshed = _brain_manager().loader.get_record_with_source(
        created.record_id
    )
    if historical_refreshed is None or created_refreshed is None:
        raise RuntimeError(f"Split records not found after update: {record_id}")

    historical_record, historical_source, historical_path = historical_refreshed
    created_record, created_source, created_path = created_refreshed

    return {
        "applied": True,
        "source_record": _serialize_brain_record(
            record=historical_record,
            source=historical_source,
            path=historical_path,
        ),
        "created_record": _serialize_brain_record(
            record=created_record,
            source=created_source,
            path=created_path,
        ),
    }
