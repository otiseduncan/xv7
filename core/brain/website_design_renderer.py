"""Polished deterministic renderer for XV7 multi-page website artifacts.

This renderer intentionally stays deterministic: no external calls, no hidden
model dependency, and no repo writes. The goal is to make XV7's website artifact
path produce a useful, editable baseline instead of a thin generic template.
"""

from __future__ import annotations

import html
import re
from pathlib import PurePosixPath
from typing import Any

_PAGE_LABELS = {
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
    "pricing": "Pricing",
    "reviews": "Reviews",
    "portfolio": "Portfolio",
    "booking": "Booking",
    "aftercare": "Aftercare",
    "rentals": "Rentals",
    "safety": "Safety",
    "guided-tours": "Guided Tours",
    "hours": "Hours",
}

_PROFILE_HINTS = (
    (
        "food",
        (
            "hot dog",
            "hotdog",
            "food cart",
            "food truck",
            "tavern",
            "restaurant",
            "menu",
            "catering",
            "bbq",
            "barbeque",
        ),
    ),
    (
        "retail",
        (
            "vape",
            "cbd",
            "smoke shop",
            "dispensary",
            "shop",
            "store",
            "products",
            "inventory",
            "retail",
        ),
    ),
    (
        "auto",
        (
            "adas",
            "calibration",
            "diagnostic",
            "diagnostics",
            "auto repair",
            "body shop",
            "vehicle",
        ),
    ),
    ("church", ("church", "ministry", "bible", "sermon", "fellowship")),
    (
        "cyber",
        (
            "cybersecurity",
            "cyber security",
            "network security",
            "automation",
            "it service",
            "managed it",
        ),
    ),
)

PROFILE_COPY: dict[str, dict[str, Any]] = {
    "food": {
        "eyebrow": "Fresh local flavor",
        "tagline": (
            "A bold, street-ready food experience with menu highlights, "
            "specials, catering, and a clear path to visit or book."
        ),
        "proof": ["Menu-first layout", "Specials built in", "Catering ready"],
        "primary": "Book catering",
        "secondary": ("View menu", "menu.html"),
        "hero_card": (
            "Menu. Specials. Catering.",
            "Designed around fast decisions: what is good, where to go, and how to book.",
        ),
        "features": [
            (
                "Signature menu blocks",
                "Featured items are organized so the site feels like an active cart, not a blank brochure.",
            ),
            (
                "Weekly specials",
                "Promotional sections give customers a reason to check back and act now.",
            ),
            (
                "Booking path",
                "Catering and contact calls-to-action are built into the structure from the start.",
            ),
        ],
    },
    "retail": {
        "eyebrow": "Premium local retail",
        "tagline": (
            "A polished retail experience with product clarity, customer guidance, "
            "featured offers, and professional local trust."
        ),
        "proof": ["Product-forward", "Trust focused", "Offer ready"],
        "primary": "Visit the shop",
        "secondary": ("See products", "products.html"),
        "hero_card": (
            "Products with polish.",
            "Designed to make products, trust, and offers feel organized from the first screen.",
        ),
        "features": [
            (
                "Product categories",
                "Products are grouped by intent so customers can understand the shop quickly.",
            ),
            (
                "Premium visual system",
                "Dark panels, highlights, and cards give the site a stronger retail feel.",
            ),
            (
                "Trust signals",
                "Guidance and FAQ areas make the business feel more professional and local.",
            ),
        ],
    },
    "auto": {
        "eyebrow": "Precision vehicle service",
        "tagline": (
            "A technical service presence that explains diagnostics, calibrations, "
            "proof, and contact paths without looking generic."
        ),
        "proof": ["Service proof", "Technical clarity", "Fast contact"],
        "primary": "Request service",
        "secondary": ("See services", "services.html"),
        "hero_card": (
            "Technical work made clear.",
            "Designed to explain high-skill work without burying the customer in jargon.",
        ),
        "features": [
            ("Service clarity", "Complex work is broken into readable service cards."),
            ("Proof sections", "Portfolio and review pages give room for job documentation."),
            ("Action flow", "Contact paths are placed where a customer would naturally need them."),
        ],
    },
    "church": {
        "eyebrow": "Community and fellowship",
        "tagline": "A warm ministry presence for gatherings, teaching, events, and visitor connection.",
        "proof": ["Visitor friendly", "Event ready", "Message focused"],
        "primary": "Plan a visit",
        "secondary": ("See events", "events.html"),
        "hero_card": (
            "A clearer welcome.",
            "Designed to make visitors feel welcome before they ever arrive.",
        ),
        "features": [
            ("Warm welcome", "Visitors get a clear first impression and next step."),
            ("Teaching ready", "Content areas can grow into sermons, Bible study, or resources."),
            ("Events path", "The layout supports recurring gatherings and announcements."),
        ],
    },
    "cyber": {
        "eyebrow": "Security and automation",
        "tagline": (
            "A sharp technology presence for security, automation, visibility, and client confidence."
        ),
        "proof": ["Security posture", "Automation ready", "Consulting focused"],
        "primary": "Request a consult",
        "secondary": ("See services", "services.html"),
        "hero_card": (
            "Security that feels alive.",
            "Designed to communicate control, security, and operational confidence.",
        ),
        "features": [
            ("Sharp positioning", "The hero explains the offer with authority and urgency."),
            ("Service blocks", "Security, automation, and consulting are separated cleanly."),
            ("Lead capture", "Contact sections are built for consultation requests."),
        ],
    },
    "general": {
        "eyebrow": "Local business website",
        "tagline": (
            "A polished multi-page website with clear offers, strong sections, "
            "and room for real business content."
        ),
        "proof": ["Clear offer", "Modern design", "Ready to edit"],
        "primary": "Get started",
        "secondary": ("Explore pages", "about.html"),
        "hero_card": (
            "Built beyond a template.",
            "Designed to be refined instead of regenerated from scratch.",
        ),
        "features": [
            (
                "Custom page structure",
                "Each page gets a real role instead of duplicate placeholder text.",
            ),
            (
                "Modern visual rhythm",
                "Cards, bands, proof strips, and CTAs create a finished feel.",
            ),
            (
                "Edit-ready content",
                "Copy can be revised without destroying the design system.",
            ),
        ],
    },
}


