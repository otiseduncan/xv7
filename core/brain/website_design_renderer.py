"""Polished deterministic renderer for XV7 multi-page website artifacts."""

from __future__ import annotations

import html
import re
from pathlib import PurePosixPath
from typing import Any

_PAGE_LABELS = {
    "index": "Home", "home": "Home", "about": "About", "products": "Products",
    "faq": "FAQ", "menu": "Menu", "events": "Events", "contact": "Contact",
    "services": "Services", "gallery": "Gallery", "specials": "Specials",
    "catering": "Catering", "locations": "Locations", "pricing": "Pricing",
    "reviews": "Reviews", "portfolio": "Portfolio", "booking": "Booking",
    "aftercare": "Aftercare", "rentals": "Rentals", "safety": "Safety",
    "guided-tours": "Guided Tours",
}

_PROFILE_HINTS = (
    ("food", ("hot dog", "hotdog", "food cart", "food truck", "tavern", "restaurant", "menu", "catering", "bbq", "barbeque")),
    ("retail", ("vape", "cbd", "smoke shop", "dispensary", "shop", "store", "products", "inventory", "retail")),
    ("auto", ("adas", "calibration", "diagnostic", "diagnostics", "auto repair", "body shop", "vehicle")),
    ("church", ("church", "ministry", "bible", "sermon", "fellowship")),
    ("cyber", ("cybersecurity", "cyber security", "network security", "automation", "it service", "managed it")),
)

