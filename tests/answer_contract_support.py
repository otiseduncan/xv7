from __future__ import annotations

import asyncio
from typing import Any

from core.brain.answer_contract import AnswerContract
from core.brain.manager import BrainContextManager
from core.brain.schema import BrainLayer
from core.runtime.model_registry import RuntimeRoleModelResolution


def _layer_map() -> dict[BrainLayer, object]:
    manager = BrainContextManager()
    records = manager.loader.load_active_records()
    return manager._highest_priority_by_layer(records)






























































































































def _artifact_session_messages(
    *, filename: str = "index.html", content: str
) -> list[dict[str, object]]:
    return [
        {
            "role": "assistant",
            "content": "Here is a draft HTML artifact for index.html.",
            "metadata": {
                "code_artifact": {
                    "type": "code_artifact",
                    "filename": filename,
                    "language": "html",
                    "previewable": True,
                    "applied": False,
                    "content": content,
                    "artifact_id": "soggy-doggy-artifact",
                    "revision_id": "soggy-doggy-artifact:r1",
                    "revision_number": 1,
                },
                "policy_provenance": {
                    "artifact_generation": "local_model",
                    "revision_number": 1,
                },
            },
        }
    ]


























# ─── Code 21: site_bundle tests ────────────────────────────────────────────────









































__all__ = [name for name in globals() if not name.startswith("__")]
