"""Website project naming and safe bundle-folder helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_PROJECT_DISPLAY_NAME = "Website"
DEFAULT_PROJECT_SLUG = "website"
MAX_PROJECT_SLUG_LENGTH = 64

_RESERVED_WINDOWS_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}

_QUOTED_NAME_RE = re.compile(r"[\"“”]([^\"“”]{2,100})[\"“”]")
_NAMED_PROJECT_RE = re.compile(
    r"\b(?:for|called|named|about)\s+([A-Za-z0-9][A-Za-z0-9 &'’.\-]{1,100})",
    re.IGNORECASE,
)
_TRAILING_DESCRIPTOR_RE = re.compile(
    r"\s+(?:with|using|that has|featuring|include|including|and make|and use|in the style of)\b.*$",
    re.IGNORECASE,
)
_LEADING_REQUEST_RE = re.compile(
    r"^(?:build|create|generate|make|scaffold|draft|design)\s+"
    r"(?:me\s+)?(?:a|an)?\s*(?:website|site|web\s+app|page)?\s*"
    r"(?:for|called|named|about)?\s*",
    re.IGNORECASE,
)
_GENERIC_SITE_WORDS_RE = re.compile(
    r"\b(?:website|site|web\s+app|landing\s+page)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class WebsiteProjectName:
    """Normalized display and filesystem-safe project naming payload."""

    display_name: str
    slug: str
    folder_name: str

    def as_dict(self) -> dict[str, str]:
        return {
            "display_name": self.display_name,
            "slug": self.slug,
            "folder_name": self.folder_name,
        }


class WebsiteProjectNameManager:
    """Pure helpers for website artifact project names and sandbox folder names."""

    @staticmethod
    def normalize_display_name(
        value: str | None, fallback: str = DEFAULT_PROJECT_DISPLAY_NAME
    ) -> str:
        raw = str(value or "").replace("\u2019", "'").strip()
        raw = _TRAILING_DESCRIPTOR_RE.sub("", raw)
        raw = _LEADING_REQUEST_RE.sub("", raw)
        raw = raw.strip(" \t\r\n-_:;,.!")
        raw = re.sub(r"\s+", " ", raw)
        if not raw or _GENERIC_SITE_WORDS_RE.fullmatch(raw):
            return fallback
        return raw

    @staticmethod
    def extract_project_name(
        prompt: str | None, fallback: str = DEFAULT_PROJECT_DISPLAY_NAME
    ) -> str:
        text = str(prompt or "").strip()
        if not text:
            return fallback

        quoted_match = _QUOTED_NAME_RE.search(text)
        if quoted_match:
            return WebsiteProjectNameManager.normalize_display_name(
                quoted_match.group(1), fallback
            )

        named_match = _NAMED_PROJECT_RE.search(text)
        if named_match:
            return WebsiteProjectNameManager.normalize_display_name(
                named_match.group(1), fallback
            )

        return WebsiteProjectNameManager.normalize_display_name(text, fallback)

    @staticmethod
    def slugify_project_name(
        value: str | None, fallback: str = DEFAULT_PROJECT_SLUG
    ) -> str:
        display_name = WebsiteProjectNameManager.normalize_display_name(
            value,
            fallback=DEFAULT_PROJECT_DISPLAY_NAME,
        )
        normalized = display_name.lower().replace("'", "").replace("\u2019", "")
        slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
        slug = re.sub(r"-{2,}", "-", slug)
        if not slug:
            slug = fallback
        slug = slug[:MAX_PROJECT_SLUG_LENGTH].strip("-") or fallback
        if slug in _RESERVED_WINDOWS_NAMES:
            slug = f"project-{slug}"
        return slug

    @staticmethod
    def safe_folder_name(
        value: str | None, fallback: str = DEFAULT_PROJECT_SLUG
    ) -> str:
        return WebsiteProjectNameManager.slugify_project_name(value, fallback=fallback)

    @staticmethod
    def build_project_name(
        prompt: str | None, fallback: str = DEFAULT_PROJECT_DISPLAY_NAME
    ) -> WebsiteProjectName:
        display_name = WebsiteProjectNameManager.extract_project_name(
            prompt, fallback=fallback
        )
        slug = WebsiteProjectNameManager.slugify_project_name(display_name)
        return WebsiteProjectName(
            display_name=display_name, slug=slug, folder_name=slug
        )

    @staticmethod
    def build_project_name_payload(
        prompt: str | None,
        fallback: str = DEFAULT_PROJECT_DISPLAY_NAME,
    ) -> dict[str, str]:
        return WebsiteProjectNameManager.build_project_name(
            prompt, fallback=fallback
        ).as_dict()
