"""Site bundle artifact support for XV7/Xoduz multi-page website generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.brain.website_business_type_manager import WebsiteBusinessTypeManager
from core.brain.website_design_renderer import (
    page_label as render_page_label,
    render_site_bundle_files,
)
from core.brain.website_page_plan_manager import WebsitePagePlanManager

# ─── Intent detection ──────────────────────────────────────────────────────────

SITE_BUNDLE_ACTION_PATTERN = re.compile(r"\b(create|build|make|generate|draft)\b")
SITE_BUNDLE_HINT_PATTERN = re.compile(r"\b(website|site)\b")
SITE_BUNDLE_INTENT_PATTERN = re.compile(
    r"\b(full website|multi.?page|multipage|"
    r"[3-9] page website|[3-9]-page website|[3-9] pages?|"
    r"home.{1,40}about.{1,40}(?:services|menu|contact)|"
    r"(?:index|home).{1,40}(?:about|menu|services).{1,40}contact)\b",
    re.IGNORECASE,
)
_WEBSITE_ARTIFACT_PATTERN = re.compile(
    r"\b(?:create|build|make|generate|draft)\s+a\s+(?:\d+[- ]page\s+)?(?:website|site)\s+artifact\b",
    re.IGNORECASE,
)
_EXPLICIT_SINGLE_PATTERN = re.compile(
    r"\b(html artifact|code artifact|draft html|inline html|single-file html|single file html|"
    r"one-page html artifact|one page html artifact|generate html artifact|create html artifact)\b"
)


def is_site_bundle_request(normalized_question: str) -> bool:
    """Return True when the prompt clearly requests a multi-page website bundle."""

    if _EXPLICIT_SINGLE_PATTERN.search(normalized_question):
        return False
    if _WEBSITE_ARTIFACT_PATTERN.search(normalized_question):
        return True
    has_action = bool(SITE_BUNDLE_ACTION_PATTERN.search(normalized_question))
    has_site_hint = bool(SITE_BUNDLE_HINT_PATTERN.search(normalized_question))
    has_multi_hint = bool(SITE_BUNDLE_INTENT_PATTERN.search(normalized_question))
    return has_action and has_site_hint and has_multi_hint


# ─── Default page selection ────────────────────────────────────────────────────

_FOOD_TERMS = (
    "tavern",
    "bar",
    "pub",
    "grill",
    "restaurant",
    "diner",
    "cafe",
    "coffee",
    "brewery",
    "bistro",
    "pizzeria",
    "sushi",
    "bbq",
    "barbeque",
)
_FOOD_BUSINESS_TYPES = {"food_cart", "restaurant"}


def default_pages_for_business(business_name: str, question: str) -> list[str]:
    """Return the default file list for the detected business category."""

    requested_pages = extract_requested_page_paths(question)
    if requested_pages:
        pages = [
            "index.html",
            *[page for page in requested_pages if page != "index.html"],
        ]
        return [*pages, "assets/site.css", "assets/site.js"]

    prompt_context = f"{business_name} {question}"
    business_type = WebsiteBusinessTypeManager.infer_business_type(prompt_context)
    q = question.lower()
    b = business_name.lower()
    has_legacy_food_term = any(w in q or w in b for w in _FOOD_TERMS)
    if business_type.kind in _FOOD_BUSINESS_TYPES or has_legacy_food_term:
        return [
            "index.html",
            "about.html",
            "menu.html",
            "events.html",
            "contact.html",
            "assets/site.css",
            "assets/site.js",
        ]
    return [
        "index.html",
        "about.html",
        "services.html",
        "gallery.html",
        "contact.html",
        "assets/site.css",
        "assets/site.js",
    ]


# ─── Path helpers ─────────────────────────────────────────────────────────────


def page_label(path: str) -> str:
    return render_page_label(path)


def is_safe_bundle_path(path: str) -> bool:
    """True when path is safe: relative, no traversal, no shell metacharacters."""

    if not isinstance(path, str) or not path.strip():
        return False
    p = path.strip().replace("\\", "/")
    if p.startswith("/") or re.match(r"^[A-Za-z]:", p):
        return False
    if ".." in p.split("/"):
        return False
    if re.search(r"[;&|`$<>]", p):
        return False
    return True


def normalize_page_path(label: str) -> str:
    """Convert 'Our Services' -> 'services.html'."""

    _ov: dict[str, str] = {
        "home": "index.html",
        "homepage": "index.html",
        "landing": "index.html",
        "about us": "about.html",
        "about me": "about.html",
        "our story": "about.html",
        "products": "products.html",
        "our products": "products.html",
        "product": "products.html",
        "faq": "faq.html",
        "faqs": "faq.html",
        "frequently asked questions": "faq.html",
        "menu": "menu.html",
        "food menu": "menu.html",
        "our menu": "menu.html",
        "events": "events.html",
        "upcoming events": "events.html",
        "contact us": "contact.html",
        "get in touch": "contact.html",
        "services": "services.html",
        "our services": "services.html",
        "gallery": "gallery.html",
        "photo gallery": "gallery.html",
        "photos": "gallery.html",
        "specials": "specials.html",
        "deals": "specials.html",
        "offers": "specials.html",
        "catering": "catering.html",
        "locations": "locations.html",
        "location": "locations.html",
        "pricing": "pricing.html",
        "prices": "pricing.html",
        "reviews": "reviews.html",
        "testimonials": "reviews.html",
        "portfolio": "portfolio.html",
        "booking": "booking.html",
        "book": "booking.html",
        "aftercare": "aftercare.html",
        "rentals": "rentals.html",
        "safety": "safety.html",
        "guided tours": "guided-tours.html",
        "tours": "guided-tours.html",
    }
    low = label.strip().lower()
    if low in _ov:
        return _ov[low]
    slug = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
    return f"{slug}.html" if slug else "page.html"


def _page_aliases() -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = [
        ("frequently asked questions", "faq"),
        ("home", "home"),
        ("products", "products"),
        ("product", "products"),
    ]
    for alias, title in WebsitePagePlanManager.PAGE_ALIASES:
        aliases.append((alias, WebsitePagePlanManager.page_slug(title)))
    aliases.extend(
        [
            ("faq", "faq"),
            ("faqs", "faq"),
            ("events", "events"),
            ("deals", "specials"),
            ("offers", "specials"),
            ("testimonials", "reviews"),
        ]
    )
    return aliases


def extract_requested_page_paths(question: str) -> list[str]:
    """Extract explicitly requested page names in prompt order."""

    if not isinstance(question, str) or not question.strip():
        return []

    lowered = question.lower()
    hits: list[tuple[int, str]] = []
    for token, canonical in _page_aliases():
        pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
        for match in pattern.finditer(lowered):
            hits.append((match.start(), canonical))

    if len(hits) < 2:
        return []

    hits.sort(key=lambda item: item[0])
    ordered: list[str] = []
    seen: set[str] = set()
    for _, canonical in hits:
        if canonical in seen:
            continue
        seen.add(canonical)
        ordered.append(canonical)

    if len(ordered) < 2:
        return []

    normalized = [normalize_page_path(label) for label in ordered]
    html_only = [path for path in normalized if path.endswith(".html")]
    if len(html_only) < 2:
        return []
    return html_only


# ─── File content generation ───────────────────────────────────────────────────


def build_nav_html(pages: list[str]) -> str:
    html_pages = [p for p in pages if p.endswith(".html")]
    links = "".join(f'<a href="{p}">{page_label(p)}</a>' for p in html_pages)
    return f'<nav class="site-nav">{links}</nav>'


def build_bundle_files(
    *,
    business_name: str,
    slug: str,
    pages: list[str],
    style_hints: dict[str, list[str]],
    question: str,
) -> list[dict[str, str]]:
    """Build deterministic, polished file contents for the entire site bundle."""

    return render_site_bundle_files(
        business_name=business_name,
        slug=slug,
        pages=pages,
        style_hints=style_hints,
        question=question,
    )


# ─── Validation ────────────────────────────────────────────────────────────────


def validate_bundle(
    *,
    bundle_files: list[dict[str, str]],
    entry: str,
    business_name: str,
    style_hints: dict[str, list[str]],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    paths = [f.get("path", "") for f in bundle_files]
    if entry not in paths:
        failures.append(f"entry file {entry!r} missing from bundle")
    html_pages = [f for f in bundle_files if str(f.get("path", "")).endswith(".html")]
    if len(html_pages) < 2:
        failures.append("bundle must have at least 2 HTML pages")
    for f in bundle_files:
        path = str(f.get("path", ""))
        if not is_safe_bundle_path(path):
            failures.append(f"unsafe bundle path: {path!r}")
        content = str(f.get("content", ""))
        if path.endswith(".html") and business_name:
            if business_name.lower() not in content.lower():
                failures.append(f"business name missing from {path!r}")

    requested_colors = [str(color).strip() for color in style_hints.get("colors", [])]
    css_content = "\n".join(
        str(f.get("content", ""))
        for f in bundle_files
        if str(f.get("path", "")).endswith(".css")
    ).lower()
    for color in requested_colors:
        if color and color.lower() not in css_content:
            failures.append(f"requested color missing from css: {color!r}")
    return (len(failures) == 0, failures)


# ─── Patch proposal construction ───────────────────────────────────────────────


def build_patch_proposals(
    *,
    bundle_files: list[dict[str, str]],
    slug: str,
    root: Path,
    validate_fn: Any,
    diff_fn: Any,
) -> list[dict[str, Any]]:
    """Return one patch proposal dict per file in the bundle."""

    proposals: list[dict[str, Any]] = []
    for f in bundle_files:
        path = str(f.get("path", ""))
        content = str(f.get("content", ""))
        language = str(f.get("language", "html"))
        if not is_safe_bundle_path(path):
            continue
        target_path = f"generated-sites/{slug}/{path}"
        resolved_target = (root / Path(target_path)).resolve()
        existing_content: str | None = (
            resolved_target.read_text(encoding="utf-8")
            if resolved_target.exists()
            else None
        )
        operation = "update" if existing_content is not None else "create"
        validation_status, checks, validation_failures = validate_fn(
            root=root,
            target_path=target_path,
            content=content,
            language=language,
            business_name="",
            operation=operation,
        )
        diff_text = diff_fn(
            target_path=target_path,
            before_content=existing_content,
            after_content=content,
        )
        proposals.append(
            {
                "type": "artifact_patch_proposal",
                "proposal_id": f"patch-{uuid4().hex[:12]}",
                "target_path": target_path,
                "operation": operation,
                "language": language,
                "applied": False,
                "requires_confirmation": True,
                "content": content,
                "diff": diff_text,
                "validation": {
                    "status": validation_status,
                    "checks": checks,
                    "failures": validation_failures,
                },
            }
        )
    return proposals


# ─── Apply ─────────────────────────────────────────────────────────────────────


def apply_proposals(
    *,
    proposals: list[dict[str, Any]],
    root: Path,
    resolve_fn: Any,
) -> tuple[list[str], list[str]]:
    """Apply each proposal to disk. Returns (written_paths, errors)."""

    written: list[str] = []
    errors: list[str] = []
    for proposal in proposals:
        v = proposal.get("validation") or {}
        if str(v.get("status") or "failed").lower() != "passed":
            errors.append(
                f"skipped {proposal.get('target_path')}: validation not passed"
            )
            continue
        target_path = str(proposal.get("target_path") or "").replace("\\", "/")
        content = str(proposal.get("content") or "")
        target, resolve_error = resolve_fn(root=root, target_path=target_path)
        if target is None:
            errors.append(f"skipped {target_path}: {resolve_error or 'unsafe path'}")
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(target_path)
        except OSError as exc:
            errors.append(f"failed {target_path}: {exc}")
    return written, errors


# ─── Session lookup helpers ────────────────────────────────────────────────────


def latest_pending_bundle_proposals(
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    if isinstance(session_messages, list):
        for message in reversed(session_messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role") or "").lower() != "assistant":
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            proposals = metadata.get("site_bundle_patch_proposals")
            if isinstance(proposals, list) and proposals:
                if not any(p.get("applied") for p in proposals):
                    return proposals
    if isinstance(session_metadata, dict):
        payload = session_metadata.get("last_assistant_payload")
        if isinstance(payload, dict):
            proposals = payload.get("site_bundle_patch_proposals")
            if isinstance(proposals, list) and proposals:
                if not any(p.get("applied") for p in proposals):
                    return proposals
    return None


def latest_bundle_artifact(
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(session_messages, list):
        for message in reversed(session_messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role") or "").lower() != "assistant":
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            bundle = metadata.get("site_bundle")
            if (
                isinstance(bundle, dict)
                and bundle.get("artifact_type") == "site_bundle"
            ):
                return bundle
    if isinstance(session_metadata, dict):
        payload = session_metadata.get("last_assistant_payload")
        if isinstance(payload, dict):
            bundle = payload.get("site_bundle")
            if (
                isinstance(bundle, dict)
                and bundle.get("artifact_type") == "site_bundle"
            ):
                return bundle
    return None
