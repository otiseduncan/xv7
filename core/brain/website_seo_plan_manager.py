"""Website SEO metadata planning helpers.

This module is intentionally standalone during Code 22 manager slicing. It does
not mutate runtime state and does not delegate from AnswerContract yet.
"""

from __future__ import annotations

import re


class WebsiteSeoPlanManager:
    """Build deterministic SEO metadata plans for website artifacts."""

    DEFAULT_KEYWORDS = ("website", "services", "contact")
    MAX_TITLE_LENGTH = 60
    MAX_DESCRIPTION_LENGTH = 160

    _QUOTE_RE = re.compile(r"[\"“”']([^\"“”']{3,90})[\"“”']")
    _META_RE = re.compile(
        r"(?:meta\s+description|seo\s+description|description)\s*[:\-]\s*(.+)",
        re.IGNORECASE,
    )
    _KEYWORD_RE = re.compile(
        r"(?:keywords?|tags?)\s*[:\-]\s*(.+)",
        re.IGNORECASE,
    )

    @staticmethod
    def clean_text(value: object) -> str:
        """Return whitespace-normalized text."""
        if not isinstance(value, str):
            return ""
        return " ".join(value.strip().split())

    @classmethod
    def truncate(cls, value: str, max_length: int) -> str:
        """Trim text without leaving dangling punctuation or partial whitespace."""
        text = cls.clean_text(value)
        if len(text) <= max_length:
            return text
        trimmed = text[: max_length + 1].rsplit(" ", 1)[0]
        return trimmed.rstrip(" ,.;:-")

    @classmethod
    def extract_title(cls, prompt: str, business_name: str | None = None) -> str:
        """Extract a deterministic SEO title from prompt or business name."""
        explicit_name = cls.clean_text(business_name)
        if explicit_name:
            return cls.truncate(explicit_name, cls.MAX_TITLE_LENGTH)

        quoted = cls._QUOTE_RE.search(prompt)
        if quoted:
            return cls.truncate(quoted.group(1), cls.MAX_TITLE_LENGTH)

        lowered = prompt.lower()
        for marker in (" for ", " about ", " called ", " named "):
            if marker in lowered:
                index = lowered.rfind(marker)
                candidate = prompt[index + len(marker) :]
                candidate = re.split(r"\b(?:with|using|that|and|,|\.)\b", candidate)[0]
                cleaned = cls.clean_text(candidate)
                if cleaned:
                    return cls.truncate(cleaned, cls.MAX_TITLE_LENGTH)

        return "Website"

    @classmethod
    def extract_meta_description(cls, prompt: str, title: str | None = None) -> str:
        """Extract or infer a safe meta description."""
        match = cls._META_RE.search(prompt)
        if match:
            description = match.group(1).strip().strip('"\'')
            return cls.truncate(description, cls.MAX_DESCRIPTION_LENGTH)

        clean_title = cls.clean_text(title) or cls.extract_title(prompt)
        return cls.truncate(
            f"Explore {clean_title} services, highlights, and contact details.",
            cls.MAX_DESCRIPTION_LENGTH,
        )

    @classmethod
    def extract_keywords(cls, prompt: str, title: str | None = None) -> list[str]:
        """Extract stable SEO keywords from explicit keyword text and context."""
        keywords: list[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            cleaned = cls.clean_text(value).strip(" ,.;:-").lower()
            if not cleaned or cleaned in seen:
                return
            if len(cleaned) > 40:
                return
            seen.add(cleaned)
            keywords.append(cleaned)

        match = cls._KEYWORD_RE.search(prompt)
        if match:
            for part in re.split(r"[,;/]|\band\b", match.group(1), flags=re.IGNORECASE):
                add(part)

        clean_title = cls.clean_text(title)
        if clean_title and clean_title.lower() != "website":
            for part in re.split(r"\s+", clean_title):
                add(part)

        lowered = prompt.lower()
        context_terms = {
            "restaurant": ("restaurant", "menu", "food"),
            "food cart": ("food cart", "menu", "catering"),
            "vape": ("vape", "cbd", "shop"),
            "cbd": ("cbd", "wellness", "shop"),
            "adas": ("adas", "calibration", "automotive"),
            "cybersecurity": ("cybersecurity", "security", "it services"),
            "church": ("church", "ministry", "bible study"),
        }
        for marker, terms in context_terms.items():
            if marker in lowered:
                for term in terms:
                    add(term)

        for fallback in cls.DEFAULT_KEYWORDS:
            add(fallback)

        return keywords[:10]

    @classmethod
    def build_plan(cls, prompt: str, business_name: str | None = None) -> dict[str, object]:
        """Build a JSON-safe SEO plan."""
        title = cls.extract_title(prompt, business_name)
        description = cls.extract_meta_description(prompt, title)
        keywords = cls.extract_keywords(prompt, title)
        return {
            "title": title,
            "description": description,
            "keywords": keywords,
            "robots": "index, follow",
            "source": "website_seo_plan_manager",
        }