def render_site_bundle_files(
    *,
    business_name: str,
    slug: str,
    pages: list[str],
    style_hints: dict[str, list[str]],
    question: str,
) -> list[dict[str, str]]:
    """Render polished HTML/CSS/JS for the complete site bundle."""

    colors = _clean_list(style_hints.get("colors"))
    styles = [item.lower() for item in _clean_list(style_hints.get("styles"))]
    profile = _infer_profile(f"{business_name} {question}")
    signals = _design_signals(question=question, styles=styles)
    palette = _palette(colors=colors, styles=styles, signals=signals)
    fonts = _fonts(styles)
    css_path = next((path for path in pages if path.endswith(".css")), None)
    js_path = next((path for path in pages if path.endswith(".js")), None)
    html_pages = [path for path in pages if path.endswith(".html")]

    files: list[dict[str, str]] = []
    for path in html_pages:
        files.append(
            {
                "path": path,
                "language": "html",
                "content": _html_page(
                    business_name=business_name,
                    slug=slug,
                    path=path,
                    pages=html_pages,
                    css_path=css_path,
                    js_path=js_path,
                    profile=profile,
                    palette=palette,
                    question=question,
                    signals=signals,
                ),
            }
        )

    for path in pages:
        if path.endswith(".css"):
            files.append(
                {
                    "path": path,
                    "language": "css",
                    "content": _css(
                        business_name=business_name,
                        palette=palette,
                        colors=colors,
                        styles=styles,
                        fonts=fonts,
                        signals=signals,
                    ),
                }
            )
        elif path.endswith(".js"):
            files.append({"path": path, "language": "javascript", "content": _js(business_name)})
    return files


def page_label(path: str) -> str:
    name = path.split("/")[-1].replace(".html", "").replace("-", " ").replace("_", " ")
    return _PAGE_LABELS.get(name.lower(), name.title())


def _html_page(
    *,
    business_name: str,
    slug: str,
    path: str,
    pages: list[str],
    css_path: str | None,
    js_path: str | None,
    profile: str,
    palette: dict[str, str],
    question: str,
    signals: dict[str, bool],
) -> str:
    label = page_label(path)
    safe_name = html.escape(business_name)
    css_tag = f'<link rel="stylesheet" href="{_href(path, css_path)}">' if css_path else ""
    js_tag = f'<script src="{_href(path, js_path)}" defer></script>' if js_path else ""
    palette_meta = ", ".join(_clean_list([palette["bg"], palette["accent"], palette["accent_2"], palette["text"]]))
    classes = ["xv7-site"]
    if signals["premium"]:
        classes.append("is-premium")
    if signals["spacious"]:
        classes.append("is-spacious")
    if signals["playful"]:
        classes.append("is-playful")
    if signals["bold"]:
        classes.append("is-bold")
    body_class = " ".join(classes)

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8" />',
            '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
            f"  <title>{safe_name} — {html.escape(label)}</title>",
            f'  <meta name="description" content="{html.escape(_copy(profile, "tagline"), quote=True)}" />',
            f'  <meta name="xv7-site-slug" content="{html.escape(slug, quote=True)}" />',
            f'  <meta name="xv7-palette" content="{html.escape(palette_meta, quote=True)}" />',
            f"  {css_tag}",
            "</head>",
            f'<body class="{html.escape(body_class, quote=True)}">',
            _nav(pages=pages, current_path=path, business_name=business_name),
            _main(
                business_name=business_name,
                label=label,
                path=path,
                profile=profile,
                question=question,
                signals=signals,
            ),
            _footer(business_name),
            f"  {js_tag}",
            "</body>",
            "</html>",
        ]
    )


