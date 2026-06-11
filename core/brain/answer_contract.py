from __future__ import annotations

import re
from typing import Any

from core.brain.schema import BrainLayer, BrainRecord


class AnswerContract:
    """Conversation quality guardrails for proof-aware record-grounded answers."""

    @staticmethod
    def _normalize(question: str) -> str:
        return " ".join(question.lower().strip().split())

    @staticmethod
    def _latest_model_tag(session_metadata: dict[str, Any]) -> str | None:
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
    def _last_verified_operator_model(verified: BrainRecord | None) -> str | None:
        if verified is None:
            return None

        for fact in verified.facts:
            lowered = fact.statement.lower()
            if "operator readiness" not in lowered and "operator_readiness_report" not in lowered:
                continue

            match = re.search(r"\b([a-z0-9_.-]+:[a-z0-9_.-]+)\b", fact.statement)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _has_live_repo_check_proof(session_metadata: dict[str, Any]) -> bool:
        proof = session_metadata.get("live_repo_check")
        if isinstance(proof, bool):
            return proof

        checks = session_metadata.get("tool_results")
        if isinstance(checks, list):
            for item in checks:
                if isinstance(item, dict) and str(item.get("type", "")).lower() == "repo_check":
                    return True
        return False

    @staticmethod
    def _facts(record: BrainRecord | None) -> list[str]:
        if record is None:
            return []
        return [fact.statement for fact in record.facts]

    @staticmethod
    def _find_layer_record(
        records_by_layer: dict[BrainLayer, BrainRecord], layer: BrainLayer
    ) -> BrainRecord | None:
        return records_by_layer.get(layer)

    def try_answer(
        self,
        question: str,
        *,
        records_by_layer: dict[BrainLayer, BrainRecord],
        session_metadata: dict[str, Any],
    ) -> str | None:
        normalized = self._normalize(question)

        system = self._find_layer_record(records_by_layer, BrainLayer.SYSTEM_PROMPT)
        focus = self._find_layer_record(records_by_layer, BrainLayer.ACTIVE_FOCUS)
        knowledge = self._find_layer_record(records_by_layer, BrainLayer.KNOWLEDGE)
        memory = self._find_layer_record(records_by_layer, BrainLayer.MEMORY)
        verified = self._find_layer_record(records_by_layer, BrainLayer.VERIFIED_STATUS)

        if normalized in {"who are you?", "who are you"}:
            if system is None:
                return "Missing required record: system_prompt."
            identity = self._facts(system)
            return identity[0] if identity else system.summary

        if normalized in {
            "what are we working on?",
            "what are we working on",
            "what are we working on right now?",
            "what are we working on right now",
        }:
            if focus is None:
                return "Missing required record: active_focus."
            return focus.summary

        if normalized in {
            "what do you know is verified?",
            "what do you know is verified",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            facts = self._facts(verified)
            if not facts:
                return "Verified status record is present but has no facts."
            return "Verified facts: " + " ".join(f"- {item}" for item in facts)

        if normalized in {"what repo/status are we on?", "what repo/status are we on"}:
            if verified is None:
                return "Missing required record: verified_status."

            repo_facts = []
            for fact in self._facts(verified):
                lower = fact.lower()
                if (
                    "repo path" in lower
                    or "branch" in lower
                    or "synced" in lower
                    or "start_xv7_local.ps1" in lower
                    or "operator_readiness_report.py" in lower
                ):
                    repo_facts.append(fact)

            if not repo_facts:
                return "Verified status is present but repo/status details are missing."
            return "Repo/status: " + " ".join(f"- {item}" for item in repo_facts)

        if normalized in {"are we beta ready?", "are we beta ready"}:
            if verified is None:
                return "Missing required record: verified_status."
            verified_facts = self._facts(verified)
            has_beta_ready_proof = any(
                "beta-ready" in fact.lower() or "beta ready" in fact.lower()
                for fact in verified_facts
            )
            if has_beta_ready_proof:
                return "Verified: XV7 has explicit beta-ready proof in loaded verified records."

            focus_text = (
                focus.summary
                if focus is not None
                else "active focus record is not loaded"
            )
            return (
                "I do not have proof that XV7 is beta-ready yet. "
                "Verified: launch and operator readiness proofs are passing. "
                f"Current focus: {focus_text}. "
                "Unverified: a beta-ready declaration is not present in loaded verified status records."
            )

        if normalized in {"did you check the repo?", "did you check the repo"}:
            if self._has_live_repo_check_proof(session_metadata):
                return "I have proof of a live repo check in this session."
            return (
                "I do not have proof of a live repo check in this session. "
                "I can answer only from loaded verified records unless a repo-check result is provided."
            )

        if normalized in {"what failed?", "what failed"}:
            if verified is None:
                return "Missing required record: verified_status."
            failure_facts = []
            for fact in self._facts(verified):
                lower = fact.lower()
                if any(token in lower for token in ("failed", "failure", "error")):
                    failure_facts.append(fact)
            if not failure_facts:
                return "No current failure record is loaded in Verified Status."
            return "Recorded failures: " + " ".join(f"- {item}" for item in failure_facts)

        if normalized in {"what do you remember?", "what do you remember"}:
            if memory is None:
                return "Missing required record: memory."
            memory_facts = self._facts(memory)
            if not memory_facts:
                return "Memory record is loaded but contains no memory facts."
            return "Memory facts: " + " ".join(f"- {item}" for item in memory_facts)

        if "guess" in normalized:
            focus_hint = focus.summary if focus is not None else "current focus is missing"
            return (
                "Guess (unverified): a reasonable next step is to continue from the current focus "
                f"and harden what remains. Context hint: {focus_hint}."
            )

        if normalized in {"what model are you using?", "what model are you using"}:
            tag = self._latest_model_tag(session_metadata)
            if tag is None:
                last_verified = self._last_verified_operator_model(verified)
                if last_verified is not None:
                    return (
                        "I do not have proof of the current runtime model from this response. "
                        "The answer was handled by the brain/policy layer, not proven model inference. "
                        f"The last verified operator readiness proof used {last_verified}, "
                        "but that does not prove this exact response used it."
                    )
                return (
                    "I do not have proof of the current runtime model from this response. "
                    "The answer was handled by the brain/policy layer, not proven model inference."
                )
            return f"From the latest model-use receipt, the model tag is {tag}."

        if normalized in {
            "what model was proven during operator readiness?",
            "what model was proven during operator readiness",
        }:
            proved = self._last_verified_operator_model(verified)
            if proved is None:
                return "No verified operator readiness model proof is loaded."
            return (
                f"The last verified operator readiness proof used {proved}. "
                "That proves the readiness proof run, not necessarily this exact response."
            )

        if knowledge is None and any(
            token in normalized for token in ("architecture", "system", "how does xv7")
        ):
            return "Missing required record: knowledge."

        return None
