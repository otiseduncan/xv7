from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Callable


def runtime_clock_timezone() -> ZoneInfo | timezone:
    configured = (
        os.getenv("XV7_LOCAL_TIMEZONE") or os.getenv("TZ") or "America/New_York"
    ).strip()
    try:
        return ZoneInfo(configured)
    except Exception:
        return timezone.utc


def runtime_clock_now() -> datetime:
    return datetime.now(runtime_clock_timezone())


def format_runtime_date(now: datetime) -> str:
    return f"{now.strftime('%A, %B')} {now.day}, {now.year}"


def format_runtime_time(now: datetime) -> str:
    hour = now.hour % 12 or 12
    return f"{hour}:{now.minute:02d} {now.strftime('%p')}"


def runtime_clock_system_prompt() -> str:
    now = runtime_clock_now()
    tz_name = getattr(now.tzinfo, "key", None) or str(now.tzinfo or "UTC")
    return (
        "--- RUNTIME CLOCK ---\n"
        f"Current runtime date/time: {format_runtime_date(now)} at {format_runtime_time(now)} ({tz_name}).\n"
        "Use this date when answering current date, day, today, tomorrow, yesterday, or schedule questions.\n"
        "Do not infer a different date from memory or prior conversation.\n"
        "---------------------"
    )


def is_runtime_clock_question(
    question: str,
    *,
    normalize_intent_text: Callable[[str], str],
) -> bool:
    normalized = normalize_intent_text(question).strip(" .!?")
    direct_questions = {
        "what is today's date",
        "what is todays date",
        "what date is it",
        "what is the date",
        "what day is it",
        "what day is today",
        "what is today",
        "tell me today's date",
        "tell me todays date",
        "current date",
        "today date",
    }
    if normalized in direct_questions:
        return True
    return bool(
        re.search(
            r"\b(today'?s? date|current date|what date|what day is it|what day is today)\b",
            normalized,
        )
    )


def runtime_clock_answer() -> tuple[str, dict[str, Any]]:
    now = runtime_clock_now()
    tz_name = getattr(now.tzinfo, "key", None) or str(now.tzinfo or "UTC")
    visible_text = f"Today's date is {format_runtime_date(now)} ({tz_name})."
    context_receipt = {
        "compact": f"Context receipt: Runtime clock ({tz_name}).",
        "context_receipts": [
            {
                "layer": "runtime_clock",
                "record_id": "RUNTIME-CLOCK",
                "source": "server_clock",
                "status": "active",
                "timezone": tz_name,
            }
        ],
        "record_ids": ["RUNTIME-CLOCK"],
    }
    return visible_text, context_receipt
