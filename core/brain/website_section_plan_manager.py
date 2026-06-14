"""Website section planning helpers for generated site artifacts."""

from __future__ import annotations

import re
from typing import Any, ClassVar


class WebsiteSectionPlanManager:
    """Build deterministic website section plans without rendering HTML."""

    DEFAULT_SECTIONS: ClassVar[tuple[str, ...]] = (
        "Hero",
        "About",
        "Services",
        "Gallery",
        "Contact",
    )

    SECTION_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "Hero": ("hero", "landing", "intro"),
        "About": ("about", "about us", "our story"),
        "Services": ("services", "service list", "what we do"),
        "Menu Highlights": ("menu", "menu highlights", "featured items"),
        "Specials": ("specials", "deals", "promos", "promotions"),
        "Visit / Hours": ("visit", "hours", "location", "locations"),
        "Order / Catering CTA": ("order", "ordering", "catering", "cta"),
        "Products": ("products", "product list", "inventory"),
        "Reviews": ("reviews", "testimonials", "social proof"),
        "Portfolio": ("portfolio", "work examples", "case studies"),
        "Booking": ("booking", "appointments", "schedule"),
        "Gallery": ("gallery", "photos", "images"),
        "Contact": ("contact", "contact us", "get in touch"),
    }

    BUSINESS_HINT_SECTIONS: ClassVar[
        tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]
    ] = (
        (
            ("hot dog", "hotdog", "food cart", "restaurant", "cafe", "menu"),
            (
                "Hero",
                "Menu Highlights",
                "Specials",
                "Visit / Hours",
                "Order / Catering CTA",
            ),
        ),
        (
            ("vape", "cbd", "smoke shop", "dispensary", "retail"),
            ("Hero", "Products", "Specials", "Reviews", "Contact"),
        ),
        (
            ("auto", "adas", "calibration", "diagnostic", "repair"),
            ("Hero", "Services", "Portfolio", "Reviews", "Contact"),
        ),
        (
            ("church", "ministry", "bible", "sermon", "fellowship"),
            ("Hero", "About", "Services", "Events", "Contact"),
        ),
        (
            ("cybersecurity", "consulting", "automation", "it service"),
            ("Hero", "Services", "Portfolio", "Reviews", "Contact"),
        ),
    )

    REQUEST_CONTEXT_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(section|sections|include|includes|with|add|page|pages|site|website)\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_section_title(cls, title: str) -> str:
        """Return the canonical display title for a requested section."""

        cleaned = re.sub(r"\s+", " ", str(title or "")).strip(" .,:;-/")
        if not cleaned:
            return ""

        lowered = cleaned.casefold()
        for canonical, aliases in cls.SECTION_ALIASES.items():
            candidates = (canonical, *aliases)
            if lowered in {candidate.casefold() for candidate in candidates}:
                return canonical

        words = []
        for word in re.split(r"(\s+/\s+|\s+)", cleaned):
            if word.casefold() in {"cta", "it", "seo", "faq"}:
                words.append(word.upper())
            elif word.strip() == "/":
                words.append("/")
            elif word.isspace():
                words.append(word)
            else:
                words.append(word.capitalize())
        return "".join(words).replace(" / ", " / ")

    @staticmethod
    def slugify_section(title: str) -> str:
        """Return a stable anchor slug for a section title."""

        lowered = str(title or "").casefold().replace("&", " and ")
        lowered = re.sub(r"[/\\]+", " ", lowered)
        slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
        return slug or "section"

    @classmethod
    def _has_request_context(cls, prompt: str, start: int, end: int) -> bool:
        window_start = max(0, start - 80)
        window_end = min(len(prompt), end + 80)
        window = prompt[window_start:window_end]
        if cls.REQUEST_CONTEXT_RE.search(window):
            return True
        prefix = prompt[max(0, start - 3) : start]
        suffix = prompt[end : min(len(prompt), end + 3)]
        return bool(re.search(r"[,;:]\s*$", prefix) or re.search(r"^\s*[,;]", suffix))

    @classmethod
    def _contains_alias(cls, prompt: str, alias: str) -> bool:
        pattern = re.compile(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", re.IGNORECASE)
        return any(
            cls._has_request_context(prompt, match.start(), match.end())
            for match in pattern.finditer(prompt)
        )

    @classmethod
    def extract_requested_sections(cls, prompt: str) -> list[str]:
        """Extract explicitly requested section titles from a prompt."""

        text = str(prompt or "")
        sections: list[str] = []
        for canonical, aliases in cls.SECTION_ALIASES.items():
            candidates = (canonical, *aliases)
            if any(cls._contains_alias(text, candidate) for candidate in candidates):
                sections.append(canonical)
        return cls._dedupe_sections(sections) or ["Hero"]

    @classmethod
    def infer_business_sections(cls, prompt: str) -> list[str]:
        """Infer a section set from business hints in a prompt."""

        lowered = str(prompt or "").casefold()
        for hints, sections in cls.BUSINESS_HINT_SECTIONS:
            if any(hint in lowered for hint in hints):
                return list(sections)
        return list(cls.DEFAULT_SECTIONS)

    @classmethod
    def build_section_plan(
        cls,
        prompt: str,
        requested_sections: list[str] | tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Build a JSON-safe section plan for website generation."""

        if requested_sections is None:
            extracted = cls.extract_requested_sections(prompt)
            inferred = cls.infer_business_sections(prompt)
            source = "requested" if extracted != ["Hero"] else "inferred"
            titles = extracted if source == "requested" else inferred
        else:
            source = "requested"
            titles = list(requested_sections)

        normalized = cls._dedupe_sections(
            title
            for title in (cls.normalize_section_title(item) for item in titles)
            if title
        )
        if "Hero" not in normalized:
            normalized.insert(0, "Hero")

        return [
            {
                "title": title,
                "slug": cls.slugify_section(title),
                "anchor": f"#{cls.slugify_section(title)}",
                "kind": cls.classify_section(title),
                "source": source,
            }
            for title in normalized
        ]

    @staticmethod
    def classify_section(title: str) -> str:
        """Classify a section title into a coarse content role."""

        lowered = str(title or "").casefold()
        if lowered == "hero":
            return "hero"
        if "cta" in lowered or "order" in lowered or "booking" in lowered:
            return "action"
        if any(term in lowered for term in ("contact", "visit", "hours", "location")):
            return "contact"
        if any(
            term in lowered for term in ("review", "portfolio", "case stud", "gallery")
        ):
            return "proof"
        return "content"

    @staticmethod
    def _dedupe_sections(sections: Any) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for section in sections:
            key = str(section).casefold()
            if key and key not in seen:
                seen.add(key)
                result.append(str(section))
        return result
