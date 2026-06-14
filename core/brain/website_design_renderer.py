# fmt: off
"""Polished deterministic renderer for XV7 multi-page website artifacts."""

from __future__ import annotations

import html
import re
from pathlib import PurePosixPath
from typing import Any

LABELS = {
    "index": "Home",
    "home": "Home",
    "about": "About",
    "products": "Products",
    "faq": "FAQ",
    "menu": "Menu",
    "events": "Events",
    "contact": "Contact",
    "services": "Services",
    "gallery": "Gallery",
    "specials": "Specials",
    "catering": "Catering",
    "locations": "Locations",
}

COLOR_HEX = {
    "black": "#050505",
    "white": "#ffffff",
    "green": "#22c55e",
    "red": "#ef4444",
    "blue": "#3b82f6",
    "purple": "#8b5cf6",
    "orange": "#f97316",
    "yellow": "#facc15",
    "gold": "#f59e0b",
    "gray": "#64748b",
    "grey": "#64748b",
}

PROFILE_HINTS = {
    "food": ("hot dog", "hotdog", "food cart", "food truck", "menu", "catering"),
    "retail": ("vape", "cbd", "smoke shop", "shop", "store", "products"),
}

PROFILE_COPY: dict[str, dict[str, Any]] = {
    "food": {
        "eyebrow": "Fresh local flavor",
        "tagline": "A bold, street-ready food experience with menu highlights, specials, catering, and a clear path to visit or book.",
        "proof": ["Menu-first layout", "Specials built in", "Catering ready"],
        "primary": "Book catering",
        "secondary": ("View menu", "menu.html"),
        "hero": ("Menu. Specials. Catering.", "Fast choices and a clear next step."),
        "features": [
            ("Signature menu blocks", "Featured items feel like an active cart."),
            ("Weekly specials", "Promotional sections give customers urgency."),
            ("Booking path", "Catering and contact calls-to-action are built in."),
        ],
    },
    "retail": {
        "eyebrow": "Premium local retail",
        "tagline": "A polished retail experience with product clarity and trust.",
        "proof": ["Product-forward", "Trust focused", "Offer ready"],
        "primary": "Visit the shop",
        "secondary": ("See products", "products.html"),
        "hero": ("Products with polish.", "Products and offers feel organized."),
        "features": [
            ("Product categories", "Products are grouped by customer intent."),
            ("Premium visual system", "Dark panels and cards add retail polish."),
            ("Trust signals", "FAQ and guidance make the shop feel professional."),
        ],
    },
    "general": {
        "eyebrow": "Local business website",
        "tagline": "A polished multi-page website with clear offers and strong sections.",
        "proof": ["Clear offer", "Modern design", "Ready to edit"],
        "primary": "Get started",
        "secondary": ("Explore pages", "about.html"),
        "hero": ("Built beyond a template.", "Designed to be refined."),
        "features": [
            ("Custom page structure", "Each page gets a real role."),
            ("Modern visual rhythm", "Cards and CTAs create a finished feel."),
            ("Edit-ready content", "Copy can change without destroying layout."),
        ],
    },
}


def render_site_bundle_files(*, business_name: str, slug: str, pages: list[str], style_hints: dict[str, list[str]], question: str) -> list[dict[str, str]]:
    colors = _clean_list(style_hints.get("colors"))
    styles = [item.lower() for item in _clean_list(style_hints.get("styles"))]
    profile = _profile(f"{business_name} {question}")
    signals = _signals(question, styles)
    palette = _palette(colors, styles, signals)
    css_path = next((path for path in pages if path.endswith(".css")), None)
    js_path = next((path for path in pages if path.endswith(".js")), None)
    html_pages = [path for path in pages if path.endswith(".html")]
    files = [
        {
            "path": path,
            "language": "html",
            "content": _html_page(business_name, slug, path, html_pages, css_path, js_path, profile, palette, question, signals),
        }
        for path in html_pages
    ]
    for path in pages:
        if path.endswith(".css"):
            files.append({"path": path, "language": "css", "content": _css(business_name, palette, colors, styles, signals)})
        elif path.endswith(".js"):
            files.append({"path": path, "language": "javascript", "content": "// XV7 site bundle ready for static preview.\n"})
    return files