def _nav(*, pages: list[str], current_path: str, business_name: str) -> str:
    links = []
    for page in pages:
        active = " active" if page == current_path else ""
        aria = ' aria-current="page"' if page == current_path else ""
        links.append(
            f'<a class="nav-link{active}" href="{_href(current_path, page)}"{aria}>{html.escape(page_label(page))}</a>'
        )
    return "\n".join(
        [
            '<header class="site-header">',
            f'  <a class="brand-mark" href="{_href(current_path, "index.html")}"><span class="brand-sigil">✦</span><span>{html.escape(_short_brand(business_name))}</span></a>',
            '  <button class="nav-toggle" type="button" aria-label="Toggle navigation" aria-expanded="false">Menu</button>',
            '  <nav class="site-nav" aria-label="Primary navigation">',
            *[f"    {link}" for link in links],
            "  </nav>",
            "</header>",
        ]
    )


def _main(
    *,
    business_name: str,
    label: str,
    path: str,
    profile: str,
    question: str,
    signals: dict[str, bool],
) -> str:
    slug = path.split("/")[-1].replace(".html", "").lower()
    if slug in {"index", "home"}:
        return _home(business_name, profile, question, signals)
    if slug == "menu":
        blocks = [
            ("Classic Street Dog", "Snappy frank, toasted bun, mustard, onion, and house relish."),
            ("Loaded Chili Dog", "Slow-simmered chili, cheddar, diced onion, and a little heat."),
            ("Cart Combo", "Any signature dog with chips and a cold drink for a quick stop."),
            ("Family Pack", "A crowd-friendly set built for lunch breaks, teams, and events."),
        ]
        return _page_shell(
            business_name,
            "Menu Highlights",
            f"Signature favorites from {business_name}, organized like a real menu.",
            _maybe_append_special_request(blocks, question),
        )
    if slug == "products":
        blocks = [
            ("Premium products", "Clear categories and product groups instead of a generic retail paragraph."),
            ("Staff picks", "Featured items can be swapped as inventory or priorities change."),
            ("Accessories", "Add-ons, care items, and supporting products get their own space."),
            ("Customer guidance", "A professional area for questions, fitment, or responsible shopping details."),
        ]
        return _page_shell(
            business_name,
            "Products",
            f"Product categories for {business_name} with real retail structure.",
            blocks,
        )
    if slug == "specials":
        return _page_shell(
            business_name,
            "Specials",
            f"Current offers for {business_name} that feel editable and alive.",
            _maybe_append_special_request(_special_blocks(profile), question),
            deal=True,
        )
    if slug == "catering":
        blocks = [
            ("Small event cart", "Fast setup for birthdays, office lunches, and local gatherings."),
            ("Team lunch pack", "A predictable package for crews, shops, and work sites."),
            ("Custom crowd menu", "Flexible choices for larger groups and repeat events."),
        ]
        return _page_shell(business_name, "Catering", f"Event-ready packages from {business_name}.", blocks)
    if slug in {"locations", "events", "hours"}:
        blocks = [
            ("Find us", "Add the current cart stop, shop address, or service area here."),
            ("Hours", "Monday-Saturday · 11 AM-7 PM · update these hours anytime."),
            ("Events", "Use this space for pop-ups, catering stops, church events, or markets."),
        ]
        return _page_shell(business_name, label, f"Where to find {business_name} and what is happening next.", blocks)
    if slug == "about":
        blocks = [
            ("Local first", "The copy speaks like a local business instead of a generic template."),
            ("Clear offer", "Every section explains what the customer can do next."),
            ("Room to grow", "Pages are structured so more content can be added without rebuilding."),
        ]
        return _page_shell(business_name, "About", f"The story and operating style behind {business_name}.", blocks)
    if slug == "faq":
        blocks = [
            ("How do I get started?", "Use the contact page or primary button to ask for availability, pricing, or details."),
            ("Can this page be edited later?", "Yes. Copy, sections, colors, and offers can be changed without starting over."),
            ("Is this site multi-page?", "Yes. Navigation, page-specific content, CSS, and JavaScript are generated together."),
        ]
        return _page_shell(business_name, "FAQ", f"Common questions for {business_name}.", blocks)
    if slug == "contact":
        blocks = [
            ("Call", _extract_phone(question) or "(555) 555-0199"),
            ("Email", _extract_email(question) or "hello@example.com"),
            ("Visit", "Add the business address or service area here."),
            ("Hours", "Monday-Saturday · 11 AM-7 PM"),
        ]
        return _page_shell(business_name, "Contact", f"Give customers a clear path to reach {business_name}.", blocks, contact=True)
    if slug == "services":
        return _page_shell(business_name, "Services", f"What {business_name} can do for customers.", _service_blocks(profile))
    if slug in {"gallery", "portfolio", "reviews"}:
        blocks = [
            ("Real-world detail", "Show photos, work examples, or testimonials here."),
            ("Customer confidence", "Use this page to prove the business is active and trustworthy."),
            ("Fresh updates", "Keep this section changing as the business grows."),
        ]
        return _page_shell(business_name, label, f"Proof and personality for {business_name}.", blocks)
    return _page_shell(
        business_name,
        label,
        f"A focused {label.lower()} page for {business_name}.",
        [
            ("Purpose", f"This page gives {business_name} a dedicated area for {label.lower()}."),
            ("Details", "The section is structured with cards so real content can replace placeholders."),
            ("Next step", "Customers always have a clear path back to contact or booking."),
        ],
    )


