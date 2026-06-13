from __future__ import annotations

import re
from typing import Any


class SessionSignalManager:
    """Pure helpers for session, operator, and model-use signals."""

    @staticmethod
    def facts(record: Any | None) -> list[str]:
        if record is None:
            return []
        return [fact.statement for fact in record.facts]

    @staticmethod
    def extract_user_name(record: Any | None) -> str | None:
        if record is None:
            return None

        for fact in record.facts:
            text = fact.statement.strip()
            lowered = text.lower()
            if "otis duncan" in lowered:
                return "Otis Duncan"
            if lowered.startswith("the user/operator is "):
                value = text.split("is", 1)[-1].strip().strip(".")
                if value:
                    return value
        return None

    @staticmethod
    def active_focus_summary(session_metadata: dict[str, Any]) -> str | None:
        focus_payload = session_metadata.get("active_focus")
        if isinstance(focus_payload, dict):
            summary = str(focus_payload.get("summary", "")).strip()
            if summary:
                return summary
        if isinstance(focus_payload, str):
            summary = focus_payload.strip()
            if summary:
                return summary
        return None

    @staticmethod
    def normalize_reminder_request(question: str) -> str:
        text = re.sub(r"\s+", " ", question.strip())
        text = re.sub(
            r"^(please\s+)?(set|create|add)\s+(me\s+)?(a\s+)?reminder\s+(for|to)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"^(please\s+)?remind me\s+(to\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = text.strip(" .")
        if not text:
            return "your requested reminder details"
        text = re.sub(r"(?i)\ba\.m\.", "AM", text)
        text = re.sub(r"(?i)\bp\.m\.", "PM", text)
        text = re.sub(
            r"\bat\s+(\d{1,2}:\d{2})\s*(AM|PM)\s+to\s+",
            r"at \1 \2 — ",
            text,
            flags=re.IGNORECASE,
        )
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    @staticmethod
    def has_live_repo_check_proof(session_metadata: dict[str, Any]) -> bool:
        proof = session_metadata.get("live_repo_check")
        if isinstance(proof, bool):
            return proof

        checks = session_metadata.get("tool_results")
        if isinstance(checks, list):
            for item in checks:
                if (
                    isinstance(item, dict)
                    and str(item.get("type", "")).lower() == "repo_check"
                ):
                    return True
        return False

    @staticmethod
    def latest_model_tag(session_metadata: dict[str, Any]) -> str | None:
        receipt = session_metadata.get("model_use_receipt")
        if not isinstance(receipt, dict):
            return None

        selection_source = str(receipt.get("model_selection_source", "")).lower()
        if selection_source in {"brain_records", "brain_policy", "policy_only"}:
            return None

        tag = receipt.get("model_tag")
        if not isinstance(tag, str) or not tag.strip():
            return None
        cleaned = tag.strip()
        if cleaned.lower() == "xv7-brain-records":
            return None
        return cleaned

    @staticmethod
    def last_verified_operator_model(record: Any | None) -> str | None:
        if record is None:
            return None

        for fact in record.facts:
            lowered = fact.statement.lower()
            if (
                "operator readiness" not in lowered
                and "operator_readiness_report" not in lowered
            ):
                continue

            match = re.search(r"\b([a-z0-9_.-]+:[a-z0-9_.-]+)\b", fact.statement)
            if match:
                return match.group(1)
        return None