def page_label(path: str) -> str:
    name = path.split("/")[-1].replace(".html", "").replace("-", " ")
    return LABELS.get(name.lower(), name.title())


def _html_page(business_name: str, slug: str, path: str, pages: list[str], css_path: str | None, js_path: str | None, profile: str, palette: dict[str, str], question: str, signals: dict[str, bool]) -> str:
    label = page_label(path)
    css_tag = f'<link rel="stylesheet" href="{_href(path, css_path)}">' if css_path else ""
    js_tag = f'<script src="{_href(path, js_path)}" defer></script>' if js_path else ""
    palette_meta = ", ".join([palette["bg"], palette["accent"], palette["accent_2"], palette["text"]])
    return "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8" />',
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
        f"  <title>{html.escape(business_name)} — {html.escape(label)}</title>",
        f'  <meta name="xv7-site-slug" content="{html.escape(slug)}" />',
        f'  <meta name="xv7-palette" content="{html.escape(palette_meta)}" />',
        f"  {css_tag}",
        "</head>",
        f'<body class="{_body_class(signals)}">',
        _nav(pages, path, business_name),
        _main(business_name, label, path, profile, question, signals),
        _footer(business_name),
        f"  {js_tag}",
        "</body>",
        "</html>",
    ])


def _body_class(signals: dict[str, bool]) -> str:
    classes = ["xv7-site"]
    if signals["premium"]:
        classes.append("is-premium")
    if signals["spacious"]:
        classes.append("is-spacious")
    if signals["playful"]:
        classes.append("is-playful")
    if signals["bold"]:
        classes.append("is-bold")
    return " ".join(classes)


def _nav(pages: list[str], current_path: str, business_name: str) -> str:
    links = []
    for page in pages:
        active = " active" if page == current_path else ""
        aria = ' aria-current="page"' if page == current_path else ""
        links.append(f'<a class="nav-link{active}" href="{_href(current_path, page)}"{aria}>{html.escape(page_label(page))}</a>')
    return "\n".join([
        '<header class="site-header">',
        f'  <a class="brand-mark" href="{_href(current_path, "index.html")}"><span>{html.escape(_short_brand(business_name))}</span></a>',
        '  <nav class="site-nav" aria-label="Primary navigation">',
        *[f"    {link}" for link in links],
        "  </nav>",
        "</header>",
    ])


def _main(business_name: str, label: str, path: str, profile: str, question: str, signals: dict[str, bool]) -> str:
    slug = path.split("/")[-1].replace(".html", "").lower()
    if slug in {"index", "home"}:
        return _home(business_name, profile, question, signals)
    title = _page_title(slug, label)
    blocks = _page_blocks(slug, profile, question)
    if slug in {"menu", "specials"}:
        blocks = _maybe_add_special(blocks, question)
    return _page_shell(business_name, title, _page_lede(slug, title, business_name), blocks, slug == "specials", slug == "contact")


