"""Site bundle artifact support for XV7/Xoduz multi-page website generation."""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.brain.website_business_type_manager import WebsiteBusinessTypeManager
from core.brain.website_design_renderer import (
    build_site_design_spec,
    page_label as render_page_label,
    render_site_bundle_files,
)
from core.brain.website_page_plan_manager import WebsitePagePlanManager

SITE_BUNDLE_ACTION_PATTERN = re.compile(
    r"\b(generate|preview|show|display|draft|mock\s*up|mockup)\b"
)
SITE_BUNDLE_HINT_PATTERN = re.compile(r"\b(website|site)\b")
SITE_SANDBOX_WRITE_PATTERN = re.compile(
    r"\b(build|write|create|export|save)\b|\bpublish\s+to\s+sandbox\b",
    re.IGNORECASE,
)
CONCEPTUAL_WEBSITE_QUESTION_PATTERN = re.compile(
    r"^(what|how|why|which)\b.*\b(website|site|preview|builder|generated websites?)\b",
    re.IGNORECASE,
)
SITE_BUNDLE_INTENT_PATTERN = re.compile(
    r"\b(full website|multi.?page|multipage|"
    r"[3-9] page website|[3-9]-page website|[3-9] pages?|"
    r"home.{1,40}about.{1,40}(?:services|menu|contact)|"
    r"(?:index|home).{1,40}(?:about|menu|services).{1,40}contact)\b",
    re.IGNORECASE,
)
_WEBSITE_ARTIFACT_PATTERN = re.compile(
    r"\b(?:create|build|make|generate|draft)\s+a\s+"
    r"(?:\d+[- ]page\s+)?(?:website|site)\s+artifact\b",
    re.IGNORECASE,
)
_EXPLICIT_SINGLE_PATTERN = re.compile(
    r"\b(html artifact|code artifact|draft html|inline html|single-file html|single file html|"
    r"one-page html artifact|one page html artifact|generate html artifact|create html artifact)\b"
)