def _home(
    business_name: str,
    profile: str,
    question: str,
    signals: dict[str, bool],
) -> str:
    card_title, card_copy = _copy(profile, "hero_card")
    secondary_label, secondary_href = _copy(profile, "secondary")
    if signals["premium"]:
        card_title = "Premium, custom, and ready to refine."
        card_copy = "Premium spacing, stronger contrast, richer cards, and page-specific content are applied across the bundle."
    if signals["bold"]:
        card_copy = f"{card_copy} The hero and buttons are intentionally larger, punchier, and easier to act on."

    dynamic_sections: list[str] = []
    if signals["specials"] or profile == "food":
        dynamic_sections.append(_home_specials(profile, question))
    if signals["premium"]:
        dynamic_sections.append(_premium_band(business_name))
    if signals["less_template"]:
        dynamic_sections.append(_customization_band(business_name))

    return "\n".join(
        [
            '<main class="page-content home-layout">',
            '  <section class="hero-section">',
            '    <div class="hero-copy">',
            f'      <p class="eyebrow">{html.escape(_copy(profile, "eyebrow"))}</p>',
            f"      <h1>{html.escape(business_name)}</h1>",
            f'      <p class="hero-lede">{html.escape(_copy(profile, "tagline"))}</p>',
            '      <div class="hero-actions">',
            f'        <a class="button button-primary" href="contact.html">{html.escape(_copy(profile, "primary"))}</a>',
            f'        <a class="button button-ghost" href="{html.escape(str(secondary_href))}">{html.escape(str(secondary_label))}</a>',
            "      </div>",
            "    </div>",
            '    <aside class="hero-card" aria-label="Featured highlights">',
            f"      <span>Built for {html.escape(business_name)}</span>",
            f"      <strong>{html.escape(str(card_title))}</strong>",
            f"      <p>{html.escape(str(card_copy))}</p>",
            "    </aside>",
            "  </section>",
            '  <section class="proof-strip" aria-label="Highlights">',
            *[f"    <span>{html.escape(item)}</span>" for item in _copy(profile, "proof")],
            "  </section>",
            '  <section class="card-grid feature-grid">',
            *[_card(title, copy) for title, copy in _copy(profile, "features")],
            "  </section>",
            *dynamic_sections,
            '  <section class="split-band">',
            "    <div>",
            '      <p class="eyebrow">Why it works</p>',
            f"      <h2>A site that finally feels specific to {html.escape(business_name)}.</h2>",
            "    </div>",
            f"    <p>{html.escape(_why(profile))}</p>",
            "  </section>",
            "</main>",
        ]
    )


def _home_specials(profile: str, question: str) -> str:
    blocks = _maybe_append_special_request(_special_blocks(profile), question)
    return "\n".join(
        [
            '  <section class="spotlight-section xv7-specials" aria-label="Specials spotlight">',
            "    <div>",
            '      <p class="eyebrow">Specials spotlight</p>',
            "      <h2>Offers customers can act on today.</h2>",
            "    </div>",
            '    <div class="card-grid compact-grid">',
            *[_deal(title, copy) for title, copy in blocks[:3]],
            "    </div>",
            "  </section>",
        ]
    )


def _premium_band(business_name: str) -> str:
    return "\n".join(
        [
            '  <section class="premium-band">',
            "    <div>",
            '      <p class="eyebrow">Premium revision applied</p>',
            f"      <h2>{html.escape(business_name)} now has stronger visual hierarchy.</h2>",
            "    </div>",
            "    <p>Glass panels, bigger spacing, high-contrast CTAs, and sharper section rhythm are applied without throwing away the approved site structure.</p>",
            "  </section>",
        ]
    )


def _customization_band(business_name: str) -> str:
    return "\n".join(
        [
            '  <section class="custom-band">',
            "    <div>",
            '      <p class="eyebrow">Not a blank template</p>',
            f"      <h2>Specific sections now support {html.escape(business_name)} instead of filler copy.</h2>",
            "    </div>",
            "    <p>Every page gets a clear job: sell the offer, answer questions, prove trust, and move customers toward contact or booking.</p>",
            "  </section>",
        ]
    )


