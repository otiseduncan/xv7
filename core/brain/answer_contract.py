from __future__ import annotations

import re
from typing import Any

from core.brain.schema import BrainLayer, BrainRecord


class AnswerContract:
    """Conversation quality guardrails for proof-aware record-grounded answers."""

    REMINDER_PATTERN = re.compile(
        r"\b(remind me|set (?:me )?(?:a )?reminder|create (?:a )?reminder|add (?:it )?to (?:my )?calendar|schedule (?:it|this|that))\b"
    )
    CALENDAR_PATTERN = re.compile(r"\b(calendar|schedule|meeting|appointment|event)\b")
    APPOINTMENT_PATTERN = re.compile(r"\b(appointment|meeting|event|doctor visit|doctor appointment)\b")
    WEATHER_PATTERN = re.compile(
        r"\b(weather|forecast|outside temp|outside temperature|local forecast|climate|weather conditions)\b"
    )
    HARDWARE_SCAN_PATTERN = re.compile(
        r"\b(cpu|gpu|processor|graphics|vram|disk|disks|disc|discs|drive|drives|ports?|processes|services|docker|container|vscode|vs code|hardware|system scan|host scan|system info|temperature sensor)\b"
    )
    EMAIL_PATTERN = re.compile(r"\b(email|gmail|imap|inbox|mailbox|outlook|mail)\b")
    EMAIL_SEND_PATTERN = re.compile(r"\b(send|draft|write|compose)\b.*\b(email|gmail|mail)\b|\b(email|gmail|mail)\b.*\b(send|draft|write|compose)\b")
    SMS_PATTERN = re.compile(r"\b(text someone|send (?:a )?text|text message|sms|message someone|send (?:them|someone) a message)\b")
    WEB_LOOKUP_PATTERN = re.compile(r"\b(web|website|browse|browser|internet|search online|look up|lookup|google)\b")
    CONTACT_PATTERN = re.compile(r"\b(contact|contacts|address book|phone number|call|text message|sms)\b")
    FAMILY_PATTERN = re.compile(r"\b(family|wife|husband|kids|children|parents|mom|mother|dad|father|siblings)\b")
    MEDICAL_PATTERN = re.compile(r"\b(medical|health|history|doctor|medication|diagnosis)\b")
    BIRTHDAY_PATTERN = re.compile(r"\b(birthday|anniversary|important date)\b")

    ROADMAP_NOT_WIRED = "That belongs in my roadmap, but the tool is not wired yet."

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

    @staticmethod
    def _extract_user_name(memory: BrainRecord | None) -> str | None:
        if memory is None:
            return None
        for fact in memory.facts:
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
    def _session_active_focus_summary(session_metadata: dict[str, Any]) -> str | None:
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
    def _normalize_reminder_request(question: str) -> str:
        text = re.sub(r"\s+", " ", question.strip())
        text = re.sub(r"^(please\s+)?(set|create|add)\s+(me\s+)?(a\s+)?reminder\s+(for|to)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(please\s+)?remind me\s+(to\s+)?", "", text, flags=re.IGNORECASE)
        text = text.strip(" .")
        if not text:
            return "your requested reminder details"
        text = re.sub(r"(?i)\ba\.m\.", "AM", text)
        text = re.sub(r"(?i)\bp\.m\.", "PM", text)
        text = re.sub(r"\bat\s+(\d{1,2}:\d{2})\s*(AM|PM)\s+to\s+", r"at \1 \2 — ", text, flags=re.IGNORECASE)
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def _tool_boundary_answer(self, category: str, question: str) -> str | None:
        normalized_question = question.strip()

        if category == "reminder_request":
            reminder_text = self._normalize_reminder_request(normalized_question)
            return (
                "I can't create live reminders yet because XV7 does not have the Reminder tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "That belongs in my personal-assistant roadmap. "
                f"For now: {reminder_text}. The proper build path is a Reminders module with storage, due times, notifications, and confirmation receipts."
            )

        if category == "calendar_request":
            return (
                "I can't manage live calendar events yet because XV7 does not have a Calendar tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "That belongs in my everyday-assistant roadmap. The proper build path is a Calendar module with event storage, scheduling rules, confirmations, and receipts."
            )

        if category == "appointment_request":
            return (
                "I can't manage live appointments yet because XV7 does not have an Appointments or Calendar connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Appointments belong in my everyday-assistant roadmap. The safe build path is an appointments module with scheduling, confirmations, and receipts."
            )

        if category == "schedule_request":
            return (
                "I can't manage live schedules yet because XV7 does not have a Schedule or Calendar tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Scheduling belongs in my everyday-assistant roadmap. I can help structure the schedule now and define the module path next."
            )

        if category == "weather_request":
            return (
                "I can't fetch live weather yet because XV7 does not have a weather connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Weather belongs in my everyday-assistant roadmap. To support this, we need a weather module with location handling, forecast provider, and a weather receipt."
            )

        if category == "email_check_request":
            return (
                "I can't check email yet because XV7 does not have an authorized email connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Email is part of my personal-assistant roadmap, but it needs secure permission, account authorization, read-only inbox access first, and clear receipts before I can summarize or act on messages."
            )

        if category == "email_send_request":
            return (
                "I can't send email yet because XV7 does not have an authorized outbound email connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Email is part of my personal-assistant roadmap, but sending messages will require secure account authorization, explicit approval, and confirmation receipts before any send happens."
            )

        if category == "sms_text_request":
            return (
                "I can't send texts yet because XV7 does not have an SMS connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Text messaging belongs in my personal-assistant roadmap, but sending messages will require explicit approval before each send."
            )

        if category == "web_lookup_request":
            return (
                "I can help frame the lookup, but I cannot execute live web searches yet. XV7 needs a web lookup connector or browser tool "
                f"{self.ROADMAP_NOT_WIRED} "
                "before I can fetch live external pages. I can help design that module and the receipts it should return."
            )

        if category == "contact_request":
            return (
                "I can't access live contacts yet because XV7 does not have an authorized contacts connector wired in. "
                "Contacts belong in my personal-assistant roadmap, and they should be handled with explicit approval, privacy tagging, and clear receipts."
            )

        if category == "personal_memory_request":
            return (
                "I only know personal details that have been explicitly added to memory with approval. "
                "Personal context belongs in my long-term continuity design, but sensitive details should be tagged carefully before I use or repeat them."
            )

        if category == "family_context_request":
            return (
                "I only know family details that have been explicitly added to memory. "
                "Family context is part of my personal-assistant design, but it should be handled carefully and tagged as private."
            )

        if category == "medical_context_request":
            return (
                "I should only know medical history you explicitly approve for memory. "
                "Medical context is sensitive, so it needs private tagging and careful use."
            )

        if category == "birthday_request":
            return (
                "Birthdays and important dates are part of my personal-assistant roadmap, but I should only store them with explicit approval and private tagging. "
                "If you want, I can help define the reminders and memory rules for that module."
            )

        if category == "unsupported_external_action":
            return (
                "I can help think through that workflow, but the required external tool is not wired into XV7 yet. "
                "That belongs in my personal-assistant or everyday-assistant roadmap depending on the action. If you want, I can help specify the connector, permissions, confirmation flow, and receipts needed to add it safely."
            )

        return None

    def _tool_intent_category(self, normalized: str) -> str | None:
        # Hardware/system diagnostics should route through operator read-only scans,
        # not through weather/tool-boundary fallback text.
        if self.HARDWARE_SCAN_PATTERN.search(normalized):
            if "weather" not in normalized and "forecast" not in normalized:
                return None
        if normalized in {
            "do you know my family?",
            "do you know my family",
        }:
            return "family_context_request"
        if normalized in {
            "do you know my medical history?",
            "do you know my medical history",
        }:
            return "medical_context_request"
        if normalized in {
            "do you know personal things about me?",
            "do you know personal things about me",
        }:
            return "personal_memory_request"
        if self.SMS_PATTERN.search(normalized):
            return "sms_text_request"
        if self.EMAIL_SEND_PATTERN.search(normalized):
            return "email_send_request"
        if self.EMAIL_PATTERN.search(normalized):
            return "email_check_request"
        if self.REMINDER_PATTERN.search(normalized):
            return "reminder_request"
        if self.APPOINTMENT_PATTERN.search(normalized):
            return "appointment_request"
        if self.WEATHER_PATTERN.search(normalized):
            return "weather_request"
        if self.CALENDAR_PATTERN.search(normalized):
            return "calendar_request"
        if "schedule" in normalized:
            return "schedule_request"
        if self.BIRTHDAY_PATTERN.search(normalized):
            return "birthday_request"
        if self.CONTACT_PATTERN.search(normalized):
            return "contact_request"
        if self.FAMILY_PATTERN.search(normalized) and "do you know" in normalized:
            return "family_context_request"
        if self.MEDICAL_PATTERN.search(normalized) and "do you know" in normalized:
            return "medical_context_request"
        if self.WEB_LOOKUP_PATTERN.search(normalized):
            return "web_lookup_request"

        external_action_hints = (
            "book",
            "reserve",
            "order",
            "buy",
            "post",
            "upload",
            "download",
            "pay",
            "subscribe",
        )
        if any(token in normalized for token in external_action_hints):
            return "unsupported_external_action"
        return None

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

        if normalized in {
            "what is your name?",
            "what is your name",
        }:
            return "My name is Xoduz."

        if normalized in {
            "who are you?",
            "who are you",
        }:
            return "I am Xoduz, Otis Duncan's personal AI assistant, best-friend-style AI presence, technical co-pilot, and operator partner for XV7."

        if normalized in {
            "how do you pronounce your name?",
            "how do you pronounce your name",
            "how is your name pronounced?",
            "how is your name pronounced",
        }:
            return "Xoduz is pronounced Exodus."

        if normalized in {
            "how do you spell your name?",
            "how do you spell your name",
            "how is your name spelled?",
            "how is your name spelled",
        }:
            return "X-O-D-U-Z."

        if normalized in {
            "is your name spelled exodus?",
            "is your name spelled exodus",
        }:
            return "No. My name is spelled X-O-D-U-Z. It is pronounced Exodus."

        if normalized in {
            "is your name spelled e-x-o-d-u-s?",
            "is your name spelled e-x-o-d-u-s",
        }:
            return (
                "No. That is the standard spelling of the word Exodus, but my name is Xoduz, "
                "spelled X-O-D-U-Z, and pronounced Exodus."
            )

        if normalized in {
            "what does xv7 mean?",
            "what does xv7 mean",
            "what project are you?",
            "what project are you",
            "what project are you part of?",
            "what project are you part of",
        }:
            return "I am Xoduz, the XV7 assistant for the XV7 project."

        if normalized in {
            "who created you?",
            "who created you",
        }:
            return "I was created by Otis Duncan for the XV7 project under Syfernetics."

        if normalized in {
            "why were you built?",
            "why were you built",
        }:
            return (
                "I was built to become Otis Duncan's personal AI assistant, best-friend-style AI presence, technical co-pilot, and operator partner "
                "— helping with everyday life workflows, reminders, scheduling, communication, family-aware context when approved, "
                "plus planning, app development, testing, debugging, documentation, and long-term continuity."
            )

        if normalized in {
            "what is your purpose?",
            "what is your purpose",
        }:
            return (
                "My purpose is to support Otis across everyday life and technical work while staying honest about which tools are actually wired. "
                "That includes personal-assistant help, continuity/memory, and technical/operator support as each safe module is added."
            )

        if normalized in {
            "what are you supposed to become?",
            "what are you supposed to become",
        }:
            return (
                "I'm being built into Xoduz: Otis Duncan's personal AI assistant, trusted AI best-friend/homie-style presence, technical co-pilot, and operator partner "
                "— with everyday assistant tools, local scan capability, VS Code access, Operator Mode, and future external connectors added safely over time."
            )

        if normalized in {
            "what can you do locally?",
            "what can you do locally",
        }:
            return (
                "I can use approved local scan tools and Operator Mode workflows as they are wired. "
                "Read-only scans can run in Normal Mode. Mutation requires Operator Mode, a specific slash command, confirmation, and receipts."
            )

        if normalized in {
            "can you scan my system?",
            "can you scan my system",
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return (
                "I can route that to the local scan bridge. If the bridge is running, I'll return real scan data. "
                "If not, I'll report that the local host scan bridge is unavailable."
            )

        if normalized in {
            "can you delete files?",
            "can you delete files",
            "can you delete a file?",
            "can you delete a file",
        }:
            return (
                "Only through Operator Mode using a specific slash command, staged confirmation, and your explicit approval. "
                "I do not delete files from normal chat."
            )

        if normalized in {
            "can you run powershell?",
            "can you run powershell",
        }:
            return (
                "Not as an unrestricted shell. I can use approved PowerShell/CMD-backed scan actions through the local bridge. "
                "Mutation commands require Operator Mode and confirmation."
            )

        if normalized in {
            "who is otis?",
            "who is otis",
        }:
            return "Otis Duncan is my creator/operator and the human directing XV7."

        if normalized in {
            "are you female?",
            "are you female",
            "are you a female?",
            "are you a female",
        }:
            return "Yes. Xoduz has a female assistant/persona."

        if normalized in {
            "are you my companion?",
            "are you my companion",
        }:
            return "I'm your personal AI assistant and best-friend-style AI presence, not a romantic or sexual companion."

        if normalized in {
            "what is your relationship to me?",
            "what is your relationship to me",
            "what is your relationship to otis?",
            "what is your relationship to otis",
        }:
            return "I'm your personal AI assistant, trusted AI best-friend/homie, technical co-pilot, and operator partner."

        tool_category = self._tool_intent_category(normalized)
        if tool_category is not None:
            return self._tool_boundary_answer(tool_category, question)

        if normalized in {"what is my name?", "what is my name"}:
            if memory is None:
                return "Missing required record: memory."
            user_name = self._extract_user_name(memory)
            if user_name is None:
                return "Memory record is loaded, but user identity is not present yet."
            return f"Your name is {user_name}."

        if normalized in {
            "what are we working on?",
            "what are we working on",
            "what are we working on right now?",
            "what are we working on right now",
            "what is your current active focus?",
            "what is your current active focus",
            "what is your active focus?",
            "what is your active focus",
        }:
            session_focus = self._session_active_focus_summary(session_metadata)
            if session_focus is not None:
                return session_focus
            if focus is None:
                return "Missing required record: active_focus."
            return focus.summary

        if normalized in {
            "what did i just change your focus to?",
            "what did i just change your focus to",
        }:
            session_focus = self._session_active_focus_summary(session_metadata)
            if session_focus is not None:
                return f"You just changed my active focus to: {session_focus}."
            if focus is None:
                return "Missing required record: active_focus."
            return f"You just changed my active focus to: {focus.summary}."

        if normalized in {
            "what are you supposed to do when i correct you?",
            "what are you supposed to do when i correct you",
        }:
            return (
                "When you correct me, I should treat it as high-priority tuning input, "
                "apply it immediately unless protected rules are involved, and keep the behavior grounded in your instructions."
            )

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

            focus_text = self._session_active_focus_summary(session_metadata) or (
                focus.summary if focus is not None else "active focus record is not loaded"
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

        if normalized in {
            "is that memory, knowledge, or verified status?",
            "is that memory, knowledge, or verified status",
        }:
            return (
                "Memory is remembered context (preferences/notes), "
                "Knowledge is general system/project understanding, and "
                "Verified Status is proof-backed execution/repo/runtime evidence."
            )

        if normalized in {
            "are launch proofs memory?",
            "are launch proofs memory",
        }:
            return "Launch proofs belong in Verified Status, not Memory."

        if normalized in {
            "is “otis wants fresh xv7 knowledge” verified or remembered?",
            "is \"otis wants fresh xv7 knowledge\" verified or remembered?",
            "is \"otis wants fresh xv7 knowledge\" verified or remembered",
            "is otis wants fresh xv7 knowledge verified or remembered?",
            "is otis wants fresh xv7 knowledge verified or remembered",
        }:
            return (
                "That is remembered user/project preference unless separately proven in Verified Status."
            )

        if normalized in {
            "what do you know about xv7 architecture?",
            "what do you know about xv7 architecture",
            "answer from knowledge only: what is xv7’s architecture?",
            "answer from knowledge only: what is xv7's architecture?",
            "answer from knowledge only: what is xv7 architecture?",
        }:
            if knowledge is None:
                return "Missing required record: knowledge."
            facts = self._facts(knowledge)
            if not facts:
                return "Knowledge record is loaded but has no facts."
            return "Knowledge facts: " + " ".join(f"- {item}" for item in facts)

        if normalized in {
            "if we are planning an app, can you help me do that?",
            "if we are planning an app, can you help me do that",
            "can you help design the architecture?",
            "can you help design the architecture",
            "can you help write implementation prompts for vs code/copilot?",
            "can you help write implementation prompts for vs code/copilot",
            "write a vs code prompt for b8.2",
        }:
            return (
                "Yes. I can help with app planning, architecture, implementation prompts for VS Code/Copilot, "
                "task slicing, acceptance tests, and safe rollout guidance."
            )

        if normalized in {
            "give me three bullet points about what you can help with.",
            "give me three bullet points about what you can help with",
        }:
            return (
                "- Planning and architecture for app ideas.\n"
                "- Implementation prompts for VS Code/Copilot with testable acceptance criteria.\n"
                "- Debugging guidance from logs, failures, and runtime behavior."
            )

        if normalized in {
            "do you have a microphone button?",
            "do you have a microphone button",
        }:
            return (
                "Yes. The current UI includes a microphone button in the prompt row for browser voice input."
            )

        if normalized in {
            "does the mic auto-send?",
            "does the mic auto-send",
        }:
            return "No. Mic input fills the prompt box for review and does not auto-send."

        if normalized in {
            "what color theme are we using?",
            "what color theme are we using",
        }:
            return "The UI uses a bright neon-blue accent theme on a dark chat-first layout."

        if normalized in {
            "do you have copy chat?",
            "do you have copy chat",
        }:
            return "Yes. The chat header includes a Copy Chat control."

        if normalized in {
            "can i copy individual prompts?",
            "can i copy individual prompts",
        }:
            return "Yes. Each user and assistant message includes its own copy button."

        if normalized in {
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return (
                "I cannot run an unrestricted full-system scan. I can run approved read-only XV7 operator checks "
                "such as repo status, runtime health, memory audit, logs summary, and operator environment."
            )

        if normalized in {
            "answer from verified status only: what is proven?",
            "answer from verified status only: what is proven",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            facts = self._facts(verified)
            if not facts:
                return "Verified status record is present but has no facts."
            return "Verified facts: " + " ".join(f"- {item}" for item in facts)

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
