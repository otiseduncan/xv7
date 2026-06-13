"""Site bundle artifact support for XV7/Xoduz multi-page website generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

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


def default_pages_for_business(business_name: str, question: str) -> list[str]:
    """Return the default file list for the detected business category."""
    q = question.lower()
    b = business_name.lower()
    if any(w in q or w in b for w in _FOOD_TERMS):
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


# ─── Path helpers ──────────────────────────────────────────────────────────────

_NAV_LABELS: dict[str, str] = {
    "index": "Home",
    "home": "Home",
    "about": "About",
    "menu": "Menu",
    "events": "Events",
    "contact": "Contact",
    "services": "Services",
    "gallery": "Gallery",
}


def page_label(path: str) -> str:
    name = path.split("/")[-1].replace(".html", "").replace("-", " ").replace("_", " ")
    return _NAV_LABELS.get(name.lower(), name.title())


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
    }
    low = label.strip().lower()
    if low in _ov:
        return _ov[low]
    slug = re.sub(r"[^a-z0-9]+", "-", low).strip("-")
    return f"{slug}.html" if slug else "page.html"


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
    """Build deterministic file contents for the entire site bundle."""
    colors = style_hints.get("colors", [])
    styles = [str(item).lower() for item in style_hints.get("styles", [])]
    bg = colors[0] if len(colors) > 0 else "#0a0a0a"
    accent = colors[1] if len(colors) > 1 else "#f97316"
    text_c = colors[2] if len(colors) > 2 else "#f5f5f5"
    body_font = "'Trebuchet MS', Arial, sans-serif"
    heading_font = body_font
    if any("blackletter" in item or "gothic" in item for item in styles):
        body_font = '"Old English Text MT", "UnifrakturMaguntia", Georgia, serif'
        heading_font = body_font
    elif any("script" in item or "cursive" in item for item in styles):
        heading_font = '"Brush Script MT", "Segoe Script", cursive'
    nav_html = build_nav_html(pages)
    css_path = next((p for p in pages if p.endswith(".css")), None)
    js_path = next((p for p in pages if p.endswith(".js")), None)
    link_tag = f'<link rel="stylesheet" href="/{css_path}">' if css_path else ""
    script_tag = f'<script src="/{js_path}" defer></script>' if js_path else ""

    def _page(path: str) -> str:
        lbl = page_label(path)
        is_home = path in {"index.html", "home.html"}
        hero = f"<h1>{business_name}</h1>" if is_home else f"<h1>{lbl}</h1>"
        copy_text = (
            f"<p>Welcome to {business_name}. Your premier destination for an unforgettable experience.</p>"
            if is_home
            else f"<p>{business_name} — {lbl} page.</p>"
        )
        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8" />',
                '<meta name="viewport" content="width=device-width, initial-scale=1" />',
                f"<title>{business_name} — {lbl}</title>",
                link_tag,
                "</head>",
                "<body>",
                nav_html,
                '<main class="page-content">',
                hero,
                copy_text,
                "</main>",
                script_tag,
                "</body>",
                "</html>",
            ]
        )

    css_content = "\n".join(
        [
            f"/* {business_name} — shared styles */",
            ":root {",
            f"  --bg: {bg};",
            f"  --accent: {accent};",
            f"  --text: {text_c};",
            f"  --body-font: {body_font};",
            f"  --heading-font: {heading_font};",
            "}",
            "*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }",
            "body { background: var(--bg); color: var(--text); font-family: var(--body-font); }",
            ".site-nav { display: flex; gap: 1.2rem; padding: 1rem 2rem; background: rgba(0,0,0,0.6); flex-wrap: wrap; }",
            ".site-nav a { color: var(--accent); text-decoration: none; font-weight: 600; "
            "letter-spacing: 0.06em; text-transform: uppercase; font-size: 0.85rem; }",
            ".site-nav a:hover { text-decoration: underline; }",
            ".page-content { max-width: 960px; margin: 3rem auto; padding: 0 1.5rem; }",
            "h1 { font-size: clamp(2rem, 6vw, 4rem); color: var(--accent); margin-bottom: 1rem; font-family: var(--heading-font); }",
            "p { line-height: 1.7; opacity: 0.88; }",
        ]
    )

    js_content = "\n".join(
        [
            f"/* {business_name} — site interactivity */",
            "document.addEventListener('DOMContentLoaded', function () {",
            "  var cur = window.location.pathname.split('/').pop() || 'index.html';",
            "  document.querySelectorAll('.site-nav a').forEach(function (a) {",
            "    if (a.getAttribute('href') === cur || a.getAttribute('href') === '/' + cur) {",
            "      a.style.textDecoration = 'underline';",
            "      a.setAttribute('aria-current', 'page');",
            "    }",
            "  });",
            "});",
        ]
    )

    files: list[dict[str, str]] = []
    for path in pages:
        if path.endswith(".html"):
            files.append({"path": path, "language": "html", "content": _page(path)})
        elif path.endswith(".css"):
            files.append({"path": path, "language": "css", "content": css_content})
        elif path.endswith(".js"):
            files.append(
                {"path": path, "language": "javascript", "content": js_content}
            )
    return files


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
