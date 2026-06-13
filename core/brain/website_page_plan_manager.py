from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WebsitePagePlan:
    """Normalized website page plan entry for future site-bundle extraction."""

    title: str
    path: str
    source: str


class WebsitePagePlanManager:
    """Pure helpers for requested website page planning.

    This manager is intentionally standalone for Code 22 manager-only slicing.
    Runtime delegation can happen later after local validation.
    """

    HOME_TITLE = "Home"

    PAGE_ALIASES: tuple[tuple[str, str], ...] = (
        ("about", "About"),
        ("about us", "About"),
        ("menu", "Menu"),
        ("services", "Services"),
        ("service", "Services"),
        ("specials", "Specials"),
        ("special", "Specials"),
        ("catering", "Catering"),
        ("locations", "Locations"),
        ("location", "Locations"),
        ("pricing", "Pricing"),
        ("price", "Pricing"),
        ("prices", "Pricing"),
        ("reviews", "Reviews"),
        ("review", "Reviews"),
        ("portfolio", "Portfolio"),
        ("gallery", "Gallery"),
        ("booking", "Booking"),
        ("book", "Booking"),
        ("aftercare", "Aftercare"),
        ("rentals", "Rentals"),
        ("rental", "Rentals"),
        ("safety", "Safety"),
        ("guided tours", "Guided Tours"),
        ("tour", "Guided Tours"),
        ("tours", "Guided Tours"),
        ("contact", "Contact"),
        ("contact us", "Contact"),
    )

    MULTIPAGE_TERMS: tuple[str, ...] = (
        "multi-page",
        "multipage",
        "multiple pages",
        "pages",
        "full site",
        "complete site",
    )

    @classmethod
    def normalize_title(cls, value: str | None) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        if not text:
            return cls.HOME_TITLE
        text = text.replace("_", " ").replace("-", " ")
        words = [word.capitalize() for word in text.split()]
        return " ".join(words)

    @classmethod
    def page_slug(cls, title: str | None) -> str:
        normalized = cls.normalize_title(title).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
        return slug or "home"

    @classmethod
    def page_path(cls, title: str | None) -> str:
        normalized = cls.normalize_title(title)
        if normalized == cls.HOME_TITLE:
            return "index.html"
        return f"{cls.page_slug(normalized)}.html"

    @classmethod
    def is_multipage_request(cls, prompt: str | None) -> bool:
        text = str(prompt or "").lower()
        return any(term in text for term in cls.MULTIPAGE_TERMS)

    @classmethod
    def extract_requested_titles(cls, prompt: str | None) -> list[str]:
        text = str(prompt or "").lower()
        titles = [cls.HOME_TITLE]
        for alias, title in cls.PAGE_ALIASES:
            if cls._contains_alias(text, alias):
                titles.append(title)
        return cls._dedupe(titles)

    @classmethod
    def build_page_plan(cls, prompt: str | None) -> list[WebsitePagePlan]:
        titles = cls.extract_requested_titles(prompt)
        return [
            WebsitePagePlan(
                title=title,
                path=cls.page_path(title),
                source="default" if title == cls.HOME_TITLE else "prompt",
            )
            for title in titles
        ]

    @classmethod
    def build_manifest_pages(cls, prompt: str | None) -> list[dict[str, str]]:
        return [
            {"title": page.title, "path": page.path, "source": page.source}
            for page in cls.build_page_plan(prompt)
        ]

    @staticmethod
    def _contains_alias(text: str, alias: str) -> bool:
        escaped = re.escape(alias).replace(r"\ ", r"\s+")
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        return re.search(pattern, text) is not None

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result