def _page_shell(
    business_name: str,
    title: str,
    lede: str,
    blocks: list[tuple[str, str]],
    *,
    deal: bool = False,
    contact: bool = False,
) -> str:
    card_fn = _deal if deal else _contact if contact else _card
    return "\n".join(
        [
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
            "    <div>",
            f"      <h2>Ready to work with {html.escape(business_name)}?</h2>",
            "      <p>Use the contact page to turn this design into a real customer path.</p>",
            "    </div>",
            '    <a class="button button-primary" href="contact.html">Contact us</a>',
            "  </section>",
            "</main>",
        ]
    )


def _css(
    *,
    business_name: str,
    palette: dict[str, str],
    colors: list[str],
    styles: list[str],
    fonts: dict[str, str],
    signals: dict[str, bool],
) -> str:
    requested = [f"  --requested-{index + 1}: {color};" for index, color in enumerate(colors[:8])]
    style_comment = ", ".join(styles) if styles else "balanced"
    premium_gap = "clamp(2.2rem, 6vw, 6rem)" if signals["spacious"] or signals["premium"] else "clamp(2rem, 5vw, 5rem)"
    button_scale = "1.08" if signals["bold"] else "1"
    return "\n".join(
        [
            f"/* {business_name} — XV7 polished site bundle ({style_comment}) */",
            ":root {",
            f"  --bg: {palette['bg']};",
            f"  --panel: {palette['panel']};",
            f"  --panel-strong: {palette['panel_strong']};",
            f"  --text: {palette['text']};",
            f"  --muted: {palette['muted']};",
            f"  --accent: {palette['accent']};",
            f"  --accent-2: {palette['accent_2']};",
            f"  --shadow: {palette['shadow']};",
            f"  --body-font: {fonts['body']};",
            f"  --heading-font: {fonts['heading']};",
            f"  --button-scale: {button_scale};",
            *requested,
            "}",
            "*, *::before, *::after { box-sizing: border-box; }",
            "html { scroll-behavior: smooth; }",
            "body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 28%, transparent), transparent 34rem), linear-gradient(135deg, var(--bg), #050506 70%); color: var(--text); font-family: var(--body-font); }",
            "body::before { content: ''; position: fixed; inset: 0; pointer-events: none; background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px); background-size: 42px 42px; mask-image: linear-gradient(to bottom, rgba(0,0,0,.8), transparent); }",
            "a { color: inherit; }",
            ".site-header { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .85rem clamp(1rem, 4vw, 3rem); background: color-mix(in srgb, var(--bg) 82%, transparent); backdrop-filter: blur(18px); border-bottom: 1px solid rgba(255,255,255,.12); }",
            ".brand-mark { display: inline-flex; align-items: center; gap: .55rem; text-decoration: none; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }",
            ".brand-sigil { display: grid; place-items: center; width: 2.25rem; height: 2.25rem; border-radius: 999px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #111; box-shadow: 0 0 32px color-mix(in srgb, var(--accent) 50%, transparent); }",
            ".site-nav { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: .35rem; }",
            ".nav-link { padding: .65rem .85rem; border-radius: 999px; color: var(--muted); text-decoration: none; font-size: .82rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; transition: color .2s ease, background .2s ease, transform .2s ease; }",
            ".nav-link:hover, .nav-link.active { color: var(--text); background: rgba(255,255,255,.1); transform: translateY(-1px); }",
            ".nav-toggle { display: none; border: 1px solid rgba(255,255,255,.18); border-radius: 999px; background: rgba(255,255,255,.08); color: var(--text); padding: .6rem .9rem; font-weight: 800; }",
            f".page-content {{ width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: {premium_gap} 0; position: relative; }}",
            ".hero-section, .page-hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr); gap: clamp(1.25rem, 4vw, 3rem); align-items: center; }",
            ".compact-hero { grid-template-columns: minmax(0, 1fr); max-width: 840px; }",
            ".eyebrow { margin: 0 0 .85rem; color: var(--accent); font-size: .8rem; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; }",
            "h1, h2, h3 { font-family: var(--heading-font); line-height: 1.02; margin: 0; }",
            "h1 { max-width: 11ch; font-size: clamp(3rem, 9vw, 6.8rem); letter-spacing: -.07em; }",
            ".is-bold h1 { font-size: clamp(3.4rem, 10vw, 7.8rem); }",
            "h2 { font-size: clamp(1.7rem, 4vw, 3rem); letter-spacing: -.04em; }",
            "h3 { font-size: 1.15rem; }",
            ".hero-lede, .content-card p, .deal-card p, .contact-item p, .split-band p, .cta-band p, .site-footer span, .premium-band p, .custom-band p { color: var(--muted); line-height: 1.7; }",
            ".hero-lede { max-width: 66ch; margin: 1.2rem 0 0; font-size: clamp(1.05rem, 2vw, 1.28rem); }",
            ".hero-actions { display: flex; flex-wrap: wrap; gap: .9rem; margin-top: 1.6rem; }",
            ".button { display: inline-flex; align-items: center; justify-content: center; min-height: calc(3rem * var(--button-scale)); padding: calc(.8rem * var(--button-scale)) calc(1.15rem * var(--button-scale)); border-radius: 999px; text-decoration: none; font-weight: 900; letter-spacing: .04em; }",
            ".button-primary { background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #111; box-shadow: 0 18px 40px var(--shadow); }",
            ".button-ghost { border: 1px solid rgba(255,255,255,.22); background: rgba(255,255,255,.06); color: var(--text); }",
            ".hero-card, .content-card, .deal-card, .contact-item { border: 1px solid rgba(255,255,255,.14); background: linear-gradient(145deg, var(--panel-strong), var(--panel)); border-radius: 1.5rem; box-shadow: 0 24px 70px rgba(0,0,0,.32); }",
            ".is-premium .hero-card, .is-premium .content-card, .is-premium .deal-card, .is-premium .contact-item { border-color: color-mix(in srgb, var(--accent) 35%, rgba(255,255,255,.16)); box-shadow: 0 30px 90px color-mix(in srgb, var(--accent) 18%, rgba(0,0,0,.42)); }",
            ".hero-card { padding: clamp(1.4rem, 3vw, 2rem); transform: rotate(1.5deg); }",
            ".hero-card span { display: block; color: var(--accent); font-weight: 900; text-transform: uppercase; letter-spacing: .12em; font-size: .75rem; }",
            ".hero-card strong { display: block; margin: .8rem 0; font-size: clamp(1.8rem, 4vw, 3rem); line-height: 1; }",
            ".proof-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin: 2.5rem 0; }",
            ".proof-strip span { padding: 1rem; border-radius: 1.2rem; background: rgba(255,255,255,.07); color: var(--text); text-align: center; font-weight: 900; }",
            ".card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin-top: 2rem; }",
            ".compact-grid { margin-top: 0; }",
            ".content-card, .deal-card, .contact-item { padding: 1.15rem; }",
            ".deal-card { background: linear-gradient(145deg, color-mix(in srgb, var(--accent) 24%, var(--panel-strong)), var(--panel)); }",
            ".deal-card strong { display: inline-flex; margin-bottom: .6rem; padding: .3rem .55rem; border-radius: 999px; background: color-mix(in srgb, var(--accent) 30%, transparent); color: var(--text); }",
            ".split-band, .cta-band, .spotlight-section, .premium-band, .custom-band { display: grid; grid-template-columns: minmax(0, .8fr) minmax(0, 1fr); gap: 1.5rem; align-items: center; margin-top: 2.5rem; padding: clamp(1.25rem, 3vw, 2rem); border: 1px solid rgba(255,255,255,.14); border-radius: 1.6rem; background: linear-gradient(135deg, rgba(255,255,255,.08), rgba(255,255,255,.03)); }",
            ".spotlight-section { grid-template-columns: minmax(0, .65fr) minmax(0, 1.35fr); }",
            ".premium-band { background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 18%, rgba(255,255,255,.08)), rgba(255,255,255,.035)); }",
            ".custom-band { border-style: dashed; }",
            ".cta-band .button { justify-self: end; }",
            ".site-footer { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: 2rem 0 3rem; display: flex; justify-content: space-between; gap: 1rem; border-top: 1px solid rgba(255,255,255,.12); }",
            "@media (max-width: 820px) { .hero-section, .page-hero, .split-band, .cta-band, .spotlight-section, .premium-band, .custom-band { grid-template-columns: 1fr; } .site-nav { display: none; width: 100%; } .site-nav.open { display: grid; } .nav-toggle { display: inline-flex; } .site-header { flex-wrap: wrap; } .proof-strip, .card-grid { grid-template-columns: 1fr; } .cta-band .button { justify-self: start; } h1 { max-width: 100%; } }",
        ]
    )


