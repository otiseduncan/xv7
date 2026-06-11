from __future__ import annotations

from pathlib import Path
import re

from core.brain.context import BrainContext, BrainContextAssembler
from core.brain.records import BrainRecordLoader
from core.brain.schema import BrainLayer, BrainRecord


class BrainContextManager:
    """Facade for loading active records and assembling runtime context."""

    def __init__(self, records_dir: Path | None = None) -> None:
        self.loader = BrainRecordLoader(records_dir=records_dir)
        self.assembler = BrainContextAssembler()

    def build_active_context(self) -> BrainContext:
        records = self.loader.load_active_records()
        return self.assembler.assemble(records)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.lower().strip().split())

    @staticmethod
    def _highest_priority_by_layer(records: list[BrainRecord]) -> dict[BrainLayer, BrainRecord]:
        result: dict[BrainLayer, BrainRecord] = {}
        for record in records:
            current = result.get(record.layer)
            if current is None or record.priority > current.priority:
                result[record.layer] = record
        return result

    def select_relevant_layers(self, question: str) -> list[BrainLayer]:
        normalized = self._normalize_question(question)

        if normalized in {"who are you?", "who are you"}:
            return [BrainLayer.SYSTEM_PROMPT]

        if normalized in {"what are we working on?", "what are we working on"}:
            return [BrainLayer.ACTIVE_FOCUS]

        if normalized in {
            "what do you know is verified?",
            "what do you know is verified",
            "what repo/status are we on?",
            "what repo/status are we on",
        }:
            return [BrainLayer.VERIFIED_STATUS]

        layers: list[BrainLayer] = [BrainLayer.SYSTEM_PROMPT]
        if re.search(r"\b(work|working|focus|task|priority)\b", normalized):
            layers.append(BrainLayer.ACTIVE_FOCUS)
        if re.search(r"\b(verified|prove|proof|repo|branch|status|sync|synced)\b", normalized):
            layers.append(BrainLayer.VERIFIED_STATUS)
        if re.search(r"\b(remember|memory|prefer|preference|asked|request)\b", normalized):
            layers.append(BrainLayer.MEMORY)
        if re.search(r"\b(architecture|component|service|system|how)\b", normalized):
            layers.append(BrainLayer.KNOWLEDGE)

        if layers == [BrainLayer.SYSTEM_PROMPT]:
            layers.append(BrainLayer.KNOWLEDGE)

        deduped: list[BrainLayer] = []
        for layer in layers:
            if layer not in deduped:
                deduped.append(layer)
        return deduped

    def build_context_for_question(self, question: str) -> BrainContext:
        records = self.loader.load_active_records()
        layer_map = self._highest_priority_by_layer(records)
        selected_layers = self.select_relevant_layers(question)
        selected_records = [
            layer_map[layer] for layer in selected_layers if layer in layer_map
        ]
        return self.assembler.assemble(
            selected_records,
            target_layers=selected_layers,
        )

    def answer_from_records(self, question: str) -> str | None:
        """Return deterministic answers for core B4 context checks.

        Returns None when the question is outside the supported B4 pass set.
        """
        normalized = self._normalize_question(question)
        records = self.loader.load_active_records()

        layer_map = self._highest_priority_by_layer(records)
        system = layer_map.get(BrainLayer.SYSTEM_PROMPT)
        focus = layer_map.get(BrainLayer.ACTIVE_FOCUS)
        verified = layer_map.get(BrainLayer.VERIFIED_STATUS)

        if normalized in {"who are you?", "who are you"}:
            if system is None:
                return "Missing required record: system_prompt."
            return system.facts[0].statement if system.facts else system.summary

        if normalized in {"what are we working on?", "what are we working on"}:
            if focus is None:
                return "Missing required record: active_focus."
            return focus.summary

        if normalized in {
            "what do you know is verified?",
            "what do you know is verified",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            verified_facts = [f.statement for f in verified.facts]
            if not verified_facts:
                return "Verified status record is present but has no facts."
            joined = " ".join(f"- {item}" for item in verified_facts)
            return f"Verified facts: {joined}"

        if normalized in {"what repo/status are we on?", "what repo/status are we on"}:
            if verified is None:
                return "Missing required record: verified_status."

            repo_items = []
            for fact in verified.facts:
                text = fact.statement.lower()
                if (
                    "repo path" in text
                    or "branch" in text
                    or "synced" in text
                    or "start_xv7_local.ps1" in text
                    or "operator_readiness_report.py" in text
                ):
                    repo_items.append(fact.statement)

            if not repo_items:
                return "Verified status is present but repo/status details are missing."

            return "Repo/status: " + " ".join(f"- {item}" for item in repo_items)

        return None
