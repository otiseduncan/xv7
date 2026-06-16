from __future__ import annotations

import re
from typing import Any


def auto_memory_prompt_from_metadata(metadata: dict[str, Any]) -> str:
    prompt = metadata.get("auto_memory_context_prompt")
    return prompt.strip() if isinstance(prompt, str) else ""


def auto_memory_receipt_from_metadata(metadata: dict[str, Any]) -> str | None:
    receipt = metadata.get("auto_memory_context_receipt")
    if isinstance(receipt, str) and receipt.strip():
        return receipt.strip()
    return None


def auto_memory_hints_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    hints = metadata.get("auto_memory_hints")
    return hints if isinstance(hints, dict) else {}


def build_assistant_payload(
    *,
    visible_text: str,
    context_receipt: dict[str, Any] | None = None,
    operator_receipts: list[dict[str, Any]] | None = None,
    operator_result: dict[str, Any] | None = None,
    memory_receipts: list[str] | None = None,
    model_use_receipt: dict[str, Any] | None = None,
    policy_provenance: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    action_history_refs: list[str] | None = None,
    code_artifact: dict[str, Any] | None = None,
    code_artifacts: list[dict[str, Any]] | None = None,
    artifact_patch_proposal: dict[str, Any] | None = None,
    site_bundle: dict[str, Any] | None = None,
    site_bundle_patch_proposals: list[dict[str, Any]] | None = None,
    commit_proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deduped_memory_receipts: list[str] = []
    seen_memory_receipts: set[str] = set()
    for receipt in memory_receipts or []:
        key = str(receipt).strip()
        if not key or key in seen_memory_receipts:
            continue
        seen_memory_receipts.add(key)
        deduped_memory_receipts.append(key)

    return {
        "visible_text": visible_text,
        "context_receipt": context_receipt or {},
        "operator_receipts": operator_receipts or [],
        "operator_result": operator_result or {},
        "memory_receipts": deduped_memory_receipts,
        "model_use_receipt": model_use_receipt or {},
        "policy_provenance": policy_provenance or {},
        "warnings": warnings or [],
        "action_history_refs": action_history_refs or [],
        "code_artifact": code_artifact or {},
        "code_artifacts": code_artifacts or [],
        "artifact_patch_proposal": artifact_patch_proposal or {},
        "site_bundle": site_bundle or {},
        "site_bundle_patch_proposals": site_bundle_patch_proposals or [],
        "commit_proposal": commit_proposal or {},
    }


def sanitize_visible_answer_text(text: str) -> str:
    """Remove receipt/debug lines from user-visible assistant text."""
    if not text:
        return ""

    text = re.sub(r"\*\*sources\*\*\s*:\s*.*$", "", str(text), flags=re.IGNORECASE)
    text = re.sub(r"\bsources\s*:\s*.*$", "", text, flags=re.IGNORECASE)

    blocked_prefixes = (
        "operator receipt:",
        "context receipt:",
        "memory receipt:",
        "model receipt:",
        "sources:",
        "**sources**:",
        "- *xv7-",
        "- xv7-",
    )
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith(blocked_prefixes):
            continue
        cleaned_lines.append(raw_line)

    return "\n".join(cleaned_lines).strip()