def _card(title: str, copy: str) -> str:
    return "\n".join(
        [
            '    <article class="content-card">',
            f"      <h3>{html.escape(title)}</h3>",
            f"      <p>{html.escape(copy)}</p>",
            "    </article>",
        ]
    )


def _deal(title: str, copy: str) -> str:
    return "\n".join(
        [
            '    <article class="deal-card">',
            f"      <strong>{html.escape(title)}</strong>",
            f"      <p>{html.escape(copy)}</p>",
            "    </article>",
        ]
    )


def _contact(title: str, copy: str) -> str:
    return "\n".join(
        [
            '    <article class="contact-item">',
            f"      <h3>{html.escape(title)}</h3>",
            f"      <p>{html.escape(copy)}</p>",
            "    </article>",
        ]
    )


def _service_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "auto":
        return [
            ("ADAS calibration", "Camera, radar, and sensor calibration service areas."),
            ("Diagnostics", "OEM-level diagnostic paths and repair documentation."),
            ("Programming support", "Module setup, scans, and verification language."),
        ]
    if profile == "cyber":
        return [
            ("Security assessment", "Network, endpoint, and workflow risks made visible."),
            ("Automation", "Repeatable systems for alerts, reports, and operator flow."),
            ("Managed support", "Ongoing help that turns complexity into a clear plan."),
        ]
    return [
        ("Primary service", "The main offer is easy to understand and act on."),
        ("Supporting service", "A second offer gets a clear card instead of hidden copy."),
        ("Custom requests", "The site leaves room for the real business details."),
    ]


