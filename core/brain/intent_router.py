from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.brain import site_bundle as sb


class IntentKind(StrEnum):
    NORMAL_QUESTION = "normal_question"
    PREVIEW_ARTIFACT = "preview_artifact"
    CODE_ARTIFACT = "code_artifact"
    SITE_BUNDLE = "site_bundle"
    SANDBOX_BUILD = "sandbox_build"
    ARTIFACT_EDIT = "artifact_edit"
    PROTECTED_REPO_MUTATION = "protected_repo_mutation"


@dataclass(frozen=True)
class IntentDecision:
    """Normalized routing decision for user prompts before answer composition."""

    normalized_question: str
    kind: IntentKind
    has_explicit_artifact_intent: bool = False
    is_preview_artifact_request: bool = False
    is_code_artifact_request: bool = False
    is_site_bundle_request: bool = False
    is_sandbox_build_request: bool = False
    is_artifact_edit_request: bool = False
    is_repo_mutation_build_prompt: bool = False
    prioritize_artifact_over_build_guard: bool = False

    @property
    def normalized_text(self) -> str:
        return self.normalized_question

    @property
    def mode(self) -> IntentKind:
        return self.kind


class IntentRouter:
    """Classify artifact, sandbox, revision, and protected mutation prompts.

    This is the Code 22 extraction target for routing rules that were previously
    embedded directly in AnswerContract. Keep behavior-compatible wrappers in
    AnswerContract until the migration is complete.
    """

    CODE_ARTIFACT_PATTERN = re.compile(
        r"\b(generate|create|build|draft|write|return|make)\b"
    )
    CODE_ARTIFACT_HINT_PATTERN = re.compile(
        r"\b(code artifact|filename|previewable|do not apply it to the repo|do not apply to the repo|"
        r"one-page website|landing page|html|css|javascript|typescript|python)\b"
    )
    WEBSITE_BUILD_ARTIFACT_PATTERN = re.compile(
        r"\b(build|create|make|generate|draft)\b.*\b(website|site)\b.*\bfor\b"
    )
    EXPLICIT_ARTIFACT_INTENT_PATTERN = re.compile(
        r"\b(html artifact|code artifact|draft html|inline html|single-file html|single file html|"
        r"one-page html artifact|one page html artifact|generate html artifact|create html artifact|artifact)\b"
    )
    PREVIEW_VERB_PATTERN = re.compile(
        r"\b(generate|preview|show|render|display|draft|mock\s*up|mockup)\b"
    )
    PREVIEW_ARTIFACT_PATTERN = re.compile(
        r"\b(preview|show|render|display|mock\s*up|mockup)\b"
    )
    CHAT_DISPLAY_PATTERN = re.compile(
        r"\b("
        r"display in chat|display it in the chat|show in chat|show it here|"
        r"display here|preview here|chat preview|show me a preview"
        r")\b"
    )
    SANDBOX_BUILD_ACTION_PATTERN = re.compile(
        r"\b(build|write|create|export|save|scaffold)\b|"
        r"\bmake\s+(?:a\s+)?project\b|\bgenerate\s+files\b|\bwrite\s+files\b|"
        r"\bpublish\s+to\s+sandbox\b"
    )
    SANDBOX_BUILD_TARGET_PATTERN = re.compile(
        r"\b(website|site|page|design|project|app|files?|react|vite|frontend|landing page|web page|homepage|sandbox)\b"
    )
    ARTIFACT_REPO_MUTATION_PATTERN = re.compile(
        r"\b(create a website in the repo|make the app|implement this feature|"
        r"change the project files|write this into the repo|write this to the repo|"
        r"in the repo and commit it|commit it|git commit|git push|push it)\b"
    )
    ARTIFACT_EDIT_ACTION_PATTERN = re.compile(
        r"\b(change|make|update|revise|edit|adjust|tweak|restyle|refresh|rewrite|switch|set|use|improve|redesign|move|keep|preserve|undo|revert|summarize|add)\b"
    )
    ARTIFACT_EDIT_TARGET_PATTERN = re.compile(
        r"\b(website|site|artifact|page|pages|font|text|headline|button|buttons|copy|wording|color|colors|palette|theme|style|css|html|javascript|js|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|preview|code|hero|cta|section|layout|spacing|background|read|smaller|bigger|home\s?page|homepage|specials?|glass|glassmorphism|frosted|translucent|transparent|backdrop|blur|glow|glowing|shadow|card|roomy|cherry|spread)\b"
    )
    ARTIFACT_UNDO_PATTERN = re.compile(
        r"\b(undo the last change|undo|revert that|go back|restore previous)\b"
    )
    ARTIFACT_EXPLAIN_PATTERN = re.compile(
        r"\b(what changed|show me what changed|summarize the changes|summarise the changes|explain the changes)\b"
    )
    ARTIFACT_STYLE_PATTERN = re.compile(
        r"\b(color|colors|palette|background|font|script|cursive|handwritten|premium|luxury|playful|modern|dark|light|bold|cleaner|easier to read|black|gold|white)\b"
    )
    ARTIFACT_CONTENT_PATTERN = re.compile(
        r"\b(headline|cta|button text|buttons|copy|wording|services section|specials section|specials page|main headline|rewrite|rewrite the homepage|rewrite homepage|say)\b"
    )
    ARTIFACT_TARGETED_PATTERN = re.compile(
        r"\b(only|keep the layout|keep the content|preserve)\b"
    )
    ACTIVE_ARTIFACT_REFERENCE_PATTERN = re.compile(
        r"\b(this|current|existing|previous|latest)\s+"
        r"(site|website|artifact|page|design|preview)\b|"
        r"\b(the active|active)\s+(site|website|artifact|page|design|preview)\b"
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
    CONCEPTUAL_WEBSITE_QUESTION_PATTERN = re.compile(
        r"^(what|how|why|which)\b.*\b(website|site|preview|builder|generated websites?)\b"
    )
    OPERATOR_MODE_PREFIX_PATTERN = re.compile(r"^operator\s+mode\s*:\s*", re.IGNORECASE)
    OPERATOR_GITHUB_PROJECT_PATTERN = re.compile(
        r"\b(build and push|push to github|create a github repo|create a new repository on github|"
        r"create a new repo|create new repo|create a new repo named|push to github new repo|"
        r"initialize git|git init|commit and push|real github proof project|real build and push|"
        r"not a preview|not a patch)\b"
    )
    OPERATOR_PROJECT_COMMAND_PATTERN = re.compile(
        r"\b(build and push a real github proof project|"
        r"initialize the new repository and push to github|"
        r"push to github new repo|"
        r"create a new repository on github and push|"
        r"create a new repository on github|"
        r"create a new repo named|"
        r"create a new repo|"
        r"finish the github push|"
        r"commit and push this project|"
        r"push to github|"
        r"create a github repo|"
        r"git init|initialize git)\b"
    )
    OPERATOR_PROJECT_SLASH_PATTERN = re.compile(
        r"^/(build|export|write|commit|push|github|publish)\b"
    )

    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    @classmethod
    def strip_operator_mode_prefix(cls, normalized_text: str) -> str:
        if not normalized_text:
            return ""
        return cls.OPERATOR_MODE_PREFIX_PATTERN.sub(
            "", normalized_text, count=1
        ).strip()

    @classmethod
    def is_operator_mode_prefixed(cls, normalized_text: str) -> bool:
        return bool(cls.OPERATOR_MODE_PREFIX_PATTERN.match(normalized_text or ""))

    @classmethod
    def is_operator_github_project_request(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        stripped = cls.strip_operator_mode_prefix(normalized_text)
        return bool(cls.OPERATOR_GITHUB_PROJECT_PATTERN.search(stripped))

    @classmethod
    def is_operator_project_command_request(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        stripped = cls.strip_operator_mode_prefix(normalized_text)
        return bool(
            cls.OPERATOR_PROJECT_COMMAND_PATTERN.search(stripped)
            or cls.OPERATOR_PROJECT_SLASH_PATTERN.search(stripped)
        )

    @classmethod
    def has_explicit_artifact_intent(cls, normalized_text: str) -> bool:
        if cls.is_conceptual_website_question(normalized_text):
            return False
        return bool(cls.EXPLICIT_ARTIFACT_INTENT_PATTERN.search(normalized_text))

    @classmethod
    def is_conceptual_website_question(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        if not normalized_text.endswith("?") and not normalized_text.startswith(
            ("what ", "how ", "why ", "which ")
        ):
            return False
        if not cls.CONCEPTUAL_WEBSITE_QUESTION_PATTERN.search(normalized_text):
            return False
        return not re.search(
            r"\b(generate|create|build|draft|write|export|save|revise|change|make me|show me)\b",
            normalized_text,
        )

    @classmethod
    def typography_style_request(cls, normalized_text: str) -> str | None:
        if cls.TYPOGRAPHY_BLACKLETTER_PATTERN.search(normalized_text):
            return "blackletter/gothic"
        if (
            "gothic" in normalized_text
            and cls.TYPOGRAPHY_BLACKLETTER_DETAIL_PATTERN.search(normalized_text)
        ):
            return "blackletter/gothic"
        if cls.TYPOGRAPHY_SCRIPT_PATTERN.search(normalized_text):
            return "script/cursive"
        return None

    @classmethod
    def artifact_refinement_mode(cls, normalized_text: str) -> str | None:
        if cls.is_conceptual_website_question(normalized_text):
            return None
        typography_style = cls.typography_style_request(normalized_text)
        asks_for_color_change = bool(
            cls.COLOR_CHANGE_REQUEST_PATTERN.search(normalized_text)
        )
        if typography_style is not None and not asks_for_color_change:
            return "typography_only"

        if cls.ARTIFACT_UNDO_PATTERN.search(normalized_text):
            return "undo"
        if cls.ARTIFACT_EXPLAIN_PATTERN.search(normalized_text):
            return "explain"
        has_action = bool(cls.ARTIFACT_EDIT_ACTION_PATTERN.search(normalized_text))
        targeted = bool(cls.ARTIFACT_TARGETED_PATTERN.search(normalized_text))
        style = bool(cls.ARTIFACT_STYLE_PATTERN.search(normalized_text))
        content = bool(cls.ARTIFACT_CONTENT_PATTERN.search(normalized_text))
        has_target = bool(cls.ARTIFACT_EDIT_TARGET_PATTERN.search(normalized_text))
        has_active_reference = bool(
            cls.ACTIVE_ARTIFACT_REFERENCE_PATTERN.search(normalized_text)
        )
        if not has_action and not (style or content or targeted):
            return None
        if not has_action and not has_active_reference:
            return None
        if not has_action and not has_target:
            return None
        if has_action and not (has_target or style or content or targeted):
            return None
        if targeted and style and not content:
            return "style_only"
        if targeted and content and not style:
            return "content_only"
        if (
            style
            and not content
            and any(
                phrase in normalized_text
                for phrase in (
                    "change the colors",
                    "background white",
                    "use script font",
                    "make it easier to read",
                    "restyle",
                )
            )
        ):
            return "style_only"
        if (
            content
            and not style
            and any(
                phrase in normalized_text
                for phrase in (
                    "headline",
                    "cta",
                    "button text",
                    "rewrite",
                    "services section",
                )
            )
        ):
            return "content_only"
        if targeted:
            return "targeted_revision"
        return "full_revision"

    @classmethod
    def looks_like_artifact_edit(cls, normalized_text: str) -> bool:
        if cls.is_conceptual_website_question(normalized_text):
            return False
        if cls.artifact_refinement_mode(normalized_text) in {
            "undo",
            "explain",
            "typography_only",
            "style_only",
            "content_only",
            "targeted_revision",
            "full_revision",
        }:
            return True
        has_action = bool(cls.ARTIFACT_EDIT_ACTION_PATTERN.search(normalized_text))
        has_target = bool(cls.ARTIFACT_EDIT_TARGET_PATTERN.search(normalized_text))
        explicit = any(
            phrase in normalized_text
            for phrase in (
                "revise this site",
                "update the artifact",
                "change the website",
                "make the text script",
                "change the text on the website",
                "change the font to script",
            )
        )
        return explicit or (has_action and has_target)

    @classmethod
    def is_preview_artifact_request(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        if cls.is_conceptual_website_question(normalized_text):
            return False
        if cls.has_explicit_artifact_intent(normalized_text):
            return True
        if cls.PREVIEW_ARTIFACT_PATTERN.search(normalized_text):
            return True
        return bool(
            re.search(
                r"\bgenerate\b.*\b(website|site|page|design)\b",
                normalized_text,
                flags=re.IGNORECASE,
            )
        )

    @classmethod
    def is_explicit_chat_site_display_request(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        if not cls.CHAT_DISPLAY_PATTERN.search(normalized_text):
            return False
        if "show me a preview" in normalized_text and not re.search(
            r"\b(website|site|design)\b", normalized_text
        ):
            return False
        return bool(cls.SANDBOX_BUILD_TARGET_PATTERN.search(normalized_text))

    @classmethod
    def is_repo_mutation_build_prompt(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        if cls.ARTIFACT_REPO_MUTATION_PATTERN.search(normalized_text):
            return True
        if any(
            marker in normalized_text
            for marker in (" in the repo", " into the repo", " to the repo")
        ) and not re.search(
            r"\b(do not|don't)\s+(apply|write|save)\b", normalized_text
        ):
            return True
        return False

    @classmethod
    def is_sandbox_build_request(cls, normalized_text: str) -> bool:
        if not normalized_text:
            return False
        if cls.is_conceptual_website_question(normalized_text):
            return False
        if cls.has_explicit_artifact_intent(normalized_text):
            return False
        if cls.is_explicit_chat_site_display_request(normalized_text):
            return False
        if cls.is_repo_mutation_build_prompt(normalized_text):
            return False
        if re.search(
            r"\b(generate|preview|show|display|draft|mock\s*up|mockup)\b",
            normalized_text,
        ) and not re.search(
            r"\b(to|into)\s+(?:the\s+)?sandbox\b|\bgenerate\s+files\b|\bexport\b|\bsave\b|\bwrite\b|\bbuild\b|\bcreate\b",
            normalized_text,
        ):
            return False
        # Site preview/artifact requests are chat delivery by default; sandbox export
        # is triggered only by explicit write/build/create/export/save intent.
        has_action = bool(cls.SANDBOX_BUILD_ACTION_PATTERN.search(normalized_text))
        has_target = bool(cls.SANDBOX_BUILD_TARGET_PATTERN.search(normalized_text))
        return has_action and has_target

    @classmethod
    def is_code_artifact_request(cls, normalized_text: str) -> bool:
        if cls.is_conceptual_website_question(normalized_text):
            return False
        has_hint = bool(cls.CODE_ARTIFACT_HINT_PATTERN.search(normalized_text))
        has_action = bool(cls.CODE_ARTIFACT_PATTERN.search(normalized_text))
        if cls.has_explicit_artifact_intent(normalized_text) and has_action:
            return True
        if has_hint and has_action:
            return True
        if cls.WEBSITE_BUILD_ARTIFACT_PATTERN.search(normalized_text):
            return not sb.is_site_bundle_request(normalized_text)
        if cls.is_preview_artifact_request(normalized_text) and re.search(
            r"\b(website|site|page|design|homepage|landing page)\b",
            normalized_text,
            flags=re.IGNORECASE,
        ):
            return True
        return False

    @classmethod
    def prioritize_artifact_over_build_guard(cls, normalized_text: str) -> bool:
        return (
            cls.has_explicit_artifact_intent(normalized_text)
            or sb.is_site_bundle_request(normalized_text)
            or cls.is_explicit_chat_site_display_request(normalized_text)
        ) and not cls.is_repo_mutation_build_prompt(normalized_text)

    @classmethod
    def classify(cls, text: str) -> IntentDecision:
        normalized = cls.normalize(text)
        explicit_artifact = cls.has_explicit_artifact_intent(normalized)
        repo_mutation = cls.is_repo_mutation_build_prompt(normalized)
        chat_site_display = cls.is_explicit_chat_site_display_request(normalized)
        site_bundle = sb.is_site_bundle_request(normalized) or chat_site_display
        sandbox_build = cls.is_sandbox_build_request(normalized)
        artifact_edit = cls.looks_like_artifact_edit(normalized)
        preview_artifact = cls.is_preview_artifact_request(normalized)
        code_artifact = cls.is_code_artifact_request(normalized)
        prioritize_artifact = cls.prioritize_artifact_over_build_guard(normalized)

        kind = IntentKind.NORMAL_QUESTION
        if repo_mutation:
            kind = IntentKind.PROTECTED_REPO_MUTATION
        elif sandbox_build:
            kind = IntentKind.SANDBOX_BUILD
        elif site_bundle:
            kind = IntentKind.SITE_BUNDLE
        elif code_artifact:
            kind = IntentKind.CODE_ARTIFACT
        elif artifact_edit:
            kind = IntentKind.ARTIFACT_EDIT
        elif preview_artifact:
            kind = IntentKind.PREVIEW_ARTIFACT

        return IntentDecision(
            normalized_question=normalized,
            kind=kind,
            has_explicit_artifact_intent=explicit_artifact,
            is_preview_artifact_request=preview_artifact,
            is_code_artifact_request=code_artifact,
            is_site_bundle_request=site_bundle,
            is_sandbox_build_request=sandbox_build,
            is_artifact_edit_request=artifact_edit,
            is_repo_mutation_build_prompt=repo_mutation,
            prioritize_artifact_over_build_guard=prioritize_artifact,
        )
