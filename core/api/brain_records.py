from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.brain.schema import BrainRecord


def summary_from_body(body: str) -> str:
    cleaned = " ".join(body.split()).strip()
    if not cleaned:
        return "(empty)"
    if len(cleaned) <= 160:
        return cleaned
    return cleaned[:157].rstrip() + "..."


def status_label(status: str) -> str:
    normalized = str(status or "").lower()
    if normalized in {"pending", "pending_review"}:
        return "pending"
    if normalized == "disabled":
        return "disabled"
    if normalized == "archived":
        return "archived"
    return "active"


def brain_hygiene_classification(record: BrainRecord) -> dict[str, Any]:
    text_blob = " ".join(
        [
            record.title,
            record.summary,
            record.body,
            " ".join(record.tags),
            " ".join(record.evidence),
        ]
    ).lower()
    flags: list[str] = []
    recommendations: list[dict[str, Any]] = []
    reasons: list[str] = []
    effective_relevance = record.relevance_state

    has_phase_ref = bool(re.search(r"\bb\d+(?:\.\d+)?\b", text_blob))
    has_milestone_done = any(
        token in text_blob
        for token in (
            "completed",
            "passed",
            "verified",
            "proven",
            "milestone",
            "done",
            "shipped",
            "phase",
        )
    )
    has_operational_rule = any(
        token in text_blob
        for token in (
            "from now on",
            "current",
            "in progress",
            "must",
            "always",
            "operator mode",
            "working priority",
            "active focus",
            "should",
            "bridge",
        )
    )

    if has_phase_ref:
        flags.append("old_phase_reference")
        reasons.append("Contains legacy B-phase references.")
    if has_milestone_done:
        flags.append("completed_milestone")
        reasons.append("Contains completed/passed milestone language.")
    if has_phase_ref and has_milestone_done:
        flags.append("historical_candidate")
        if record.relevance_state == "current":
            effective_relevance = "historical"
            recommendations.append(
                {
                    "type": "mark_historical_via_runtime_override",
                    "record_id": record.record_id,
                    "approval_required": True,
                    "reason": "Contains old completed milestones without current-only scoping.",
                    "payload": {
                        "relevance_state": "historical",
                        "review_reason": "Contains completed or passed phase milestone references.",
                    },
                }
            )

    if has_phase_ref and has_milestone_done and has_operational_rule:
        flags.append("mixed_historical_and_operational")
        flags.append("mixed_historical_and_current")
        effective_relevance = "needs_review"
        reasons.append(
            "Contains old completed milestones and current operational bridge rule content."
        )
        recommendations.append(
            {
                "type": "split_record",
                "record_id": record.record_id,
                "approval_required": True,
                "reason": "Split historical milestones from current operational behavior.",
                "steps": [
                    "Mark existing record as historical or superseded via runtime override",
                    "Create a smaller current operational rule record via runtime override",
                ],
            }
        )

    if record.valid_until:
        try:
            until = datetime.fromisoformat(record.valid_until.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if until < now and record.relevance_state in {"current", "needs_review"}:
                flags.append("expired_window")
                effective_relevance = "expired"
        except Exception:
            pass

    return {
        "effective_relevance_state": effective_relevance,
        "flags": flags,
        "recommended_actions": recommendations,
        "reason": " ".join(dict.fromkeys(reasons)),
    }


def serialize_brain_record(
    *,
    record: BrainRecord,
    source: str,
    path: Path,
    updated_at: str | None,
) -> dict[str, Any]:
    hygiene = brain_hygiene_classification(record)
    return {
        "record_id": record.record_id,
        "layer": record.layer.value,
        "title": record.title,
        "summary": record.summary,
        "body": record.body,
        "status": record.status,
        "status_label": status_label(record.status),
        "relevance_state": record.relevance_state,
        "effective_relevance_state": hygiene["effective_relevance_state"],
        "superseded_by": record.superseded_by,
        "valid_from": record.valid_from,
        "valid_until": record.valid_until,
        "applies_when": record.applies_when,
        "review_reason": record.review_reason,
        "last_reviewed_at": record.last_reviewed_at,
        "priority": record.priority,
        "tags": list(record.tags),
        "source": source,
        "writable": source == "runtime_override",
        "source_label": "runtime_override" if source == "runtime_override" else "seed",
        "hygiene_flags": hygiene["flags"],
        "hygiene_recommendations": hygiene["recommended_actions"],
        "hygiene_reason": hygiene.get("reason", ""),
        "updated_at": updated_at,
        "raw_record": record.model_dump(mode="json"),
    }
