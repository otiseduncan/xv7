from __future__ import annotations

import re

from core.brain.schema import BrainLayer, BrainRecord


def layer_token(layer: BrainLayer) -> str:
    return {
        BrainLayer.MEMORY: "MEMORY",
        BrainLayer.KNOWLEDGE: "KNOWLEDGE",
        BrainLayer.VERIFIED_STATUS: "VERIFIED",
        BrainLayer.ACTIVE_FOCUS: "FOCUS",
        BrainLayer.SYSTEM_PROMPT: "SYSTEM",
    }[layer]


def next_record_id_for_layer(layer: BrainLayer, records: list[BrainRecord]) -> str:
    token = layer_token(layer)
    max_index = 0
    for record in records:
        match = re.match(rf"^XV7-{token}-(\d{{4}})$", record.record_id)
        if match is None:
            continue
        max_index = max(max_index, int(match.group(1)))
    return f"XV7-{token}-{max_index + 1:04d}"
