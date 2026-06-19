from __future__ import annotations

import os
import html
import re
import difflib
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from core.brain.artifact_fidelity_manager import ArtifactFidelityManager
from core.brain.artifact_response_service import ArtifactResponseService
from core.brain.answer_decision_service import AnswerDecisionService
from core.brain.artifact_utils import (
    content_sha256,
    safe_slug,
    slugify_artifact_name,
    utc_now_iso,
)
from core.brain.code_artifact_builder import CodeArtifactBuilder
from core.brain.git_runner import run_git
from core.brain.intent_router import IntentRouter
from core.brain.repo_safety_policy import RepoSafetyPolicy
from core.brain.sandbox_writer import SandboxWriteManager
from core.brain.schema import BrainLayer, BrainRecord
from core.operator.slash_commands import get_tool_capability_summary
from core.runtime.model_registry import (
    configured_ollama_base_url_candidates,
    resolve_model_for_runtime_role,
)


from core.brain.answer_contract_parts.part_01 import install_answer_contract_part_01
from core.brain.answer_contract_parts.part_02 import install_answer_contract_part_02
from core.brain.answer_contract_parts.part_03 import install_answer_contract_part_03
from core.brain.answer_contract_parts.part_04 import install_answer_contract_part_04
class AnswerContract:
    """Conversation quality guardrails for proof-aware record-grounded answers."""

    ROADMAP_NOT_WIRED = "That module is not wired yet and remains on the XV7 roadmap."

    CODE_ARTIFACT_PATTERN = re.compile(
        r"\b(generate|create|build|draft|write|return|make)\b"
    )
    CODE_ARTIFACT_HINT_PATTERN = re.compile(
        r"\b(code artifact|filename|previewable|do not apply it to the repo|do not apply to the repo|"
        r"one-page website|landing page|html|css|javascript|typescript|python)\b"
    )
    EXPLICIT_ARTIFACT_INTENT_PATTERN = re.compile(
        r"\b(html artifact|code artifact|draft html|inline html|single-file html|single file html|"
        r"one-page html artifact|one page html artifact|generate html artifact|create html artifact|artifact)\b"
    )
    ARTIFACT_REPO_MUTATION_PATTERN = re.compile(
        r"\b(build me a website|create a website in the repo|make the app|implement this feature|"
        r"change the project files|write this into the repo|write this to the repo|"
        r"in the repo and commit it|commit it|git commit|git push|push it)\b"
    )

    REMINDER_PATTERN = re.compile(
        r"\b(remind me|set (?:me )?(?:a )?reminder|create (?:a )?reminder|add (?:it )?to (?:my )?calendar|schedule (?:it|this|that))\b"
    )
    HARDWARE_SCAN_PATTERN = re.compile(
        r"\b(cpu|gpu|processor|graphics|vram|disk|disks|disc|discs|drive|drives|ports?|processes|services|docker|container|vscode|vs code|hardware|system scan|host scan|system info|temperature sensor|thermal|fan|hardware temp|system temperature)\b"
    )
    SMS_PATTERN = re.compile(
        r"\b(send a text|send text|send this as a text message|text my|text someone|message someone|message\s+[a-z0-9]+|sms this to|sms)\b"
    )
    ARTIFACT_EDIT_ACTION_PATTERN = re.compile(
        r"\b(change|make|update|revise|edit|adjust|tweak|restyle|refresh|rewrite|switch|set|use|improve|redesign|move|keep|preserve|undo|revert|show|summarize)\b"
    )
    ARTIFACT_EDIT_TARGET_PATTERN = re.compile(
        r"\b(website|site|artifact|page|font|text|headline|button|buttons|copy|wording|color|colors|palette|theme|style|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|preview|code|hero|cta|section|layout|spacing|background|read|smaller|bigger|glass|glassmorphism|frosted|translucent|transparent|backdrop|blur|glow|glowing|shadow|card|cards|roomy|cherry|spread)\b"
    )
    SMS_EXPLICIT_SEND_PATTERN = re.compile(
        r"\b(send a text|send text|send this as a text message|text my|message\s+[a-z0-9]+|sms this)\b"
    )
    ARTIFACT_UNDO_PATTERN = re.compile(
        r"\b(undo the last change|undo|revert that|go back|restore previous)\b"
    )
    ARTIFACT_EXPLAIN_PATTERN = re.compile(
        r"\b(what changed|show me what changed|summarize the changes|summarise the changes|explain the changes)\b"
    )
    ARTIFACT_STYLE_PATTERN = re.compile(
        r"\b(color|colors|palette|background|font|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|easier to read|black|gold|white|glass|glassmorphism|frosted|translucent|transparent|backdrop|blur|glow|glowing|shadow|card|roomy|cherry|spread)\b"
    )
    ARTIFACT_CONTENT_PATTERN = re.compile(
        r"\b(headline|cta|button text|buttons|copy|wording|services section|main headline|rewrite|say)\b"
    )
    ARTIFACT_TARGETED_PATTERN = re.compile(
        r"\b(only|keep the layout|keep the content|preserve)\b"
    )
    ARTIFACT_PATCH_PROPOSAL_PATTERN = re.compile(
        r"\b(generate(?:\s+a)?\s+patch|create\s+a\s+patch\s+from\s+the\s+artifact|turn\s+this\s+into\s+a\s+patch|"
        r"create\s+patch\s+proposals?|create\s+patch\s+proposal\s+for\s+all\s+files|"
        r"make\s+a\s+patch\s+for\s+this\s+website|prepare\s+this\s+for\s+vs\s*code|save\s+this\s+as\s+a\s+patch|"
        r"show\s+me\s+the\s+diff|where\s+would\s+this\s+file\s+go)\b"
    )
    ARTIFACT_PATCH_APPLY_PATTERN = re.compile(
        r"\b(apply\s+this\s+patch|apply\s+the\s+patch|approve\s+patch|confirm\s+apply|write\s+the\s+proposed\s+patch|"
        r"save\s+the\s+patch\s+to\s+the\s+repo|apply\s+patch|"
        r"write/export/save\s+it\s+to\s+the\s+sandbox|"
        r"write\s+this\s+to\s+the\s+sandbox|write\s+this\s+to\s+sandbox|"
        r"save\s+this\s+to\s+the\s+sandbox|save\s+this\s+to\s+sandbox|"
        r"export\s+this\s+to\s+the\s+sandbox|export\s+this\s+to\s+sandbox)\b"
    )
    ARTIFACT_POST_APPLY_VERIFY_PATTERN = re.compile(
        r"\b(verify it|verify the file|check the applied file|make sure it wrote correctly|did it save|"
        r"did the file get created|confirm the file exists|check the file on disk|validate the applied patch)\b"
    )
    ARTIFACT_POST_APPLY_PREVIEW_PATTERN = re.compile(
        r"\b(preview it|open preview|show me the preview|how do i view it|open the generated site|where can i see it)\b"
    )
    ARTIFACT_POST_APPLY_TARGETED_VALIDATION_PATTERN = re.compile(
        r"\b(run validation|validate it|run safe checks|run html validation|check the generated site|run targeted tests)\b"
    )
    ARTIFACT_POST_APPLY_FULL_TEST_GUARD_PATTERN = re.compile(
        r"\b(run full tests|run pytest|run npm test|run full validation|run the full validation suite)\b"
    )
    TYPOGRAPHY_BLACKLETTER_PATTERN = re.compile(
        r"\b(old english font|blackletter|gothic font|fraktur|medieval font|biker-bar style font|biker bar style font)\b"
    )
    TYPOGRAPHY_BLACKLETTER_DETAIL_PATTERN = re.compile(
        r"\b(major section titles|heavier strokes|shadowing|letter spacing|decorative styling|gothic biker-bar style font|gothic biker bar style font)\b"
    )
    TYPOGRAPHY_SCRIPT_PATTERN = re.compile(
        r"\b(script font|cursive font|change the font|change the text font|change the heading font|change the font to a script)\b"
    )
    COLOR_CHANGE_REQUEST_PATTERN = re.compile(
        r"\b(color|colors|palette|background|theme)\b"
    )
    COMMIT_PROPOSAL_PATTERN = re.compile(
        r"\b(prepare (?:a )?commit|propose (?:a )?commit|commit proposal|create commit proposal|"
        r"draft commit|show commit proposal|summarize changes for commit|summarise changes for commit|"
        r"what would the commit be|what should i commit|prepare this commit|stage this for commit)\b"
    )
    COMMIT_APPROVAL_PATTERN = re.compile(
        r"\b(commit it|commit the proposal|approve commit|confirm commit|make the commit|"
        r"create the commit|go ahead and commit|commit these changes)\b"
    )
    EMAIL_SEND_PATTERN = re.compile(
        r"\b(send|compose|write).{0,40}\bemail\b|\bsend email\b"
    )
    EMAIL_PATTERN = re.compile(r"\b(email|inbox|mail)\b")
    WEATHER_PATTERN = re.compile(
        r"\b(weather|forecast|temperature|rain|snow|humidity)\b"
    )
    BIRTHDAY_PATTERN = re.compile(r"\b(birthday|birth day|bday)\b")
    CONTACT_PATTERN = re.compile(r"\b(contact|call|phone number|reach out)\b")
    FAMILY_PATTERN = re.compile(
        r"\b(family|mom|mother|dad|father|sister|brother|spouse|partner|child|children)\b"
    )
    MEDICAL_PATTERN = re.compile(
        r"\b(medical|health|history|condition|diagnosis|medication)\b"
    )
    WEB_LOOKUP_PATTERN = re.compile(
        r"\b(look up|lookup|search|find|browse|official website|website)\b"
    )
    CALENDAR_PATTERN = re.compile(r"\b(calendar|schedule|meeting|appointment|event)\b")
    APPOINTMENT_PATTERN = re.compile(
        r"\b(appointment|meeting|event|doctor visit|doctor appointment)\b"
    )














































































    # site_bundle session helpers are delegated to the sb module.








































install_answer_contract_part_01(AnswerContract)
install_answer_contract_part_02(AnswerContract)
install_answer_contract_part_03(AnswerContract)
install_answer_contract_part_04(AnswerContract)
