"""Website content block planning helpers.

This module is intentionally standalone during the Code 22 split. It only
builds deterministic JSON-safe plans and does not render HTML or write files.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal, TypedDict


BlockSource = Literal["requested", "inferred"]


class ContentBlockPlanItem(TypedDict):
    id: str
    slug: str
    kind: str
    label: str
    source: BlockSource


class ContentBlockPlanPayload(TypedDict):
    profile: str
    blocks: list[ContentBlockPlanItem]


class WebsiteContentBlockPlanManager:
    """Build deterministic website content block plans."""

    NON_WORD_RE = re.compile(r"[^a-z0-9]+")
    SECTION_CONTEXT_RE = re.compile(
        r"\b(section|sections|block|blocks|include|with|featuring|show|add|page|pages)\b",
        re.IGNORECASE,
    )

    BLOCK_LABELS: dict[str, str] = {
        "hero": "Hero",
        "intro": "Intro",
        "menu": "Menu",
        "specials": "Specials",
        "products": "Products",
        "compliance_note": "Compliance Note",
        "services": "Services",
        "process": "Process",
        "diagnostics": "Diagnostics",
        "gallery": "Gallery",
        "testimonials": "Testimonials",
        "contact": "Contact",
        "hours": "Hours",
        "faq": "FAQ",
        "call_to_action": "Call To Action",
        "sermons": "Sermons",
        "bible_study": "Bible Study",
        "events": "Events",
        "trust_security": "Trust & Security",
    }

    BLOCK_ALIASES: dict[str, tuple[str, ...]] = {
        "hero": ("hero", "headline", "top section"),
        "intro": ("intro", "introduction", "about intro", "welcome"),
        "menu": ("menu", "food menu", "tap list"),
        "specials": ("specials", "deals", "offers"),
        "products": ("products", "product", "inventory", "catalog"),
        "compliance_note": ("compliance", "age gate", "legal note"),
        "services": ("services", "service cards", "offerings"),
        "process": ("process", "how it works", "workflow"),
        "diagnostics": ("diagnostics", "diagnostic", "calibration"),
        "gallery": ("gallery", "photos", "portfolio"),
        "testimonials": ("testimonials", "reviews"),
        "contact": ("contact", "get in touch", "phone"),
        "hours": ("hours", "store hours", "open hours", "visit", "location"),
        "faq": ("faq", "faqs", "questions"),
        "call_to_action": ("call to action", "cta", "button"),
        "sermons": ("sermons", "sermon"),
        "bible_study": ("bible study", "study group"),
        "events": ("events", "calendar"),
        "trust_security": ("trust", "security", "safe", "secure"),
    }

    PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
        "food": ("food cart", "food truck", "hot dog", "restaurant", "cafe"),
        "vape": ("vape", "cbd", "smoke shop", "dispensary"),
        "auto": ("adas", "automotive", "calibration", "diagnostic", "mechanic"),
        "church": ("church", "ministry", "bible study", "worship", "sermon"),
        "cyber": ("cyber", "it services", "network security", "msp", "security firm"),
    }

    PROFILE_DEFAULT_BLOCKS: dict[str, tuple[str, ...]] = {
        "food": ("hero", "menu", "specials", "hours", "contact"),
        "vape": ("hero", "products", "compliance_note", "hours", "contact"),
        "auto": ("hero", "services", "process", "diagnostics", "contact"),
        "church": ("hero", "sermons", "bible_study", "events", "contact"),
        "cyber": ("hero", "services", "trust_security", "contact"),
        "default": ("hero", "intro", "contact"),
    }

    @classmethod
    def slug_for_kind(cls, kind: str) -> str:
        slug = cls.NON_WORD_RE.sub("-", kind.strip().lower()).strip("-")
        return slug or "content-block"

    @classmethod
    def normalize_block_kind(cls, value: str) -> str:
        lowered = re.sub(
            r"\s+", " ", str(value or "").replace("-", " ").strip().lower()
        )
        for kind, aliases in cls.BLOCK_ALIASES.items():
            if lowered == kind.replace("_", " ") or lowered in aliases:
                return kind
        return cls.slug_for_kind(lowered).replace("-", "_")

    @classmethod
    def infer_profile(cls, prompt: str) -> str:
        lowered = str(prompt or "").lower()
        for profile, keywords in cls.PROFILE_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return profile
        return "default"

    @classmethod
    def _contains_alias(cls, prompt: str, alias: str) -> bool:
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        return bool(re.search(pattern, prompt, flags=re.IGNORECASE))

    @classmethod
    def extract_requested_blocks(cls, prompt: str) -> list[str]:
        if not cls.SECTION_CONTEXT_RE.search(prompt or ""):
            return []
        requested: list[str] = []
        for kind, aliases in cls.BLOCK_ALIASES.items():
            if any(cls._contains_alias(prompt, alias) for alias in aliases):
                requested.append(kind)
        return cls.dedupe_blocks(requested)

    @staticmethod
    def dedupe_blocks(blocks: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for block in blocks:
            normalized = WebsiteContentBlockPlanManager.normalize_block_kind(block)
            if normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @classmethod
    def infer_default_blocks(cls, prompt: str) -> list[str]:
        profile = cls.infer_profile(prompt)
        return list(
            cls.PROFILE_DEFAULT_BLOCKS.get(
                profile, cls.PROFILE_DEFAULT_BLOCKS["default"]
            )
        )

    @classmethod
    def build_content_block_plan(
        cls,
        prompt: str,
        requested_blocks: Sequence[str] | None = None,
        page_sections: Sequence[str] | None = None,
    ) -> ContentBlockPlanPayload:
        explicit_blocks = cls.dedupe_blocks(
            [
                *(requested_blocks or ()),
                *(page_sections or ()),
                *cls.extract_requested_blocks(prompt),
            ]
        )
        profile = cls.infer_profile(prompt)
        has_known_profile = profile != "default"
        if has_known_profile:
            block_kinds = [*cls.infer_default_blocks(prompt), *explicit_blocks]
            source: BlockSource = "inferred"
        else:
            block_kinds = explicit_blocks or cls.infer_default_blocks(prompt)
            source = "requested" if explicit_blocks else "inferred"
        blocks: list[ContentBlockPlanItem] = []
        for index, kind in enumerate(cls.dedupe_blocks(block_kinds), start=1):
            slug = cls.slug_for_kind(kind)
            blocks.append(
                {
                    "id": f"block-{index:02d}-{slug}",
                    "slug": slug,
                    "kind": kind,
                    "label": cls.BLOCK_LABELS.get(kind, kind.replace("_", " ").title()),
                    "source": source,
                }
            )
        return {"profile": profile, "blocks": blocks}
