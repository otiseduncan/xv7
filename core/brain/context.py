from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from core.brain.schema import BrainLayer, BrainRecord


_LAYER_ORDER: list[BrainLayer] = [
    BrainLayer.SYSTEM_PROMPT,
    BrainLayer.ACTIVE_FOCUS,
    BrainLayer.KNOWLEDGE,
    BrainLayer.MEMORY,
    BrainLayer.VERIFIED_STATUS,
]


class BrainContext(BaseModel):
    """Assembled active brain context plus compact provenance receipt."""

    model_config = ConfigDict(extra="forbid")

    prompt: str
    receipt: dict[str, object]


class BrainContextAssembler:
    """Build compact, layer-aware prompt context from active records."""

    _LAYER_LABELS: dict[BrainLayer, str] = {
        BrainLayer.SYSTEM_PROMPT: "System Prompt",
        BrainLayer.ACTIVE_FOCUS: "Active Focus",
        BrainLayer.KNOWLEDGE: "Knowledge",
        BrainLayer.MEMORY: "Memory",
        BrainLayer.VERIFIED_STATUS: "Verified Status",
    }

    def assemble(
        self,
        records: list[BrainRecord],
        *,
        target_layers: list[BrainLayer] | None = None,
    ) -> BrainContext:
        layers = target_layers[:] if target_layers is not None else _LAYER_ORDER[:]
        by_layer: dict[BrainLayer, list[BrainRecord]] = {layer: [] for layer in layers}
        for record in records:
            if record.layer in by_layer:
                by_layer[record.layer].append(record)

        sections: list[str] = [
            "--- XV7 ACTIVE CONTEXT ---",
            "Use only these records for factual grounding.",
            "If a needed record is missing, state exactly what is missing.",
            "Do not claim hidden memory. Do not invent verification.",
        ]

        selected: list[BrainRecord] = []
        missing_layers: list[str] = []

        for layer in layers:
            layer_records = sorted(by_layer.get(layer, []), key=lambda r: (-r.priority, r.record_id))
            if not layer_records:
                missing_layers.append(layer.value)
                sections.append(f"[{layer.value}] MISSING")
                continue

            if layer in (BrainLayer.SYSTEM_PROMPT, BrainLayer.ACTIVE_FOCUS):
                layer_records = layer_records[:1]

            selected.extend(layer_records)
            sections.append(f"[{layer.value}]")
            for record in layer_records:
                sections.append(f"- {record.record_id}: {record.summary}")
                for fact in record.facts:
                    sections.append(
                        f"  * {fact.statement} (source={fact.source_type})"
                    )

        sections.append("--- END XV7 ACTIVE CONTEXT ---")

        source_counts: Counter[str] = Counter()
        for record in selected:
            for fact in record.facts:
                source_counts[fact.source_type] += 1

        compact_parts: list[str] = []
        for layer in layers:
            layer_selected = [r for r in selected if r.layer == layer]
            if layer_selected:
                joined = ", ".join(r.record_id for r in layer_selected)
                compact_parts.append(f"{self._LAYER_LABELS[layer]} {joined}")
            else:
                compact_parts.append(f"{self._LAYER_LABELS[layer]} missing")

        receipt: dict[str, object] = {
            "version": "xv7-brain-b4",
            "record_ids": [r.record_id for r in selected],
            "missing_layers": missing_layers,
            "layer_counts": {
                layer.value: len([r for r in selected if r.layer == layer])
                for layer in layers
            },
            "memory_source_counts": dict(source_counts),
            "compact": "Context receipt: " + "; ".join(compact_parts) + ".",
        }

        return BrainContext(prompt="\n".join(sections), receipt=receipt)