def _special_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "food":
        return [
            ("Classic Dog Combo", "A signature dog, chips, and drink built for a quick lunch stop."),
            ("Loaded Chili Dog Special", "A bolder special with chili, cheese, onion, and a limited-time push."),
            ("Family Pack Deal", "A simple group offer for teams, families, and weekend stops."),
        ]
    if profile == "retail":
        return [
            ("Featured Product Drop", "Highlight a weekly product group or customer favorite."),
            ("Bundle Offer", "Group accessories or related products into an easy deal."),
            ("New Customer Pick", "Give first-time visitors a clear place to start."),
        ]
    return [
        ("Featured Offer", "A rotating offer customers can understand quickly."),
        ("Limited-Time Push", "A timely deal area that makes the site feel active."),
        ("Custom Package", "A flexible option for real-world requests."),
    ]


def _maybe_append_special_request(
    blocks: list[tuple[str, str]],
    question: str,
) -> list[tuple[str, str]]:
    requested = _extract_named_special(question)
    if not requested:
        return blocks
    title = requested
    if all(title.casefold() not in item[0].casefold() for item in blocks):
        return [(title, "Added from the latest revision request so the site visibly reflects the requested special."), *blocks]
    return blocks


def _extract_named_special(question: str) -> str:
    text = " ".join(str(question or "").split())
    if not text:
        return ""
    match = re.search(
        r"\badd\s+(?:a|an|the)?\s*([a-z0-9][a-z0-9 '\-&]{2,60}?\s+special)\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return _titlecase(match.group(1))
    match = re.search(
        r"\b([a-z0-9][a-z0-9 '\-&]{2,60}?\s+special)\b",
        text,
        flags=re.IGNORECASE,
    )
    return _titlecase(match.group(1)) if match else ""


def _why(profile: str) -> str:
    if profile == "food":
        return "Food customers make quick decisions. The design puts menu, specials, location, and catering where they can act without digging."
    if profile == "retail":
        return "Retail sites need trust and product clarity. The structure makes categories, offers, and questions feel organized."
    if profile == "auto":
        return "Technical service sites need credibility. The layout explains complex work in plain blocks with visible proof paths."
    if profile == "church":
        return "Ministry sites need warmth and clarity. Visitors can see what to expect and how to connect."
    if profile == "cyber":
        return "Security sites need authority. The design signals control, process, and a clear consultation path."
    return "The layout gives each page a job so the site can evolve instead of being rebuilt every time."


def _footer(business_name: str) -> str:
    return "\n".join(
        [
            '<footer class="site-footer">',
            f"  <strong>{html.escape(business_name)}</strong>",
            "  <span>Generated by XV7 · Edit-ready multi-page site bundle</span>",
            "</footer>",
        ]
    )


def _js(business_name: str) -> str:
    safe = business_name.replace("\\", "\\\\").replace('"', '\\"')
    return "\n".join(
        [
            f'console.log("XV7 site bundle ready: {safe}");',
            "document.querySelectorAll('.nav-toggle').forEach((button) => {",
            "  button.addEventListener('click', () => {",
            "    const nav = button.parentElement?.querySelector('.site-nav');",
            "    const expanded = button.getAttribute('aria-expanded') === 'true';",
            "    button.setAttribute('aria-expanded', String(!expanded));",
            "    nav?.classList.toggle('open');",
            "  });",
            "});",
        ]
    )


def _design_signals(*, question: str, styles: list[str]) -> dict[str, bool]:
    q = str(question or "").casefold()
    style_set = {style.casefold() for style in styles}
    return {
        "premium": bool({"premium", "luxury", "high-end", "high end", "polished"} & style_set)
        or bool(re.search(r"\b(premium|luxury|high[- ]end|more polished|more professional)\b", q)),
        "spacious": bool(re.search(r"\b(spacing|spacious|more room|breathe|less cramped)\b", q)),
        "bold": bool({"bold", "neon", "cyberpunk"} & style_set)
        or bool(re.search(r"\b(bold|buttons? pop|stronger hero|bigger|punchier)\b", q)),
        "playful": "playful" in style_set or bool(re.search(r"\b(fun|playful|friendly)\b", q)),
        "specials": bool(re.search(r"\bspecials?\b|\bdeals?\b|\boffers?\b", q)),
        "less_template": bool(
            re.search(
                r"\b(less template|not template|template-looking|generic|custom|specific|less basic|not basic)\b",
                q,
            )
        ),
    }


def _infer_profile(text: str) -> str:
    normalized = text.casefold()
    for profile, hints in _PROFILE_HINTS:
        if any(hint in normalized for hint in hints):
            return profile
    return "general"


def _palette(*, colors: list[str], styles: list[str], signals: dict[str, bool]) -> dict[str, str]:
    normalized = [_normalize_color(color) for color in colors]
    normalized = [color for color in normalized if color]
    lowered_styles = {style.lower() for style in styles}
    wants_light = "light" in lowered_styles
    wants_dark = "dark" in lowered_styles or "neon" in lowered_styles or "cyberpunk" in lowered_styles
    if signals["premium"]:
        wants_dark = True
    if normalized:
        primary = normalized[0]
        secondary = normalized[1] if len(normalized) > 1 else "#ffffff"
        accent = normalized[2] if len(normalized) > 2 else primary
    else:
        primary, secondary, accent = "#0b1020", "#f8fafc", "#22c55e"

    bg = "#f8fafc" if wants_light else primary if _is_dark(primary) else "#09090b"
    text = "#0f172a" if wants_light else "#f8fafc"
    muted = "#475569" if wants_light else "#cbd5e1"
    panel = "rgba(255,255,255,.76)" if wants_light else "rgba(255,255,255,.075)"
    panel_strong = "rgba(255,255,255,.92)" if wants_light else "rgba(255,255,255,.12)"
    accent_2 = secondary if secondary != bg else accent
    if not wants_light and not wants_dark and _is_light(bg):
        bg = "#09090b"
        text = "#f8fafc"
    return {
        "bg": bg,
        "panel": panel,
        "panel_strong": panel_strong,
        "text": text,
        "muted": muted,
        "accent": accent,
        "accent_2": accent_2,
        "shadow": "color-mix(in srgb, " + accent + " 35%, transparent)",
    }


def _normalize_color(color: str) -> str:
    value = str(color or "").strip().lower()
    aliases = {
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
        "teal": "#14b8a6",
        "cyan": "#06b6d4",
        "pink": "#ec4899",
        "brown": "#92400e",
        "silver": "#cbd5e1",
    }
    if re.fullmatch(r"#[0-9a-f]{3}(?:[0-9a-f]{3})?", value):
        return value
    return aliases.get(value, "")


def _is_dark(color: str) -> bool:
    value = _normalize_color(color) if not color.startswith("#") else color
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    if not re.fullmatch(r"#[0-9a-f]{6}", value):
        return True
    red = int(value[1:3], 16)
    green = int(value[3:5], 16)
    blue = int(value[5:7], 16)
    return (red * 0.299 + green * 0.587 + blue * 0.114) < 140


def _is_light(color: str) -> bool:
    return not _is_dark(color)


def _fonts(styles: list[str]) -> dict[str, str]:
    lowered = {style.lower() for style in styles}
    if "playful" in lowered:
        return {
            "body": "'Trebuchet MS', 'Segoe UI', sans-serif",
            "heading": "'Trebuchet MS', 'Segoe UI', sans-serif",
        }
    if "luxury" in lowered or "premium" in lowered:
        return {
            "body": "'Inter', 'Segoe UI', sans-serif",
            "heading": "'Georgia', 'Times New Roman', serif",
        }
    if "futuristic" in lowered or "cyberpunk" in lowered:
        return {
            "body": "'Rajdhani', 'Segoe UI', sans-serif",
            "heading": "'Rajdhani', 'Segoe UI', sans-serif",
        }
    return {
        "body": "'Inter', 'Segoe UI', sans-serif",
        "heading": "'Inter', 'Segoe UI', sans-serif",
    }


def _href(current_path: str, target_path: str | None) -> str:
    if not target_path:
        return "#"
    current_parent = PurePosixPath(current_path).parent
    if str(current_parent) == ".":
        return target_path
    try:
        return str(PurePosixPath(target_path).relative_to(current_parent))
    except ValueError:
        depth = len(current_parent.parts)
        return "../" * depth + target_path


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
    if len(words) > 1:
        compact = " ".join(words[:3])
        return compact if len(compact) <= 24 else words[0]
    return cleaned[:24].rstrip()


def _titlecase(value: str) -> str:
    keep_upper = {"bbq", "cbd", "adas", "faq", "seo", "it"}
    parts = []
    for word in str(value or "").strip().split():
        stripped = word.strip()
        parts.append(stripped.upper() if stripped.casefold() in keep_upper else stripped.capitalize())
    return " ".join(parts)