def _home(business_name: str, profile: str, question: str, signals: dict[str, bool]) -> str:
    card_title, card_copy = _copy(profile, "hero")
    secondary_label, secondary_href = _copy(profile, "secondary")
    if signals["premium"]:
        card_title = "Premium, custom, and ready to refine."
        card_copy = "Premium spacing, stronger contrast, and richer cards are applied."
    if signals["bold"]:
        card_copy = f"{card_copy} The hero and buttons are larger and punchier."
    extra: list[str] = []
    if signals["specials"] or profile == "food":
        extra.append(_home_specials(profile, question))
    if signals["premium"]:
        extra.append(_premium_band(business_name))
    if signals["less_template"]:
        extra.append(_customization_band(business_name))
    return "\n".join([
        '<main class="page-content home-layout">',
        '  <section class="hero-section">',
        '    <div class="hero-copy">',
        f'      <p class="eyebrow">{html.escape(str(_copy(profile, "eyebrow")))}</p>',
        f"      <h1>{html.escape(business_name)}</h1>",
        f'      <p class="hero-lede">{html.escape(str(_copy(profile, "tagline")))}</p>',
        '      <div class="hero-actions">',
        f'        <a class="button button-primary" href="contact.html">{_copy(profile, "primary")}</a>',
        f'        <a class="button button-ghost" href="{secondary_href}">{secondary_label}</a>',
        "      </div>",
        "    </div>",
        '    <aside class="hero-card" aria-label="Featured highlights">',
        f"      <span>Built for {html.escape(business_name)}</span>",
        f"      <strong>{html.escape(str(card_title))}</strong>",
        f"      <p>{html.escape(str(card_copy))}</p>",
        "    </aside>",
        "  </section>",
        '  <section class="proof-strip" aria-label="Highlights">',
        *[f"    <span>{html.escape(str(item))}</span>" for item in _copy(profile, "proof")],
        "  </section>",
        '  <section class="card-grid feature-grid">',
        *[_card(title, copy) for title, copy in _copy(profile, "features")],
        "  </section>",
        *extra,
        '  <section class="split-band">',
        "    <div>",
        '      <p class="eyebrow">Why it works</p>',
        f"      <h2>A site that finally feels specific to {html.escape(business_name)}.</h2>",
        "    </div>",
        f"    <p>{html.escape(_why(profile))}</p>",
        "  </section>",
        "</main>",
    ])


def _home_specials(profile: str, question: str) -> str:
    blocks = _maybe_add_special(_special_blocks(profile), question)
    return "\n".join([
        '  <section class="spotlight-section xv7-specials">',
        '    <p class="eyebrow">Specials spotlight</p>',
        "    <h2>Offers customers can act on today.</h2>",
        '    <div class="card-grid compact-grid">',
        *[_deal(title, copy) for title, copy in blocks[:3]],
        "    </div>",
        "  </section>",
    ])


def _premium_band(business_name: str) -> str:
    return "\n".join([
        '  <section class="premium-band">',
        '    <p class="eyebrow">Premium revision applied</p>',
        f"    <h2>{html.escape(business_name)} now has stronger visual hierarchy.</h2>",
        "    <p>Glass panels, bigger spacing, and sharper CTAs are applied.</p>",
        "  </section>",
    ])


def _customization_band(business_name: str) -> str:
    return "\n".join([
        '  <section class="custom-band">',
        '    <p class="eyebrow">Not a blank template</p>',
        f"    <h2>Specific sections now support {html.escape(business_name)}.</h2>",
        "    <p>Every page gets a clear job instead of duplicated filler.</p>",
        "  </section>",
    ])


def _page_shell(business_name: str, title: str, lede: str, blocks: list[tuple[str, str]], deal: bool, contact: bool) -> str:
    card_fn = _deal if deal else _contact if contact else _card
    return "\n".join([
        '<main class="page-content inner-page">',
        '  <section class="page-hero compact-hero">',
        f'    <p class="eyebrow">{html.escape(business_name)}</p>',
        f"    <h1>{html.escape(title)}</h1>",
        f'    <p class="hero-lede">{html.escape(lede)}</p>',
        "  </section>",
        '  <section class="card-grid">',
        *[card_fn(block_title, copy) for block_title, copy in blocks],
        "  </section>",
        '  <section class="cta-band">',
        f"    <h2>Ready to work with {html.escape(business_name)}?</h2>",
        '    <a class="button button-primary" href="contact.html">Contact us</a>',
        "  </section>",
        "</main>",
    ])


def _page_title(slug: str, fallback: str) -> str:
    return {"menu": "Menu Highlights", "products": "Products", "specials": "Specials", "about": "About", "faq": "FAQ", "contact": "Contact", "services": "Services"}.get(slug, fallback)


