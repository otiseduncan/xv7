from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


def slugify_artifact_name(value: str) -> str:
    """Slugify an artifact name into a URL-safe kebab-case string."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "artifact"


def safe_slug(raw: str | None, fallback: str) -> str:
    """Return a clean, bounded slug; fall back to slugifying *fallback*."""
    base = slugify_artifact_name(str(raw or "").strip())
    if not base:
        base = slugify_artifact_name(fallback)
    base = re.sub(r"-{2,}", "-", base).strip("-")
    if len(base) > 48:
        base = base[:48].rstrip("-")
    return base or slugify_artifact_name(fallback)


def content_sha256(content: str) -> str:
    """Return the SHA-256 hex digest of *content* (UTF-8 encoded)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """Return the current UTC datetime as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
