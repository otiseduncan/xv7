from __future__ import annotations

from typing import Any

from core.brain.schema import BrainLayer


def intent_context_receipt(
    *,
    intent_class: str,
    record_id: str,
    source: str,
    persistence: str,
    status: str,
) -> dict[str, Any]:
    return {
        "compact": (
            f"Context receipt: Intent {intent_class} "
            f"(record={record_id}; source={source}; persistence={persistence}; status={status})."
        ),
        "context_receipts": [
            {
                "layer": "memory",
                "record_id": record_id,
                "source": source,
                "persistence": persistence,
                "status": status,
                "intent_class": intent_class,
            }
        ],
        "record_ids": [record_id],
    }


def learning_context_receipt(
    *,
    learning_layer: BrainLayer,
    learned_record_id: str,
    proof_required: bool,
) -> dict[str, Any]:
    compact_parts = [
        f"Memory: {learned_record_id}"
        if learning_layer == BrainLayer.MEMORY
        else "Memory: -",
        f"Knowledge: {learned_record_id}"
        if learning_layer == BrainLayer.KNOWLEDGE
        else "Knowledge: -",
        "Focus: -",
        "Proof: required" if proof_required else "Proof: none",
    ]
    return {
        "compact": "; ".join(compact_parts),
        "context_receipts": [
            {
                "layer": learning_layer.value,
                "record_id": learned_record_id,
                "status": "active",
                "source": "direct_user_instruction",
            }
        ],
        "record_ids": [learned_record_id],
    }


def session_focus_context_receipt(
    session_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    focus = session_metadata.get("active_focus")
    if not isinstance(focus, dict):
        return None

    focus_id = str(focus.get("id", "")).strip()
    focus_summary = str(focus.get("summary", "")).strip()
    source = (
        str(focus.get("source", "direct_user_instruction")).strip()
        or "direct_user_instruction"
    )
    persistence = (
        str(focus.get("persistence", "session-only")).strip() or "session-only"
    )
    if not focus_id or not focus_summary:
        return None

    return {
        "compact": (
            f"Context receipt: Active Focus {focus_id} "
            f"(source={source}; persistence={persistence})."
        ),
        "context_receipts": [
            {
                "layer": "active_focus",
                "record_id": focus_id,
                "source": source,
                "persistence": persistence,
                "status": "active",
            }
        ],
        "record_ids": [focus_id],
    }


def merge_focus_context_receipt(
    base_receipt: dict[str, Any] | None,
    session_metadata: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base_receipt or {})
    focus_receipt = session_focus_context_receipt(session_metadata)
    if focus_receipt is None:
        return merged

    existing_contexts = list(merged.get("context_receipts", []))
    if not any(
        isinstance(item, dict) and str(item.get("layer", "")).lower() == "active_focus"
        for item in existing_contexts
    ):
        existing_contexts.extend(list(focus_receipt.get("context_receipts", [])))
    merged["context_receipts"] = existing_contexts

    existing_ids = list(merged.get("record_ids", []))
    for record_id in list(focus_receipt.get("record_ids", [])):
        if record_id not in existing_ids:
            existing_ids.append(record_id)
    merged["record_ids"] = existing_ids

    focus_compact = str(focus_receipt.get("compact", "")).strip()
    base_compact = str(merged.get("compact", "")).strip()
    if focus_compact and focus_compact not in base_compact:
        merged["compact"] = (
            f"{base_compact} | {focus_compact}" if base_compact else focus_compact
        )

    return merged


def active_focus_guided_context_receipt(focus_id: str) -> dict[str, Any]:
    return {
        "compact": (
            f"Focus: {focus_id}; Memory: learning-signals; "
            "Knowledge: communication-workflow; Model: policy_only; "
            "Proof: active_focus_guided"
        ),
        "context_receipts": [
            {
                "layer": "active_focus",
                "record_id": focus_id,
                "FocusApplied": True,
                "Mode": "communication_workflow_learning",
            }
        ],
        "record_ids": [focus_id],
    }