def _page_lede(slug: str, title: str, business_name: str) -> str:
    if slug == "menu":
        return f"Signature favorites from {business_name}, organized like a real menu."
    if slug == "products":
        return f"Product categories for {business_name} with real retail structure."
    if slug == "specials":
        return f"Current offers for {business_name} that feel editable and alive."
    if slug == "contact":
        return f"Give customers a clear path to reach {business_name}."
    return f"A focused {title.lower()} page for {business_name}."


def _page_blocks(slug: str, profile: str, question: str) -> list[tuple[str, str]]:
    if slug == "menu":
        return [("Classic Street Dog", "Snappy frank, toasted bun, mustard, onion."), ("Loaded Chili Dog", "Slow-simmered chili, cheddar, onion, and heat."), ("Cart Combo", "Any signature dog with chips and a cold drink.")]
    if slug == "products":
        return [("Premium products", "Clear categories replace generic retail filler."), ("Staff picks", "Featured items can change as inventory changes."), ("Accessories", "Add-ons and supporting products get real space.")]
    if slug == "specials":
        return _special_blocks(profile)
    if slug == "contact":
        return [("Call", _extract_phone(question) or "(555) 555-0199"), ("Email", _extract_email(question) or "hello@example.com"), ("Hours", "Monday-Saturday · 11 AM-7 PM")]
    if slug == "services":
        return _service_blocks(profile)
    return [("Purpose", "This page has a dedicated job in the site."), ("Details", "Cards let real content replace placeholders."), ("Next step", "Customers always have a clear path to contact.")]


def _css(business_name: str, palette: dict[str, str], colors: list[str], styles: list[str], signals: dict[str, bool]) -> str:
    requested = [f"  --requested-{i + 1}: {color};" for i, color in enumerate(colors[:8])]
    button_scale = "1.08" if signals["bold"] else "1"
    style_comment = ", ".join(styles) if styles else "balanced"
    return "\n".join([
        f"/* {business_name} — XV7 polished site bundle ({style_comment}) */",
        ":root {",
        f"  --bg: {palette['bg']};",
        f"  --panel: {palette['panel']};",
        f"  --text: {palette['text']};",
        f"  --muted: {palette['muted']};",
        f"  --accent: {palette['accent']};",
        f"  --accent-2: {palette['accent_2']};",
        f"  --shadow: {palette['shadow']};",
        f"  --button-scale: {button_scale};",
        *requested,
        "}",
        "body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,'Segoe UI',sans-serif}",
        ".site-header{display:flex;justify-content:space-between;gap:1rem;padding:1rem 3vw;background:rgba(255,255,255,.08);border-bottom:1px solid rgba(255,255,255,.15)}",
        ".brand-mark,.nav-link{text-decoration:none;color:var(--text);font-weight:900}.site-nav{display:flex;flex-wrap:wrap;gap:.5rem}",
        ".page-content{width:min(1120px,calc(100% - 2rem));margin:0 auto;padding:clamp(2rem,5vw,5rem) 0}.hero-section,.page-hero{display:grid;grid-template-columns:1.25fr .75fr;gap:2rem;align-items:center}",
        ".eyebrow{color:var(--accent);font-weight:900;letter-spacing:.14em;text-transform:uppercase}h1{font-size:clamp(3rem,8vw,6.5rem);line-height:1;letter-spacing:-.06em}.is-bold h1{font-size:clamp(3.4rem,9vw,7.4rem)}h2{font-size:clamp(1.8rem,4vw,3rem)}",
        ".hero-lede,.content-card p,.deal-card p,.contact-item p,.split-band p,.premium-band p,.custom-band p{color:var(--muted);line-height:1.7}.hero-actions{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1.5rem}",
        ".button{display:inline-flex;align-items:center;justify-content:center;min-height:calc(3rem * var(--button-scale));padding:.8rem 1.15rem;border-radius:999px;text-decoration:none;font-weight:900}.button-primary{background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#111;box-shadow:0 18px 40px var(--shadow)}.button-ghost{border:1px solid rgba(255,255,255,.2);color:var(--text)}",
        ".hero-card,.content-card,.deal-card,.contact-item{border:1px solid rgba(255,255,255,.14);background:var(--panel);border-radius:1.5rem;padding:1.2rem;box-shadow:0 24px 70px rgba(0,0,0,.3)}.is-premium .hero-card,.is-premium .content-card,.is-premium .deal-card,.is-premium .contact-item{border-color:color-mix(in srgb,var(--accent) 35%,rgba(255,255,255,.16))}.hero-card strong{display:block;font-size:clamp(1.8rem,4vw,3rem);line-height:1}",
        ".proof-strip,.card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin-top:2rem}.proof-strip span{padding:1rem;border-radius:1rem;background:rgba(255,255,255,.08);text-align:center;font-weight:900}.deal-card strong{color:var(--accent)}",
        ".split-band,.cta-band,.spotlight-section,.premium-band,.custom-band{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:2.5rem;padding:2rem;border:1px solid rgba(255,255,255,.14);border-radius:1.5rem;background:rgba(255,255,255,.06)}.custom-band{border-style:dashed}.site-footer{width:min(1120px,calc(100% - 2rem));margin:0 auto;padding:2rem 0;border-top:1px solid rgba(255,255,255,.12)}",
        "@media(max-width:820px){.hero-section,.page-hero,.split-band,.cta-band,.spotlight-section,.premium-band,.custom-band,.proof-strip,.card-grid{grid-template-columns:1fr}}",
    ])


