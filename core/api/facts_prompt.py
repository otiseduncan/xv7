from __future__ import annotations

import json
from typing import Any


def build_facts_system_prompt(facts: dict[str, Any]) -> str:
    if not facts:
        return ""

    pretty = json.dumps(facts, ensure_ascii=False, indent=2)
    return (
        "--- PERSISTENT SESSION MEMORY ---\n"
        "These facts are your long-term knowledge base for this specific session.\n"
        "Do not explain that you have this memory; simply use the information.\n"
        f"{pretty}\n"
        "----------------------------------\n"
    )
