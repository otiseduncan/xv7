"""Website call-to-action planning helpers.

This module is intentionally standalone during the Code 22 split.  It does not
mutate runtime state and is not wired into AnswerContract yet.
"""

from __future__ import annotations

import re
from typing import Any


class WebsiteCallToActionManager:
    """Build deterministic website call-to-action plans."""

    DEFAULT_LABEL = "Contact Us"
    CTA_CONTEXT_RE = re.compile(
        r"\b(buttons?|cta|call[-\s]*to[-\s]*action|links?|actions?|add|include|use|show)\b",
        re.IGNORECASE,
    )
    NON_WORD_RE = re.compile(r"[^a-z0-9]+")
    SPACE_RE = re.compile(r"\s+")

    LABEL_ALIASES: dict[str, tuple[str, ...]] = {
        "Book Now": ("book now", "schedule", "book appointment", "booking"),
        "Call Now": ("call now", "phone", "call us"),
        "Contact Us": ("contact", "contact us", "get in touch"),
        "Get Directions": ("directions", "find us", "location"),
        "Order Online": ("order online", "order now", "online order"),
        "Order Catering": ("catering", "cater", "event catering"),
        "View Menu": ("menu", "view menu"),
        "Request Quote": ("quote", "estimate", "request quote"),
        "Schedule Service": ("schedule service", "service appointment"),
        "Shop Now": ("shop", "shop now", "store"),
        "Donate": ("donate", "give", "giving"),
        "Join Us": ("join", "join us", "visit us"),
    }

    BUSINESS_DEFAULTS: dict[str, tuple[str, ...]] = {
        "food": ("View Menu", "Order Catering", "Get Directions"),
        "vape": ("Shop Now", "Get Directions", "Contact Us"),
        "auto": ("Schedule Service", "Request Quote", "Call Now"),
        "church": ("Join Us", "Donate", "Contact Us"),
        "cyber": ("Request Quote", "Schedule Service", "Contact Us"),
        "default": (DEFAULT_LABEL,),
    }

    PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
        "food": ("food cart", "food truck", "hot dog", "restaurant", "menu"),
        "vape": ("vape", "cbd", "smoke shop", "dispensary"),
        "auto": ("auto", "adas", "calibration", "diagnostic", "mechanic"),
        "church": ("church", "ministry", "bible study", "worship"),
        "cyber": ("cyber", "security", "it services", "network", "msp"),
    }

    @classmethod
    def normalize_label(cls, value: Any) -> str:
        """Return a display-safe CTA label."""

        text = str(value or "")
        text = text.replace("_", " ").replace("-", " ")
        text = cls.SPACE_RE.sub(" ", text).strip(" .,!?:;\t\n\r")
        if not text:
            return cls.DEFAULT_LABEL
        words = []
        for word in text.split(" "):
            if word.upper() in {"CTA", "SEO", "ADAS", "IT"}:
                words.append(word.upper())
            else:
                words.append(word[:1].upper() + word[1:].lower())
        return " ".join(words)

    @classmethod
    def slug_for_label(cls, label: str) -> str:
        """Return a stable slug for a CTA label."""

        normalized = cls.normalize_label(label).lower()
        slug = cls.NON_WORD_RE.sub("-", normalized).strip("-")
        return slug or "contact-us"

    @classmethod
    def infer_profile(cls, prompt: str, business_type: str | None = None) -> str:
        """Infer a broad website profile from explicit type or prompt text."""

        candidate = (business_type or "").strip().lower().replace("_", " ")
        for profile in cls.BUSINESS_DEFAULTS:
            if profile != "default" and profile in candidate:
                return profile

        lower_prompt = (prompt or "").lower()
        for profile, keywords in cls.PROFILE_KEYWORDS.items():
            if any(keyword in lower_prompt for keyword in keywords):
                return profile
        return "default"

    @classmethod
    def _has_cta_context(cls, prompt: str) -> bool:
        return bool(cls.CTA_CONTEXT_RE.search(prompt or ""))

    @classmethod
    def _contains_alias(cls, prompt: str, alias: str) -> bool:
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        return bool(re.search(pattern, prompt, re.IGNORECASE))

    @classmethod
    def dedupe_labels(cls, labels: list[str]) -> list[str]:
        """Dedupe normalized labels while preserving order."""

        seen: set[str] = set()
        ordered: list[str] = []
        for label in labels:
            normalized = cls.normalize_label(label)
            key = normalized.casefold()
            if key not in seen:
                seen.add(key)
                ordered.append(normalized)
        return ordered

    @classmethod
    def extract_requested_labels(cls, prompt: str) -> list[str]:
        """Extract CTA labels only when prompt contains CTA-style context."""

        if not cls._has_cta_context(prompt):
            return []

        requested: list[str] = []
        for label, aliases in cls.LABEL_ALIASES.items():
            if any(cls._contains_alias(prompt, alias) for alias in aliases):
                requested.append(label)
        return cls.dedupe_labels(requested)

    @classmethod
    def infer_default_labels(
        cls,
        prompt: str,
        business_type: str | None = None,
    ) -> list[str]:
        """Infer fallback CTA labels from website profile."""

        profile = cls.infer_profile(prompt, business_type)
        return list(
            cls.BUSINESS_DEFAULTS.get(profile, cls.BUSINESS_DEFAULTS["default"])
        )

    @classmethod
    def href_for_label(cls, label: str) -> str:
        """Return a deterministic placeholder href for a CTA."""

        slug = cls.slug_for_label(label)
        if slug in {"call-now"}:
            return "tel:+10000000000"
        if slug in {"contact-us", "request-quote", "schedule-service"}:
            return "#contact"
        if slug in {"get-directions"}:
            return "#location"
        if slug in {"view-menu", "order-online", "order-catering"}:
            return "#menu"
        if slug in {"donate"}:
            return "#giving"
        return f"#{slug}"

    @classmethod
    def build_cta_plan(
        cls,
        prompt: str,
        business_type: str | None = None,
    ) -> dict[str, Any]:
        """Build a JSON-safe CTA plan payload."""

        requested = cls.extract_requested_labels(prompt)
        source = "requested" if requested else "inferred"
        labels = requested or cls.infer_default_labels(prompt, business_type)
        actions = [
            {
                "label": label,
                "slug": cls.slug_for_label(label),
                "href": cls.href_for_label(label),
                "source": source,
            }
            for label in cls.dedupe_labels(labels)
        ]
        return {
            "profile": cls.infer_profile(prompt, business_type),
            "source": source,
            "actions": actions,
        }