def _card(title: str, copy: str) -> str:
    return _article("content-card", title, copy)


def _deal(title: str, copy: str) -> str:
    return _article("deal-card", title, copy, heading_tag="strong")


def _contact(title: str, copy: str) -> str:
    return _article("contact-item", title, copy)


def _article(class_name: str, title: str, copy: str, *, heading_tag: str = "h3") -> str:
    return "\n".join([f'    <article class="{class_name}">', f"      <{heading_tag}>{html.escape(title)}</{heading_tag}>", f"      <p>{html.escape(copy)}</p>", "    </article>"])


def _service_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "retail":
        return [("Product guidance", "Categories and FAQ content help customers decide."), ("Featured offers", "Promotions can be edited without rebuilding."), ("Local trust", "Contact details and reviews can grow over time.")]
    return [("Primary service", "The main offer is easy to understand."), ("Supporting service", "A second offer gets a clear card."), ("Custom requests", "The site leaves room for real details.")]


def _special_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "food":
        return [("Classic Dog Combo", "A signature dog, chips, and drink."), ("Loaded Chili Dog Special", "Chili, cheese, onion, and a limited push."), ("Family Pack Deal", "A group offer for teams and weekends.")]
    return [("Featured Offer", "A rotating offer customers can understand quickly."), ("Limited-Time Push", "A timely deal area that feels active."), ("Custom Package", "A flexible option for real-world requests.")]


def _maybe_add_special(blocks: list[tuple[str, str]], question: str) -> list[tuple[str, str]]:
    requested = _named_special(question)
    if requested and all(requested.casefold() not in item[0].casefold() for item in blocks):
        return [(requested, "Added from the latest revision request."), *blocks]
    return blocks


def _named_special(question: str) -> str:
    text = " ".join(str(question or "").split())
    for pattern in (r"\badd\s+(?:a|an|the)?\s*([a-z0-9][a-z0-9 '\-&]{2,60}?\s+special)\b", r"\b([a-z0-9][a-z0-9 '\-&]{2,60}?\s+special)\b"):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _titlecase(match.group(1))
    return ""


def _why(profile: str) -> str:
    if profile == "food":
        return "Food customers make quick decisions, so the site leads with menu and specials."
    if profile == "retail":
        return "Retail sites need product clarity, trust, and offers in a clean structure."
    return "The layout gives each page a job so the site can evolve without being rebuilt."


def _footer(business_name: str) -> str:
    return "\n".join(['<footer class="site-footer">', f"  <strong>{html.escape(business_name)}</strong>", "  <span>Generated by XV7 · Edit-ready multi-page site bundle</span>", "</footer>"])