_FOOD_TERMS = (
    "hot dog",
    "hotdog",
    "food cart",
    "food truck",
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

_PAGE_OVERRIDES = {
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
    "hours": "hours.html",
}

_BANNED_TEMPLATE_PHRASES = (
    "premier destination for an unforgettable experience",
    "lorem ipsum",
    "your business name",
    "replace this text",
)
_REQUIRED_HTML_MARKERS = ("site-header", "page-content")
_REQUIRED_CSS_MARKERS = (
    "--bg:",
    "--accent:",
    "--text:",
    "site-header",
    "button-primary",
)


def is_site_bundle_request(normalized_question: str) -> bool:
    """Return True when the prompt clearly requests a multi-page website bundle."""

    if CONCEPTUAL_WEBSITE_QUESTION_PATTERN.search(
        normalized_question
    ) and not re.search(
        r"\b(generate|create|build|draft|write|export|save|revise|change|make me|show me)\b",
        normalized_question,
    ):
        return False
    if _EXPLICIT_SINGLE_PATTERN.search(normalized_question):
        return False
    if SITE_SANDBOX_WRITE_PATTERN.search(normalized_question) and not (
        _WEBSITE_ARTIFACT_PATTERN.search(normalized_question)
        or re.search(
            r"\b(generate|preview|show|display|draft|mock\s*up|mockup)\b",
            normalized_question,
        )
    ):
        return False
    if re.search(
        r"\b(change|revise|edit|update|restyle|refresh|tweak|adjust|rewrite|switch|preserve|keep|undo|revert)\b",
        normalized_question,
    ):
        return False
    if _WEBSITE_ARTIFACT_PATTERN.search(normalized_question):
        return True
    has_action = bool(SITE_BUNDLE_ACTION_PATTERN.search(normalized_question))
    has_site_hint = bool(SITE_BUNDLE_HINT_PATTERN.search(normalized_question))
    has_multi_hint = bool(SITE_BUNDLE_INTENT_PATTERN.search(normalized_question))
    return has_multi_hint or (has_action and has_site_hint)


def default_pages_for_business(business_name: str, question: str) -> list[str]:
    """Return the default file list for the detected business category."""

    prompt_context = f"{business_name} {question}"
    business_type = WebsiteBusinessTypeManager.infer_business_type(prompt_context)
    lowered_question = question.lower()
    lowered_business = business_name.lower()
    has_legacy_food_term = any(
        term in lowered_question or term in lowered_business for term in _FOOD_TERMS
    )
    if business_type.kind in _FOOD_BUSINESS_TYPES or has_legacy_food_term:
        pages = [
            "index.html",
            "menu.html",
            "specials.html",
            "events.html",
            "catering.html",
            "hours.html",
            "about.html",
            "contact.html",
            "assets/site.css",
            "assets/site.js",
        ]
        return merge_requested_pages(pages, question)
    pages = [
        "index.html",
        "about.html",
        "services.html",
        "gallery.html",
        "contact.html",
        "assets/site.css",
        "assets/site.js",
    ]
    return merge_requested_pages(pages, question)


def merge_requested_pages(existing_pages: list[str], follow_up: str) -> list[str]:
    """Return existing bundle paths plus any pages explicitly requested later."""

    merged: list[str] = []
    seen: set[str] = set()
    for page in existing_pages:
        normalized = str(page or "").replace("\\", "/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)

    for page in extract_requested_page_paths(follow_up):
        if page not in seen:
            seen.add(page)
            insert_at = next(
                (
                    index
                    for index, existing in enumerate(merged)
                    if existing.startswith("assets/")
                ),
                len(merged),
            )
            merged.insert(insert_at, page)

    if "assets/site.css" not in seen:
        merged.append("assets/site.css")
    if "assets/site.js" not in seen:
        merged.append("assets/site.js")
    return merged


def page_label(path: str) -> str:
    return render_page_label(path)


def is_safe_bundle_path(path: str) -> bool:
    """True when path is safe: relative, no traversal, no shell metacharacters."""

    if not isinstance(path, str) or not path.strip():
        return False
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return False
    if ".." in normalized.split("/"):
        return False
    return not bool(re.search(r"[;&|`$<>]", normalized))


def normalize_page_path(label: str) -> str:
    """Convert a page label into a safe HTML file path."""

    lowered = label.strip().lower()
    if lowered in _PAGE_OVERRIDES:
        return _PAGE_OVERRIDES[lowered]
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return f"{slug}.html" if slug else "page.html"


def _page_aliases() -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = [
        ("frequently asked questions", "faq"),
        ("home", "home"),
        ("products", "products"),
        ("product", "products"),
    ]
    aliases.extend(
        (alias, WebsitePagePlanManager.page_slug(title))
        for alias, title in WebsitePagePlanManager.PAGE_ALIASES
    )
    aliases.extend(
        [
            ("faq", "faq"),
            ("faqs", "faq"),
            ("events", "events"),
            ("deals", "specials"),
            ("offers", "specials"),
            ("testimonials", "reviews"),
            ("hours", "hours"),
        ]
    )
    return aliases


def extract_requested_page_paths(question: str) -> list[str]:
    """Extract explicitly requested page names in prompt order."""

    if not isinstance(question, str) or not question.strip():
        return []

    hits: list[tuple[int, str]] = []
    lowered = question.lower()
    for token, canonical in _page_aliases():
        pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
        hits.extend((match.start(), canonical) for match in pattern.finditer(lowered))

    if not hits:
        return []
    hits.sort(key=lambda item: item[0])

    ordered: list[str] = []
    seen: set[str] = set()
    for _, canonical in hits:
        if canonical in seen:
            continue
        seen.add(canonical)
        ordered.append(canonical)

    normalized = [normalize_page_path(label) for label in ordered]
    html_only = [path for path in normalized if path.endswith(".html")]
    return html_only


def build_nav_html(pages: list[str]) -> str:
    html_pages = [page for page in pages if page.endswith(".html")]
    links = "".join(f'<a href="{page}">{page_label(page)}</a>' for page in html_pages)
    return f'<nav class="site-nav">{links}</nav>'


def build_bundle_files(
    *,
    business_name: str,
    slug: str,
    pages: list[str],
    style_hints: dict[str, list[str]],
    question: str,
) -> list[dict[str, str]]:
    """Build deterministic, polished file contents for the entire site bundle.

    This wrapper is an intentional contract boundary for callers that depend on
    site_bundle naming while renderer internals evolve behind it.
    """

    return render_site_bundle_files(
        business_name=business_name,
        slug=slug,
        pages=pages,
        style_hints=style_hints,
        question=question,
    )


def build_design_spec_payload(
    *,
    business_name: str,
    slug: str,
    pages: list[str],
    style_hints: dict[str, list[str]],
    question: str,
) -> dict[str, Any]:
    """Build the JSON-safe design model used for a site bundle render."""

    spec = build_site_design_spec(
        business_name=business_name,
        slug=slug,
        pages=pages,
        style_hints=style_hints,
        question=question,
    )
    return json.loads(json.dumps(asdict(spec)))


def refine_bundle_files(
    *,
    existing_files: list[dict[str, Any]],
    business_name: str,
    slug: str,
    pages: list[str],
    style_hints: dict[str, list[str]],
    follow_up: str,
    source_prompt: str,
) -> list[dict[str, str]]:
    """Mutate an active site bundle without replacing its existing page bodies."""

    safe_existing = [
        {
            "path": str(item.get("path") or ""),
            "language": str(
                item.get("language") or _language_for_path(str(item.get("path") or ""))
            ),
            "content": str(item.get("content") or ""),
        }
        for item in existing_files
        if isinstance(item, dict) and is_safe_bundle_path(str(item.get("path") or ""))
    ]
    if not safe_existing:
        return build_bundle_files(
            business_name=business_name,
            slug=slug,
            pages=pages,
            style_hints=style_hints,
            question=f"{source_prompt}\n{follow_up}".strip(),
        )

    signals = _refinement_signals(follow_up, style_hints.get("styles", []))
    colors = [
        str(color).strip()
        for color in style_hints.get("colors", [])
        if str(color).strip()
    ]
    named_special = _extract_named_special(follow_up)
    refined: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    for item in safe_existing:
        path = item["path"]
        seen_paths.add(path)
        content = item["content"]
        language = item["language"] or _language_for_path(path)
        if path.endswith(".css"):
            content = _refine_css(content, colors=colors, signals=signals)
        elif path.endswith(".html"):
            content = _refine_html(
                content,
                path=path,
                business_name=business_name,
                named_special=named_special,
                signals=signals,
            )
        refined.append({"path": path, "language": language, "content": content})

    for page in pages:
        if page in seen_paths:
            continue
        rendered = build_bundle_files(
            business_name=business_name,
            slug=slug,
            pages=[page],
            style_hints=style_hints,
            question=f"{source_prompt}\n{follow_up}".strip(),
        )
        refined.extend(item for item in rendered if item.get("path") == page)
    return refined


def _language_for_path(path: str) -> str:
    if path.endswith(".css"):
        return "css"
    if path.endswith(".js"):
        return "javascript"
    return "html"


def _refinement_signals(follow_up: str, styles: list[str]) -> dict[str, bool]:
    lowered = f"{follow_up or ''} {' '.join(styles)}".lower()
    return {
        "premium": any(
            term in lowered
            for term in ("premium", "luxury", "high end", "high-end", "polished")
        ),
        "bold": any(
            term in lowered
            for term in (
                "bold",
                "pop",
                "buttons pop",
                "make the buttons",
                "bigger buttons",
            )
        ),
        "less_template": any(
            term in lowered
            for term in (
                "less template",
                "template-looking",
                "not template",
                "less basic",
                "more custom",
            )
        ),
        "specials": any(
            term in lowered for term in ("special", "specials", "deal", "offer")
        ),
    }


def _extract_named_special(follow_up: str) -> str:
    text = " ".join((follow_up or "").split())
    patterns = (
        r"add (?:a |an |the )?(?P<name>[A-Z0-9][A-Za-z0-9 '&-]{2,60}? special)",
        r"include (?:a |an |the )?(?P<name>[A-Z0-9][A-Za-z0-9 '&-]{2,60}? special)",
        r"(?P<name>[A-Z0-9][A-Za-z0-9 '&-]{2,60}? special)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group("name").strip(" .,!?").title()
    return ""


def _refine_html(
    content: str,
    *,
    path: str,
    business_name: str,
    named_special: str,
    signals: dict[str, bool],
) -> str:
    updated = content
    classes = []
    if signals["premium"]:
        classes.append("is-premium")
    if signals["bold"]:
        classes.append("is-bold")
    if signals["less_template"]:
        classes.append("is-customized")
    updated = _add_body_classes(updated, classes)

    if path == "index.html" and signals["premium"]:
        updated = _insert_before_main_close(
            updated,
            "premium-band",
            "\n".join(
                [
                    '  <section class="premium-band">',
                    '    <p class="eyebrow">Premium revision applied</p>',
                    f"    <h2>{html.escape(business_name, quote=False)} now has stronger visual hierarchy.</h2>",
                    "    <p>Sharper contrast, richer spacing, and bolder calls to action make this version feel more finished.</p>",
                    "  </section>",
                ]
            ),
        )
    if path == "index.html" and signals["less_template"]:
        updated = _insert_before_main_close(
            updated,
            "custom-band",
            "\n".join(
                [
                    '  <section class="custom-band">',
                    '    <p class="eyebrow">Less template-looking</p>',
                    f"    <h2>Specific sections still support {html.escape(business_name, quote=False)}.</h2>",
                    "    <p>The existing pages stay intact while the active revision gains more custom structure.</p>",
                    "  </section>",
                ]
            ),
        )
    if named_special and (path in {"index.html", "menu.html", "specials.html"}):
        updated = _insert_before_main_close(
            updated, _slug_token(named_special), _special_card(named_special)
        )
    return updated


def _add_body_classes(content: str, classes: list[str]) -> str:
    if not classes:
        return content

    def replace(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        existing = match.group("classes")
        suffix = match.group("suffix")
        tokens = existing.split()
        for class_name in classes:
            if class_name not in tokens:
                tokens.append(class_name)
        return f"{prefix}{' '.join(tokens)}{suffix}"

    if re.search(r"<body[^>]*class=", content, re.IGNORECASE):
        return re.sub(
            r"(?P<prefix><body[^>]*class=[\"'])(?P<classes>[^\"']*)(?P<suffix>[\"'][^>]*>)",
            replace,
            content,
            count=1,
            flags=re.IGNORECASE,
        )
    return re.sub(
        r"<body\b([^>]*)>",
        lambda match: f'<body class="{" ".join(classes)}"{match.group(1)}>',
        content,
        count=1,
        flags=re.IGNORECASE,
    )


def _insert_before_main_close(content: str, marker: str, block: str) -> str:
    if marker.lower() in content.lower():
        return content
    match = re.search(r"</main>", content, re.IGNORECASE)
    if match:
        return f"{content[: match.start()]}{block}\n{content[match.start() :]}"
    return f"{content.rstrip()}\n{block}\n"


def _special_card(named_special: str) -> str:
    return "\n".join(
        [
            '  <section class="spotlight-section xv7-specials">',
            '    <p class="eyebrow">Specials spotlight</p>',
            '    <div class="card-grid compact-grid">',
            '      <article class="info-card deal-card">',
            "        <span>Special</span>",
            f"        <h2>{html.escape(named_special, quote=False)}</h2>",
            "        <p>Added from the latest refinement request while preserving the existing menu, pages, and calls to action.</p>",
            "      </article>",
            "    </div>",
            "  </section>",
        ]
    )


def _slug_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _refine_css(content: str, *, colors: list[str], signals: dict[str, bool]) -> str:
    updated = content
    if colors:
        resolved = [_color_value(color) for color in colors]
        bg = resolved[0] if len(resolved) > 0 else "#050505"
        accent = resolved[1] if len(resolved) > 1 else bg
        text = resolved[2] if len(resolved) > 2 else "#ffffff"
        accent_2 = resolved[3] if len(resolved) > 3 else text
        for name, value in (
            ("bg", bg),
            ("accent", accent),
            ("text", text),
            ("accent-2", accent_2),
            ("requested-1", colors[0] if len(colors) > 0 else "default"),
            ("requested-2", colors[1] if len(colors) > 1 else "default"),
            ("requested-3", colors[2] if len(colors) > 2 else "default"),
            ("requested-4", colors[3] if len(colors) > 3 else "default"),
        ):
            updated = _set_css_var(updated, name, value)
        updated = _replace_or_add_comment(updated, "requested-colors", " ".join(colors))
    if signals["bold"]:
        updated = _set_css_var(updated, "button-scale", "1.08")
        if ".is-bold h1" not in updated:
            updated = f"{updated.rstrip()}\n.is-bold h1 {{ text-shadow: 0 16px 50px color-mix(in srgb, var(--accent) 22%, transparent); }}\n"
    if signals["premium"] and ".is-premium .hero-card" not in updated:
        updated = f"{updated.rstrip()}\n.is-premium .hero-card, .is-premium .info-card {{ border-color: color-mix(in srgb, var(--accent) 48%, transparent); }}\n"
    return updated


def _replace_or_add_comment(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"/\*\s*{re.escape(key)}:\s*.*?\*/", re.IGNORECASE)
    replacement = f"/* {key}: {value} */"
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    return f"{replacement}\n{content}"


def _set_css_var(content: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(--{re.escape(name)}\s*:\s*)[^;]+;", re.IGNORECASE)
    if pattern.search(content):
        return pattern.sub(rf"\g<1>{value};", content, count=1)
    root_match = re.search(r":root\s*\{", content, re.IGNORECASE)
    if root_match:
        insert_at = root_match.end()
        return f"{content[:insert_at]}\n  --{name}: {value};{content[insert_at:]}"
    return f":root {{\n  --{name}: {value};\n}}\n{content}"


def _color_value(color: str) -> str:
    token = color.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}(?:[0-9a-f]{3})?", token):
        return token
    return {
        "black": "#050505",
        "white": "#ffffff",
        "gold": "#f59e0b",
        "yellow": "#facc15",
        "red": "#ef4444",
        "green": "#22c55e",
        "blue": "#3b82f6",
        "orange": "#f97316",
        "purple": "#8b5cf6",
    }.get(token, color)


def apply_design_intent_to_css(css_content: str, design_mods: dict[str, Any]) -> str:
    """Apply design intent modifications to CSS content."""

    if not design_mods:
        return css_content

    updated = css_content

    # Apply background brightness changes
    if design_mods.get("background_brightness"):
        brightness_val = design_mods["background_brightness"]
        updated = _set_css_var(
            updated, "brightness", f"brightness({1 + brightness_val})"
        )

    # Apply text contrast changes
    if design_mods.get("text_contrast"):
        contrast_val = design_mods["text_contrast"]
        updated = _set_css_var(updated, "contrast", f"contrast({contrast_val})")

    # Apply glow strength
    if design_mods.get("glow_strength"):
        glow = design_mods["glow_strength"]
        if design_mods.get("button_glow"):
            glow_css = f"\nbutton, .button, [role='button'] {{ filter: drop-shadow(0 0 {8 * glow}px var(--accent, #4db8ff)); }}\n"
            updated = f"{updated.rstrip()}{glow_css}"
        if design_mods.get("card_glow"):
            card_glow = f"\n.card, .info-card {{ filter: drop-shadow(0 0 {6 * glow}px color-mix(in srgb, var(--accent, #4db8ff) {40 * glow}%, transparent)); }}\n"
            updated = f"{updated.rstrip()}{card_glow}"
        if design_mods.get("hero_glow"):
            hero_glow = f"\n.hero-section, .hero-card {{ filter: drop-shadow(0 0 {10 * glow}px color-mix(in srgb, var(--accent, #4db8ff) {45 * glow}%, transparent)); }}\n"
            updated = f"{updated.rstrip()}{hero_glow}"

    # Apply translucent effects
    if design_mods.get("translucent_alpha"):
        alpha = design_mods["translucent_alpha"]
        blur_px = design_mods.get("backdrop_blur", 12)
        trans_css = f"\n.card, .info-card, .panel {{ background: color-mix(in srgb, currentColor {alpha * 100}%, transparent) !important; backdrop-filter: blur({blur_px}px); }}\n"
        updated = f"{updated.rstrip()}{trans_css}"

    # Apply font scaling
    if design_mods.get("font_scale") and design_mods["font_scale"] != 1.0:
        scale = design_mods["font_scale"]
        updated = _set_css_var(updated, "font-scale", str(scale))
        font_css = f"\nbody {{ font-size: calc(1rem * var(--font-scale, {scale})); }}\nh1 {{ font-size: calc(2.4rem * var(--font-scale, {scale})); }}\nh2 {{ font-size: calc(1.8rem * var(--font-scale, {scale})); }}\n"
        updated = f"{updated.rstrip()}{font_css}"

    # Apply spacing scaling
    if design_mods.get("spacing_scale") and design_mods["spacing_scale"] != 1.0:
        scale = design_mods["spacing_scale"]
        updated = _set_css_var(updated, "spacing-scale", str(scale))
        spacing_css = f"\nsection, .section {{ margin: calc(2rem * var(--spacing-scale, {scale})); padding: calc(1.5rem * var(--spacing-scale, {scale})); }}\n"
        updated = f"{updated.rstrip()}{spacing_css}"

    # Apply shadow strength
    if design_mods.get("shadow_strength") and design_mods["shadow_strength"] != 1.0:
        shadow = design_mods["shadow_strength"]
        updated = _set_css_var(updated, "shadow-strength", str(shadow))

    return updated


def validate_bundle(
    *,
    bundle_files: list[dict[str, str]],
    entry: str,
    business_name: str,
    style_hints: dict[str, list[str]],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    paths = [str(file_item.get("path", "")) for file_item in bundle_files]
    if entry not in paths:
        failures.append(f"entry file {entry!r} missing from bundle")

    html_pages = [
        file_item
        for file_item in bundle_files
        if str(file_item.get("path", "")).endswith(".html")
    ]
    if len(html_pages) < 2:
        failures.append("bundle must have at least 2 HTML pages")

    css_files = [
        file_item
        for file_item in bundle_files
        if str(file_item.get("path", "")).endswith(".css")
    ]
    if not css_files:
        failures.append("bundle must include a CSS file")

    signatures: set[str] = set()
    for file_item in bundle_files:
        path = str(file_item.get("path", ""))
        content = str(file_item.get("content", ""))
        lowered = content.lower()
        if not is_safe_bundle_path(path):
            failures.append(f"unsafe bundle path: {path!r}")
        if not content.strip():
            failures.append(f"empty bundle content: {path!r}")
            continue
        if any(phrase in lowered for phrase in _BANNED_TEMPLATE_PHRASES):
            failures.append(f"generic template copy found in {path!r}")
        if path.endswith(".html"):
            failures.extend(
                _validate_html_file(path, content, lowered, business_name, entry)
            )
            signatures.add(_normalize_quality_signature(content))

    if len(html_pages) > 1 and len(signatures) < len(html_pages):
        failures.append("html pages must not be duplicate template copies")

    css_content = "\n".join(
        str(file_item.get("content", "")) for file_item in css_files
    ).lower()
    for marker in _REQUIRED_CSS_MARKERS:
        if marker not in css_content:
            failures.append(f"css quality marker missing: {marker!r}")
    for color in [str(color).strip() for color in style_hints.get("colors", [])]:
        if color and color.lower() not in css_content:
            failures.append(f"requested color missing from css: {color!r}")

    return (len(failures) == 0, failures)


def _validate_html_file(
    path: str,
    content: str,
    lowered: str,
    business_name: str,
    entry: str,
) -> list[str]:
    failures: list[str] = []
    business_marker = html.unescape(business_name).lower()
    content_marker = html.unescape(lowered)
    if business_marker and business_marker not in content_marker:
        failures.append(f"business name missing from {path!r}")
    for marker in _REQUIRED_HTML_MARKERS:
        if marker not in content:
            failures.append(f"quality marker {marker!r} missing from {path!r}")
    label = page_label(path).lower()
    if path != entry and label not in lowered:
        failures.append(f"page-specific label {label!r} missing from {path!r}")
    return failures


def _normalize_quality_signature(content: str) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", content.lower())).strip()
    return text[:1200]


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
    for file_item in bundle_files:
        path = str(file_item.get("path", ""))
        content = str(file_item.get("content", ""))
        language = str(file_item.get("language", "html"))
        if not is_safe_bundle_path(path):
            continue
        target_path = f"generated-sites/{slug}/{path}"
        resolved_target = (root / Path(target_path)).resolve()
        existing_content = (
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
                "diff": diff_fn(
                    target_path=target_path,
                    before_content=existing_content,
                    after_content=content,
                ),
                "validation": {
                    "status": validation_status,
                    "checks": checks,
                    "failures": validation_failures,
                },
            }
        )
    return proposals


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
        validation = proposal.get("validation") or {}
        if str(validation.get("status") or "failed").lower() != "passed":
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


def latest_pending_bundle_proposals(
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    for metadata in _assistant_metadata(session_messages, session_metadata):
        proposals = metadata.get("site_bundle_patch_proposals")
        if (
            isinstance(proposals, list)
            and proposals
            and not any(proposal.get("applied") for proposal in proposals)
        ):
            return proposals
    return None


def latest_bundle_artifact(
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    for metadata in _assistant_metadata(session_messages, session_metadata):
        bundle = metadata.get("site_bundle")
        if isinstance(bundle, dict) and bundle.get("artifact_type") == "site_bundle":
            return bundle
    return None


def _assistant_metadata(
    session_messages: list[Any] | None,
    session_metadata: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    metadata_items: list[dict[str, Any]] = []
    if isinstance(session_messages, list):
        for message in reversed(session_messages):
            if not isinstance(message, dict):
                continue
            if str(message.get("role") or "").lower() != "assistant":
                continue
            metadata = message.get("metadata")
            if isinstance(metadata, dict):
                metadata_items.append(metadata)
    if isinstance(session_metadata, dict):
        payload = session_metadata.get("last_assistant_payload")
        if isinstance(payload, dict):
            metadata_items.append(payload)
    return metadata_items
