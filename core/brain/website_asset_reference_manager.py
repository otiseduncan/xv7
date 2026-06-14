"""Helpers for local website asset references.

The answer contract currently owns several small rules around generated site
assets: references should be local, root-relative asset links should be rewritten
to bundle-relative links, and generated HTML should use deterministic stylesheet
and script tags.  This manager keeps those pure rules isolated so the runtime
path can delegate to it later without mixing filesystem writes or response
composition into the extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_REMOTE_REFERENCE_RE = re.compile(
    r"^(?:https?:)?//|^(?:data|javascript):", re.IGNORECASE
)
_REFERENCE_ATTR_RE = re.compile(
    r"\b(?:href|src)\s*=\s*(['\"])(?P<value>.*?)\1",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class AssetReference:
    """A normalized local asset reference."""

    path: str
    kind: str
    extension: str


class WebsiteAssetReferenceManager:
    """Pure helpers for generated website asset references."""

    CSS_EXTENSIONS = frozenset({".css"})
    SCRIPT_EXTENSIONS = frozenset({".js", ".mjs"})
    IMAGE_EXTENSIONS = frozenset(
        {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
    )
    FONT_EXTENSIONS = frozenset({".eot", ".otf", ".ttf", ".woff", ".woff2"})

    @classmethod
    def normalize_asset_path(cls, value: object) -> str:
        """Return a slash-normalized relative asset path."""

        if value is None:
            return ""
        normalized = str(value).strip().replace("\\", "/")
        normalized = re.sub(r"/+", "/", normalized)
        while normalized.startswith("./"):
            normalized = normalized[2:]
        normalized = normalized.lstrip("/")
        return normalized.strip()

    @classmethod
    def is_remote_reference(cls, value: object) -> bool:
        """Return true when a reference points outside the generated bundle."""

        if value is None:
            return False
        return bool(_REMOTE_REFERENCE_RE.search(str(value).strip()))

    @classmethod
    def is_safe_local_reference(cls, value: object) -> bool:
        """Return true when a reference is local and does not traverse upward."""

        normalized = cls.normalize_asset_path(value)
        if not normalized or cls.is_remote_reference(value):
            return False
        parts = [part for part in normalized.split("/") if part]
        return bool(parts) and ".." not in parts

    @classmethod
    def extension_for_path(cls, value: object) -> str:
        """Return the lower-case extension for an asset path."""

        normalized = cls.normalize_asset_path(value)
        if "." not in normalized.rsplit("/", 1)[-1]:
            return ""
        return "." + normalized.rsplit(".", 1)[-1].lower()

    @classmethod
    def classify_asset(cls, value: object) -> str:
        """Classify a local asset reference by extension."""

        extension = cls.extension_for_path(value)
        if extension in cls.CSS_EXTENSIONS:
            return "stylesheet"
        if extension in cls.SCRIPT_EXTENSIONS:
            return "script"
        if extension in cls.IMAGE_EXTENSIONS:
            return "image"
        if extension in cls.FONT_EXTENSIONS:
            return "font"
        return "asset"

    @classmethod
    def make_reference(cls, value: object) -> AssetReference | None:
        """Build a normalized reference model, or None for unsafe references."""

        if not cls.is_safe_local_reference(value):
            return None
        path = cls.normalize_asset_path(value)
        extension = cls.extension_for_path(path)
        return AssetReference(
            path=path, kind=cls.classify_asset(path), extension=extension
        )

    @classmethod
    def asset_href(cls, filename: str, folder: str = "assets") -> str:
        """Build a deterministic bundle-relative href for an asset file."""

        folder_path = cls.normalize_asset_path(folder).strip("/") or "assets"
        file_path = cls.normalize_asset_path(filename).split("/")[-1]
        return f"{folder_path}/{file_path}" if file_path else folder_path

    @classmethod
    def stylesheet_link(cls, href: str = "assets/site.css") -> str:
        """Build the canonical stylesheet tag used by generated site bundles."""

        return f'<link rel="stylesheet" href="{cls.normalize_asset_path(href)}">'

    @classmethod
    def script_tag(cls, src: str = "assets/site.js", *, defer: bool = True) -> str:
        """Build the canonical script tag used by generated site bundles."""

        normalized = cls.normalize_asset_path(src)
        defer_attr = " defer" if defer else ""
        return f'<script src="{normalized}"{defer_attr}></script>'

    @classmethod
    def rewrite_bundle_relative_references(cls, markup: str) -> str:
        """Rewrite root-relative bundle assets to relative references."""

        text = str(markup or "")
        text = re.sub(r"(?P<quote>['\"])/assets/", r"\g<quote>assets/", text)
        return re.sub(r"(?P<quote>['\"])\./assets/", r"\g<quote>assets/", text)

    @classmethod
    def collect_remote_references(cls, markup: str) -> list[str]:
        """Collect remote href/src references from HTML markup."""

        remotes: list[str] = []
        for match in _REFERENCE_ATTR_RE.finditer(str(markup or "")):
            value = match.group("value").strip()
            if cls.is_remote_reference(value):
                remotes.append(value)
        return remotes