def _signals(question: str, styles: list[str]) -> dict[str, bool]:
    q = str(question or "").casefold()
    style_set = {style.casefold() for style in styles}
    return {
        "premium": bool({"premium", "luxury", "high-end", "polished"} & style_set) or bool(re.search(r"\b(premium|luxury|high[- ]end|more professional)\b", q)),
        "spacious": bool(re.search(r"\b(spacing|spacious|more room|breathe)\b", q)),
        "bold": bool({"bold", "neon", "cyberpunk"} & style_set) or bool(re.search(r"\b(bold|buttons? pop|stronger hero|bigger|punchier)\b", q)),
        "playful": "playful" in style_set or bool(re.search(r"\b(fun|playful|friendly)\b", q)),
        "specials": bool(re.search(r"\bspecials?\b|\bdeals?\b|\boffers?\b", q)),
        "less_template": bool(re.search(r"\b(less template|not template|template-looking|generic|custom|specific|less basic|not basic)\b", q)),
    }


def _profile(text: str) -> str:
    normalized = text.casefold()
    for profile, hints in PROFILE_HINTS.items():
        if any(hint in normalized for hint in hints):
            return profile
    return "general"


def _palette(colors: list[str], styles: list[str], signals: dict[str, bool]) -> dict[str, str]:
    normalized = [_color(color) for color in colors]
    normalized = [color for color in normalized if color]
    wants_light = "light" in {style.lower() for style in styles}
    primary = normalized[0] if normalized else "#0b1020"
    secondary = normalized[1] if len(normalized) > 1 else "#ffffff"
    accent = normalized[2] if len(normalized) > 2 else primary
    bg = "#f8fafc" if wants_light else primary if _dark(primary) else "#09090b"
    if signals["premium"] and wants_light:
        bg = "#f8fafc"
    return {"bg": bg, "panel": "rgba(255,255,255,.76)" if wants_light else "rgba(255,255,255,.075)", "text": "#0f172a" if wants_light else "#f8fafc", "muted": "#475569" if wants_light else "#cbd5e1", "accent": accent, "accent_2": secondary if secondary != bg else accent, "shadow": f"color-mix(in srgb, {accent} 35%, transparent)"}


def _color(color: str) -> str:
    value = str(color or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}(?:[0-9a-f]{3})?", value):
        return value
    return COLOR_HEX.get(value, "")


def _dark(color: str) -> bool:
    value = _color(color) if not color.startswith("#") else color
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    if not re.fullmatch(r"#[0-9a-f]{6}", value):
        return True
    red = int(value[1:3], 16)
    green = int(value[3:5], 16)
    blue = int(value[5:7], 16)
    return (red * 0.299 + green * 0.587 + blue * 0.114) < 140


def _href(current_path: str, target_path: str | None) -> str:
    if not target_path:
        return "#"
    current_parent = PurePosixPath(current_path).parent
    if str(current_parent) == ".":
        return target_path
    try:
        return str(PurePosixPath(target_path).relative_to(current_parent))
    except ValueError:
        return "../" * len(current_parent.parts) + target_path


def _copy(profile: str, key: str) -> Any:
    return PROFILE_COPY.get(profile, PROFILE_COPY["general"])[key]


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text or "")
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}", text or "")
    return match.group(0) if match else ""


def _short_brand(business_name: str) -> str:
    cleaned = " ".join(str(business_name or "Home").split())
    if len(cleaned) <= 24:
        return cleaned
    words = cleaned.split()
    compact = " ".join(words[:3]) if len(words) > 1 else cleaned[:24]
    return compact if len(compact) <= 24 else words[0]


def _titlecase(value: str) -> str:
    keep_upper = {"bbq", "cbd", "adas", "faq", "seo", "it"}
    parts = []
    for word in str(value or "").strip().split():
        stripped = word.strip()
        parts.append(stripped.upper() if stripped.casefold() in keep_upper else stripped.capitalize())
    return " ".join(parts)