PROFILE_COPY: dict[str, dict[str, Any]] = {
    "food": {
        "eyebrow": "Fresh local flavor",
        "tagline": "A bold, street-ready food experience with menu highlights, specials, catering, and a clear path to visit or book.",
        "proof": ["Menu-first layout", "Specials built in", "Catering ready"],
        "primary": "Book catering",
        "secondary": ("View menu", "menu.html"),
        "hero_card": ("Menu. Specials. Catering.", "Designed around fast decisions: what is good, where to go, and how to book."),
        "features": [
            ("Signature menu blocks", "Featured items are organized so the site feels like an active cart, not a blank brochure."),
            ("Weekly specials", "Promotional sections give customers a reason to check back and act now."),
            ("Booking path", "Catering and contact calls-to-action are built into the structure from the start."),
        ],
    },
    "retail": {
        "eyebrow": "Premium local retail",
        "tagline": "A polished retail experience with product clarity, customer guidance, featured offers, and professional local trust.",
        "proof": ["Product-forward", "Trust focused", "Offer ready"],
        "primary": "Visit the shop",
        "secondary": ("See products", "products.html"),
        "hero_card": ("Products with polish.", "Designed to make products, trust, and offers feel organized from the first screen."),
        "features": [
            ("Product categories", "Products are grouped by intent so customers can understand the shop quickly."),
            ("Premium visual system", "Dark panels, highlights, and cards give the site a stronger retail feel."),
            ("Trust signals", "Guidance and FAQ areas make the business feel more professional and local."),
        ],
    },
    "auto": {
        "eyebrow": "Precision vehicle service",
        "tagline": "A technical service presence that explains diagnostics, calibrations, proof, and contact paths without looking generic.",
        "proof": ["Service proof", "Technical clarity", "Fast contact"],
        "primary": "Request service",
        "secondary": ("See services", "services.html"),
        "hero_card": ("Technical work made clear.", "Designed to explain high-skill work without burying the customer in jargon."),
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
        "hero_card": ("A clearer welcome.", "Designed to make visitors feel welcome before they ever arrive."),
        "features": [
            ("Warm welcome", "Visitors get a clear first impression and next step."),
            ("Teaching ready", "Content areas can grow into sermons, Bible study, or resources."),
            ("Events path", "The layout supports recurring gatherings and announcements."),
        ],
    },
    "cyber": {
        "eyebrow": "Security and automation",
        "tagline": "A sharp technology presence for security, automation, visibility, and client confidence.",
        "proof": ["Security posture", "Automation ready", "Consulting focused"],
        "primary": "Request a consult",
        "secondary": ("See services", "services.html"),
        "hero_card": ("Security that feels alive.", "Designed to communicate control, security, and operational confidence."),
        "features": [
            ("Sharp positioning", "The hero explains the offer with authority and urgency."),
            ("Service blocks", "Security, automation, and consulting are separated cleanly."),
            ("Lead capture", "Contact sections are built for consultation requests."),
        ],
    },
    "general": {
        "eyebrow": "Local business website",
        "tagline": "A polished multi-page website with clear offers, strong sections, and room for real business content.",
        "proof": ["Clear offer", "Modern design", "Ready to edit"],
        "primary": "Get started",
        "secondary": ("Explore pages", "about.html"),
        "hero_card": ("Built beyond a template.", "Designed to be refined instead of regenerated from scratch."),
        "features": [
            ("Custom page structure", "Each page gets a real role instead of duplicate placeholder text."),
            ("Modern visual rhythm", "Cards, bands, proof strips, and CTAs create a finished feel."),
            ("Edit-ready content", "Copy can be revised without destroying the design system."),
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
    palette = _palette(colors=colors, styles=styles)
    fonts = _fonts(styles)
    css_path = next((path for path in pages if path.endswith(".css")), None)
    js_path = next((path for path in pages if path.endswith(".js")), None)
    html_pages = [path for path in pages if path.endswith(".html")]

    files: list[dict[str, str]] = []
    for path in html_pages:
        files.append({
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
            ),
        })

    for path in pages:
        if path.endswith(".css"):
            files.append({
                "path": path,
                "language": "css",
                "content": _css(business_name=business_name, palette=palette, colors=colors, styles=styles, fonts=fonts),
            })
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
) -> str:
    label = page_label(path)
    safe_name = html.escape(business_name)
    css_tag = f'<link rel="stylesheet" href="{_href(path, css_path)}">' if css_path else ""
    js_tag = f'<script src="{_href(path, js_path)}" defer></script>' if js_path else ""
    palette_meta = ", ".join(_clean_list([palette["bg"], palette["accent"], palette["accent_2"], palette["text"]]))
    return "\n".join([
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
        "<body>",
        _nav(pages=pages, current_path=path),
        _main(business_name=business_name, label=label, path=path, profile=profile, question=question),
        _footer(business_name),
        f"  {js_tag}",
        "</body>",
        "</html>",
    ])


def _nav(*, pages: list[str], current_path: str) -> str:
    links = []
    for page in pages:
        active = " active" if page == current_path else ""
        aria = ' aria-current="page"' if page == current_path else ""
        links.append(f'<a class="nav-link{active}" href="{_href(current_path, page)}"{aria}>{html.escape(page_label(page))}</a>')
    return "\n".join([
        '<header class="site-header">',
        f'  <a class="brand-mark" href="{_href(current_path, "index.html")}"><span class="brand-sigil">✦</span><span>Home</span></a>',
        '  <button class="nav-toggle" type="button" aria-label="Toggle navigation" aria-expanded="false">Menu</button>',
        '  <nav class="site-nav" aria-label="Primary navigation">',
        *[f"    {link}" for link in links],
        "  </nav>",
        "</header>",
    ])


def _main(*, business_name: str, label: str, path: str, profile: str, question: str) -> str:
    slug = path.split("/")[-1].replace(".html", "").lower()
    if slug in {"index", "home"}:
        return _home(business_name, profile, question)
    if slug == "menu":
        blocks = [
            ("Classic Street Dog", "Snappy frank, toasted bun, mustard, onion, and house relish."),
            ("Loaded Chili Dog", "Slow-simmered chili, cheddar, diced onion, and a little heat."),
            ("Cart Combo", "Any signature dog with chips and a cold drink for a quick stop."),
            ("Family Pack", "A crowd-friendly set built for lunch breaks, teams, and events."),
        ]
        return _page_shell(business_name, "Menu Highlights", f"Signature favorites from {business_name}, organized like a real menu.", blocks)
    if slug == "products":
        blocks = [
            ("Premium products", "Clear categories and product groups instead of a generic retail paragraph."),
            ("Staff picks", "Featured items can be swapped as inventory or priorities change."),
            ("Accessories", "Add-ons, care items, and supporting products get their own space."),
            ("Customer guidance", "A professional area for questions, fitment, or responsible shopping details."),
        ]
        return _page_shell(business_name, "Products", f"Product categories for {business_name} with real retail structure.", blocks)
    if slug == "specials":
        return _page_shell(business_name, "Specials", f"Current offers for {business_name} that feel editable and alive.", _special_blocks(profile), deal=True)
    if slug == "catering":
        blocks = [("Small event cart", "Fast setup for birthdays, office lunches, and local gatherings."), ("Team lunch pack", "A predictable package for crews, shops, and work sites."), ("Custom crowd menu", "Flexible choices for larger groups and repeat events.")]
        return _page_shell(business_name, "Catering", f"Event-ready packages from {business_name}.", blocks)
    if slug in {"locations", "events"}:
        blocks = [("Find us", "Add the current cart stop, shop address, or service area here."), ("Hours", "Monday-Saturday · 11 AM-7 PM · update these hours anytime."), ("Events", "Use this space for pop-ups, catering stops, church events, or markets.")]
        return _page_shell(business_name, label, f"Where to find {business_name} and what is happening next.", blocks)
    if slug == "about":
        blocks = [("Local first", "The copy speaks like a local business instead of a generic template."), ("Clear offer", "Every section explains what the customer can do next."), ("Room to grow", "Pages are structured so more content can be added without rebuilding.")]
        return _page_shell(business_name, "About", f"The story and operating style behind {business_name}.", blocks)
    if slug == "faq":
        blocks = [("How do I get started?", "Use the contact page or primary button to ask for availability, pricing, or details."), ("Can this page be edited later?", "Yes. Copy, sections, colors, and offers can be changed without starting over."), ("Is this site multi-page?", "Yes. Navigation, page-specific content, CSS, and JavaScript are generated together.")]
        return _page_shell(business_name, "FAQ", f"Common questions for {business_name}.", blocks)
    if slug == "contact":
        blocks = [("Call", _extract_phone(question) or "(555) 555-0199"), ("Email", _extract_email(question) or "hello@example.com"), ("Visit", "Add the business address or service area here."), ("Hours", "Monday-Saturday · 11 AM-7 PM")]
        return _page_shell(business_name, "Contact", f"Give customers a clear path to reach {business_name}.", blocks, contact=True)
    if slug == "services":
        return _page_shell(business_name, "Services", f"What {business_name} can do for customers.", _service_blocks(profile))
    if slug in {"gallery", "portfolio", "reviews"}:
        blocks = [("Real-world detail", "Show photos, work examples, or testimonials here."), ("Customer confidence", "Use this page to prove the business is active and trustworthy."), ("Fresh updates", "Keep this section changing as the business grows.")]
        return _page_shell(business_name, label, f"Proof and personality for {business_name}.", blocks)
    return _page_shell(business_name, label, f"A focused {label.lower()} page for {business_name}.", [("Purpose", f"This page gives {business_name} a dedicated area for {label.lower()}.") , ("Details", "The section is structured with cards so real content can replace placeholders."), ("Next step", "Customers always have a clear path back to contact or booking.")])


def _home(business_name: str, profile: str, question: str) -> str:
    card_title, card_copy = _copy(profile, "hero_card")
    secondary_label, secondary_href = _copy(profile, "secondary")
    if "premium" in question.casefold() or "luxury" in question.casefold():
        card_copy = "Premium spacing, stronger contrast, and page-specific content are applied across the bundle."
    return "\n".join([
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
        '  <section class="split-band">',
        "    <div>",
        '      <p class="eyebrow">Why it works</p>',
        f"      <h2>A site that finally feels specific to {html.escape(business_name)}.</h2>",
        "    </div>",
        f"    <p>{html.escape(_why(profile))}</p>",
        "  </section>",
        "</main>",
    ])


def _page_shell(business_name: str, title: str, lede: str, blocks: list[tuple[str, str]], *, deal: bool = False, contact: bool = False) -> str:
    card_fn = _deal if deal else _contact if contact else _card
    return "\n".join([
        '<main class="page-content inner-page">',
        '  <section class="page-hero compact-hero">',
        f'    <p class="eyebrow">{html.escape(business_name)}</p>',
        f"    <h1>{html.escape(title)}</h1>",
        f'    <p class="hero-lede">{html.escape(lede)}</p>',
        "  </section>",
        '  <section class="card-grid">',
        *[card_fn(title, copy) for title, copy in blocks],
        "  </section>",
        '  <section class="cta-band">',
        "    <div>",
        f"      <h2>Ready to work with {html.escape(business_name)}?</h2>",
        "      <p>Use the contact page to turn this design into a real customer path.</p>",
        "    </div>",
        '    <a class="button button-primary" href="contact.html">Contact us</a>',
        "  </section>",
        "</main>",
    ])


def _css(*, business_name: str, palette: dict[str, str], colors: list[str], styles: list[str], fonts: dict[str, str]) -> str:
    requested = [f"  --requested-{index + 1}: {color};" for index, color in enumerate(colors[:8])]
    style_comment = ", ".join(styles) if styles else "balanced"
    return "\n".join([
        f"/* {business_name} — XV7 polished site bundle ({style_comment}) */", ":root {",
        f"  --bg: {palette['bg']};", f"  --panel: {palette['panel']};", f"  --panel-strong: {palette['panel_strong']};", f"  --text: {palette['text']};", f"  --muted: {palette['muted']};", f"  --accent: {palette['accent']};", f"  --accent-2: {palette['accent_2']};", f"  --shadow: {palette['shadow']};", f"  --body-font: {fonts['body']};", f"  --heading-font: {fonts['heading']};", *requested, "}",
        "*, *::before, *::after { box-sizing: border-box; }", "html { scroll-behavior: smooth; }",
        "body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 28%, transparent), transparent 34rem), linear-gradient(135deg, var(--bg), #050506 70%); color: var(--text); font-family: var(--body-font); }",
        "body::before { content: ''; position: fixed; inset: 0; pointer-events: none; background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px); background-size: 42px 42px; mask-image: linear-gradient(to bottom, rgba(0,0,0,.8), transparent); }",
        "a { color: inherit; }",
        ".site-header { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .85rem clamp(1rem, 4vw, 3rem); background: color-mix(in srgb, var(--bg) 82%, transparent); backdrop-filter: blur(18px); border-bottom: 1px solid rgba(255,255,255,.12); }",
        ".brand-mark { display: inline-flex; align-items: center; gap: .55rem; text-decoration: none; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }", ".brand-sigil { display: grid; place-items: center; width: 2.25rem; height: 2.25rem; border-radius: 999px; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #111; box-shadow: 0 0 32px color-mix(in srgb, var(--accent) 50%, transparent); }",
        ".site-nav { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: .35rem; }", ".nav-link { padding: .65rem .85rem; border-radius: 999px; color: var(--muted); text-decoration: none; font-size: .82rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; transition: color .2s ease, background .2s ease, transform .2s ease; }", ".nav-link:hover, .nav-link.active { color: var(--text); background: rgba(255,255,255,.1); transform: translateY(-1px); }", ".nav-toggle { display: none; border: 1px solid rgba(255,255,255,.18); border-radius: 999px; background: rgba(255,255,255,.08); color: var(--text); padding: .6rem .9rem; font-weight: 800; }",
        ".page-content { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: clamp(2rem, 5vw, 5rem) 0; position: relative; }", ".hero-section, .page-hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr); gap: clamp(1.25rem, 4vw, 3rem); align-items: center; }", ".compact-hero { grid-template-columns: minmax(0, 1fr); max-width: 840px; }", ".eyebrow { margin: 0 0 .85rem; color: var(--accent); font-size: .8rem; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; }",
        "h1, h2, h3 { font-family: var(--heading-font); line-height: 1.02; margin: 0; }", "h1 { max-width: 11ch; font-size: clamp(3rem, 9vw, 6.8rem); letter-spacing: -.07em; }", "h2 { font-size: clamp(1.7rem, 4vw, 3rem); letter-spacing: -.04em; }", "h3 { font-size: 1.15rem; }", ".hero-lede, .content-card p, .deal-card p, .contact-item p, .split-band p, .cta-band p, .site-footer span { color: var(--muted); line-height: 1.7; }", ".hero-lede { max-width: 66ch; margin: 1.2rem 0 0; font-size: clamp(1.05rem, 2vw, 1.28rem); }",
        ".hero-actions { display: flex; flex-wrap: wrap; gap: .9rem; margin-top: 1.6rem; }", ".button { display: inline-flex; align-items: center; justify-content: center; min-height: 3rem; padding: .8rem 1.15rem; border-radius: 999px; text-decoration: none; font-weight: 900; letter-spacing: .04em; }", ".button-primary { background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #111; box-shadow: 0 18px 40px var(--shadow); }", ".button-ghost { border: 1px solid rgba(255,255,255,.22); background: rgba(255,255,255,.06); color: var(--text); }",
        ".hero-card, .content-card, .deal-card, .contact-item { border: 1px solid rgba(255,255,255,.14); background: linear-gradient(145deg, var(--panel-strong), var(--panel)); border-radius: 1.5rem; box-shadow: 0 24px 70px rgba(0,0,0,.32); }", ".hero-card { padding: clamp(1.4rem, 3vw, 2rem); transform: rotate(1.5deg); }", ".hero-card span { display: block; color: var(--accent); font-weight: 900; text-transform: uppercase; letter-spacing: .12em; font-size: .75rem; }", ".hero-card strong { display: block; margin: .8rem 0; font-size: clamp(1.8rem, 4vw, 3rem); line-height: 1; }",
        ".proof-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin: 2.5rem 0; }", ".proof-strip span { padding: .95rem 1rem; border-radius: 999px; background: rgba(255,255,255,.08); color: var(--text); text-align: center; font-weight: 800; }", ".card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin-top: 2rem; }", ".content-card, .deal-card, .contact-item { padding: 1.25rem; }", ".content-card::before, .deal-card::before { content: ''; display: block; width: 2.5rem; height: .28rem; border-radius: 999px; margin-bottom: 1rem; background: linear-gradient(90deg, var(--accent), var(--accent-2)); }",
        ".deal-card { position: relative; overflow: hidden; }", ".deal-card::after { content: 'SPECIAL'; position: absolute; top: 1rem; right: -2.4rem; rotate: 35deg; padding: .25rem 2.6rem; background: var(--accent); color: #111; font-size: .65rem; font-weight: 900; letter-spacing: .12em; }", ".split-band, .cta-band { display: flex; align-items: center; justify-content: space-between; gap: 1.5rem; margin-top: 2rem; padding: clamp(1.25rem, 3vw, 2rem); border-radius: 1.5rem; background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 16%, transparent), rgba(255,255,255,.06)); border: 1px solid rgba(255,255,255,.14); }", ".site-footer { width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: 2rem 0 3rem; display: flex; justify-content: space-between; gap: 1rem; border-top: 1px solid rgba(255,255,255,.12); }",
        "@media (max-width: 820px) { .nav-toggle { display: inline-flex; } .site-nav { display: none; width: 100%; justify-content: flex-start; } .site-header.nav-open { flex-wrap: wrap; } .site-header.nav-open .site-nav { display: flex; } .hero-section, .page-hero, .proof-strip, .card-grid { grid-template-columns: 1fr; } .split-band, .cta-band, .site-footer { align-items: flex-start; flex-direction: column; } h1 { max-width: 100%; } }",
    ])


def _js(business_name: str) -> str:
    safe = business_name.replace("\\", "\\\\").replace("'", "\\'")
    return "\n".join([f"/* {safe} — XV7 site bundle interactivity */", "document.addEventListener('DOMContentLoaded', function () {", "  var header = document.querySelector('.site-header');", "  var toggle = document.querySelector('.nav-toggle');", "  if (toggle && header) {", "    toggle.addEventListener('click', function () {", "      var open = header.classList.toggle('nav-open');", "      toggle.setAttribute('aria-expanded', String(open));", "    });", "  }", "});"])


def _card(title: str, copy: str) -> str:
    return f'    <article class="content-card"><h3>{html.escape(title)}</h3><p>{html.escape(copy)}</p></article>'


def _deal(title: str, copy: str) -> str:
    return f'    <article class="deal-card"><h3>{html.escape(title)}</h3><p>{html.escape(copy)}</p></article>'


def _contact(title: str, copy: str) -> str:
    return f'    <article class="contact-item"><h3>{html.escape(title)}</h3><p>{html.escape(copy)}</p></article>'


def _footer(business_name: str) -> str:
    return "\n".join(['<footer class="site-footer">', f"  <strong>{html.escape(business_name)}</strong>", "  <span>Designed as a polished XV7 multi-page site bundle.</span>", "</footer>"])


def _infer_profile(prompt: str) -> str:
    lowered = prompt.casefold()
    for profile, terms in _PROFILE_HINTS:
        if any(term in lowered for term in terms):
            return profile
    return "general"


def _palette(*, colors: list[str], styles: list[str]) -> dict[str, str]:
    lowered = [color.lower() for color in colors]
    wants_dark = "dark" in styles or bool({"black", "gray", "purple", "blue", "teal", "brown"} & set(lowered))
    if not wants_dark and bool({"white", "silver", "yellow", "pink"} & set(lowered)):
        return _palette_light(colors)
    bg = "black" if "black" in lowered else "#09090b"
    text = "white"
    accent = _first_color(colors, {bg, text, "white", "black"}) or (colors[0] if colors else "#f97316")
    accent_2 = _first_color(colors, {bg, text, accent}) or "#facc15"
    return {"bg": bg, "panel": "rgba(255,255,255,.075)", "panel_strong": "rgba(255,255,255,.12)", "text": text, "muted": "rgba(255,255,255,.72)", "accent": accent, "accent_2": accent_2, "shadow": f"color-mix(in srgb, {accent} 40%, transparent)"}


def _palette_light(colors: list[str]) -> dict[str, str]:
    accent = _first_color(colors, {"white", "black"}) or "#2563eb"
    accent_2 = _first_color(colors, {"white", "black", accent}) or "#facc15"
    return {"bg": "white", "panel": "rgba(255,255,255,.78)", "panel_strong": "rgba(255,255,255,.96)", "text": "black", "muted": "rgba(0,0,0,.68)", "accent": accent, "accent_2": accent_2, "shadow": f"color-mix(in srgb, {accent} 32%, transparent)"}


def _fonts(styles: list[str]) -> dict[str, str]:
    body = "'Inter', 'Segoe UI', Arial, sans-serif"
    heading = "'Inter', 'Segoe UI', Arial, sans-serif"
    if any(style in {"script", "cursive", "handwritten"} for style in styles):
        heading = "'Brush Script MT', 'Segoe Script', cursive"
    if any(style in {"gothic", "blackletter"} for style in styles):
        heading = "'Old English Text MT', Georgia, serif"
        body = "Georgia, 'Times New Roman', serif"
    if "luxury" in styles:
        heading = "'Playfair Display', Georgia, serif"
    return {"body": body, "heading": heading}


def _href(current_path: str, target_path: str | None) -> str:
    if not target_path:
        return ""
    parent = PurePosixPath(current_path).parent
    if str(parent) == ".":
        return target_path
    return "../" * len(parent.parts) + target_path


def _clean_list(values: list[Any] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _first_color(colors: list[str], blocked: set[str]) -> str:
    blocked_lower = {item.lower() for item in blocked if item}
    for color in colors:
        if color.lower() not in blocked_lower:
            return color
    return ""


def _copy(profile: str, key: str) -> Any:
    return PROFILE_COPY.get(profile, PROFILE_COPY["general"])[key]


def _special_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "food":
        return [("Friday Chili Dog", "A bold weekly special with chili, cheese, onion, and cart-side energy."), ("Classic Combo", "A signature dog, chips, and drink built for lunch traffic."), ("Catering Starter", "A simple party tray offer for offices, teams, and family events.")]
    return [("New Customer Offer", "A first-visit promotion area with clear value."), ("Bundle Deal", "Pair high-interest items into a simple conversion-focused offer."), ("Weekly Feature", "Give the business a reason to update the site often.")]


def _service_blocks(profile: str) -> list[tuple[str, str]]:
    return {"auto": [("Diagnostics", "OEM-level troubleshooting and clear repair direction."), ("ADAS Calibration", "Camera, radar, and sensor calibration workflows."), ("Programming", "Module setup and scan documentation for modern vehicles.")], "cyber": [("Security Review", "Network, account, and device posture checks."), ("Automation", "Workflow systems that reduce repeated manual work."), ("Monitoring", "Operational visibility for small business infrastructure.")], "church": [("Gatherings", "Bible study, fellowship, and community-focused events."), ("Teaching", "Sermon and resource sections with room to grow."), ("Outreach", "A clear path for visitors to connect.")]}.get(profile, [("Core Service", "A high-value offer explained in plain language."), ("Customer Support", "Make the next step clear and easy to trust."), ("Custom Work", "Room for tailored services, packages, and upgrades.")])


def _why(profile: str) -> str:
    return {"food": "Food customers need speed, appetite, and confidence. This structure shows the menu, specials, and event path immediately.", "retail": "Retail customers need categories, guidance, and trust. This structure makes the offer easy to scan and act on.", "auto": "Automotive customers need technical confidence. This structure makes the service look precise without becoming cluttered.", "church": "Visitors need warmth and clarity. This structure gives them a welcome, a reason to connect, and a next step.", "cyber": "Technology clients need proof and authority. This structure puts outcomes, services, and contact in a direct path."}.get(profile, "The design uses reusable blocks that can keep improving through natural-language edits.")


def _extract_email(question: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", question)
    return match.group(0) if match else ""


def _extract_phone(question: str) -> str:
    match = re.search(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}", question)
    return match.group(0) if match else ""
