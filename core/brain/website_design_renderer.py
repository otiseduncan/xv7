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
    "pricing": "Pricing",
    "reviews": "Reviews",
    "portfolio": "Portfolio",
    "booking": "Booking",
    "hours": "Hours",
    "safety": "Safety",
    "rentals": "Rentals",
    "aftercare": "Aftercare",
    "guided tours": "Guided Tours",
    "guided-tours": "Guided Tours",
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
    "silver": "#cbd5e1",
    "teal": "#14b8a6",
    "cyan": "#06b6d4",
    "pink": "#ec4899",
    "brown": "#92400e",
}

PROFILE_HINTS = {
    "food": ("hot dog", "hotdog", "food cart", "food truck", "menu", "catering", "restaurant", "cafe"),
    "retail": ("vape", "cbd", "smoke shop", "shop", "store", "products", "retail", "inventory"),
    "auto": ("adas", "calibration", "diagnostic", "diagnostics", "auto repair", "body shop", "vehicle", "automotive"),
    "ministry": ("church", "ministry", "bible", "sermon", "fellowship", "worship"),
    "cyber": ("cybersecurity", "cyber security", "it service", "network security", "automation", "managed monitoring"),
}

PROFILE_COPY: dict[str, dict[str, Any]] = {
    "food": {
        "eyebrow": "Fresh local flavor",
        "tagline": "A bold, street-ready food experience with menu highlights, specials, catering, and a clear path to visit or book.",
        "proof": ["Menu-first layout", "Specials built in", "Catering ready"],
        "primary": "Book catering",
        "secondary": ("View menu", "menu.html"),
        "hero": ("Menu. Specials. Catering.", "Fast choices and a clear next step."),
        "features": [("Signature menu blocks", "Featured items feel like an active cart."), ("Weekly specials", "Promotional sections give customers urgency."), ("Booking path", "Catering and contact calls-to-action are built in.")],
    },
    "retail": {
        "eyebrow": "Premium local retail",
        "tagline": "A polished retail experience with product clarity, trust, and offer-ready sections.",
        "proof": ["Product-forward", "Trust focused", "Offer ready"],
        "primary": "Visit the shop",
        "secondary": ("See products", "products.html"),
        "hero": ("Products with polish.", "Products and offers feel organized."),
        "features": [("Product categories", "Products are grouped by customer intent."), ("Premium visual system", "Dark panels and cards add retail polish."), ("Trust signals", "FAQ and guidance make the shop feel professional.")],
    },
    "auto": {
        "eyebrow": "Precision automotive service",
        "tagline": "A technical service website built around diagnostics, calibration confidence, repair-process clarity, and shop-ready calls to action.",
        "proof": ["ADAS-ready", "Diagnostic proof", "Shop workflow"],
        "primary": "Schedule service",
        "secondary": ("View services", "services.html"),
        "hero": ("Calibration confidence.", "Technical proof and service flow are clear from the first screen."),
        "features": [("ADAS calibration workflow", "Targets, scans, and calibration steps feel professional."), ("Diagnostic authority", "Service cards explain the technical value without filler."), ("Shop-ready CTA", "The path to schedule, document, and contact is obvious.")],
    },
    "ministry": {
        "eyebrow": "Faith community online",
        "tagline": "A welcoming ministry website with service information, teaching focus, events, and a warm path for visitors to connect.",
        "proof": ["Service times", "Teaching focus", "Visitor friendly"],
        "primary": "Plan a visit",
        "secondary": ("See events", "events.html"),
        "hero": ("Gather. Grow. Serve.", "A church site should feel warm, trustworthy, and easy to navigate."),
        "features": [("Visitor welcome", "First-time guests can find what matters quickly."), ("Teaching and fellowship", "Sections support sermons, study, and community life."), ("Events and contact", "People can see what is happening and reach out fast.")],
    },
    "cyber": {
        "eyebrow": "Cybersecurity and automation",
        "tagline": "A sharp technical website for assessments, monitoring, network defense, automation, and consulting credibility.",
        "proof": ["Assessment ready", "Monitoring focused", "Automation built in"],
        "primary": "Request assessment",
        "secondary": ("View services", "services.html"),
        "hero": ("Security that looks serious.", "Clear offers, proof signals, and stronger conversion flow."),
        "features": [("Risk assessment", "The offer explains what gets checked and why it matters."), ("Monitoring and response", "Customers see active protection instead of generic IT copy."), ("Automation advantage", "The site positions technical capability as the differentiator.")],
    },
    "general": {
        "eyebrow": "Local business website",
        "tagline": "A polished multi-page website with clear offers, strong sections, and an edit-ready structure.",
        "proof": ["Clear offer", "Modern design", "Ready to edit"],
        "primary": "Get started",
        "secondary": ("Explore pages", "about.html"),
        "hero": ("Built beyond a template.", "Designed to be refined."),
        "features": [("Custom page structure", "Each page gets a real role."), ("Modern visual rhythm", "Cards and CTAs create a finished feel."), ("Edit-ready content", "Copy can change without destroying layout.")],
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
    if signals["less_template"]:
        classes.append("is-customized")
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
    return _page_shell(business_name, title, _page_lede(slug, title, business_name, profile), blocks, slug == "specials", slug == "contact")


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
        f'        <a class="button button-primary" href="contact.html">{html.escape(str(_copy(profile, "primary")))}</a>',
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


def _page_title(slug: str, label: str) -> str:
    if slug == "faq":
        return "Frequently Asked Questions"
    if slug == "guided-tours":
        return "Guided Tours"
    return label


def _page_lede(slug: str, title: str, business_name: str, profile: str) -> str:
    overrides = {
        "menu": "Menu highlights, specials, and customer favorites are organized for fast decisions.",
        "specials": "Promotions are built to feel current, urgent, and easy to act on.",
        "products": "Product groups are presented with trust, clarity, and premium local retail polish.",
        "services": "Service offerings are clear, credible, and ready for local customers.",
        "contact": "Contact details and next steps stay obvious instead of buried.",
        "faq": "Common questions are answered directly so visitors feel confident before reaching out.",
        "portfolio": "Proof and examples show what makes the work credible.",
        "booking": "Booking and scheduling steps are presented with less friction.",
        "hours": "Hours and visit details are easy to scan on desktop or mobile.",
        "safety": "Safety information is treated as a trust-building page, not an afterthought.",
    }
    if slug in overrides:
        return overrides[slug]
    return f"{title} for {business_name} is written with the {profile} site purpose in mind."


def _page_blocks(slug: str, profile: str, question: str) -> list[tuple[str, str]]:
    base = _profile_blocks(profile)
    page_specific = {
        "about": [("Story and promise", "Explain why this business exists and why customers should trust it."), ("Local identity", "Show the personality and service area instead of generic filler."), ("What makes it different", "Give the page a clear reason to exist.")],
        "services": _services_blocks(profile),
        "products": [("Featured categories", "Organize inventory into customer-friendly groups."), ("Customer guidance", "Help visitors understand what to choose next."), ("Premium presentation", "Cards and contrast make products feel intentional.")],
        "menu": _menu_blocks(profile),
        "specials": _special_blocks(profile),
        "catering": [("Catering packages", "Explain event-ready options with clear next steps."), ("Group orders", "Make larger orders feel easy to request."), ("Book ahead", "Move customers toward contact or booking.")],
        "locations": [("Where to find us", "Make location and service area information scannable."), ("Visit details", "Add directions, parking, or event-location notes."), ("Mobile-ready contact", "Keep the path from phone to visit simple.")],
        "events": [("Upcoming schedule", "Show what is happening next."), ("Community focus", "Tie events to the business mission."), ("Easy RSVP", "Give visitors a reason to reach out.")],
        "gallery": [("Visual proof", "Use the gallery to support trust, not just decoration."), ("Behind the scenes", "Show real work, products, people, or place."), ("Finished results", "Highlight the best examples first.")],
        "reviews": [("Customer proof", "Use testimonials as a conversion section."), ("Trust markers", "Pull out what customers appreciate most."), ("Repeatable wins", "Show patterns in service quality.")],
        "portfolio": [("Selected work", "Show examples with context."), ("Process notes", "Explain what problem was solved."), ("Results", "Connect the work to customer value.")],
        "booking": [("Choose a service", "Make the first step obvious."), ("Pick a time", "Explain scheduling expectations."), ("Confirm details", "Reduce back-and-forth before contact.")],
        "pricing": [("Simple packages", "Group pricing so it feels understandable."), ("Value notes", "Explain what customers receive."), ("Request quote", "Keep custom pricing easy to start.")],
        "faq": [("Before you visit", "Answer the first questions customers ask."), ("What to expect", "Reduce uncertainty with plain language."), ("How to book", "Point visitors to the next step.")],
        "hours": [("Today’s hours", "Make hours prominent and easy to scan."), ("Best time to visit", "Set expectations for busy times or appointments."), ("Contact backup", "Give an alternate path if hours change.")],
        "contact": [("Call or message", "Give a clear contact path."), ("Service area", "Tell visitors where the business works."), ("Next step", "Set expectations for response and booking.")],
        "safety": [("Safety-first promise", "Put trust and compliance in plain language."), ("Customer expectations", "Explain what visitors need to know."), ("Responsible service", "Make safety feel professional and visible.")],
        "rentals": [("Rental options", "Show choices with practical details."), ("What is included", "Clarify expectations before contact."), ("Reserve now", "Move customers toward booking.")],
        "aftercare": [("Aftercare steps", "Give customers simple follow-up guidance."), ("Common issues", "Explain what to watch for."), ("Need help", "Offer a clear contact path.")],
        "guided-tours": [("Tour options", "Present routes or experiences clearly."), ("What to bring", "Prepare visitors before they arrive."), ("Book a guide", "Make the conversion path obvious.")],
    }
    return page_specific.get(slug, base)


def _profile_blocks(profile: str) -> list[tuple[str, str]]:
    return [(str(title), str(copy)) for title, copy in _copy(profile, "features")]


def _services_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "auto":
        return [("ADAS calibration", "Camera, radar, and driver-assistance calibration workflows are presented clearly."), ("OEM diagnostics", "Diagnostic capability and scan-based proof are front and center."), ("Repair support", "Body shops and drivers can understand the next step quickly.")]
    if profile == "cyber":
        return [("Security assessment", "Network and system risk checks are explained in business language."), ("Monitoring", "Ongoing visibility and alerting are positioned as core value."), ("Automation", "Repeatable scripts and workflows reduce manual busywork.")]
    if profile == "ministry":
        return [("Worship gatherings", "Service and meeting information is clear for visitors."), ("Bible teaching", "Teaching, study, and discipleship are easy to find."), ("Community care", "Fellowship and support are presented warmly.")]
    return [("Core service", "The primary offer is clear and specific."), ("Process", "Visitors understand what happens next."), ("Support", "The contact path stays visible.")]


def _menu_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "food":
        return [("Classic favorites", "Signature items, combos, and quick choices stand out."), ("Loaded options", "Specialty builds feel exciting without clutter."), ("Catering trays", "Group and event orders have their own path.")]
    return _services_blocks(profile)


def _special_blocks(profile: str) -> list[tuple[str, str]]:
    if profile == "food":
        return [("Classic Dog Combo", "A fast lunch offer with drink and side."), ("Loaded Chili Dog Special", "A bold limited-time cart favorite."), ("Family Pack Deal", "A group-friendly special for easy ordering.")]
    if profile == "retail":
        return [("Featured bundle", "Pair popular products into a clear offer."), ("Weekly deal", "Give customers a reason to come back."), ("New arrival spotlight", "Make new inventory feel premium.")]
    return [("Featured offer", "A focused promotion that feels current."), ("Limited availability", "Urgency without sounding fake."), ("Contact for details", "Move visitors toward the next step.")]


def _maybe_add_special(blocks: list[tuple[str, str]], question: str) -> list[tuple[str, str]]:
    named = _extract_named_special(question)
    if not named:
        return blocks
    lowered_titles = {title.lower() for title, _ in blocks}
    if named.lower() in lowered_titles:
        return blocks
    return [(named, "Added from the latest refinement request so the site reflects the active special."), *blocks]


def _extract_named_special(question: str) -> str:
    text = " ".join((question or "").split())
    patterns = (
        r"add (?:a |an |the )?(?P<name>[A-Z0-9][A-Za-z0-9 '&-]{2,60}? special)",
        r"include (?:a |an |the )?(?P<name>[A-Z0-9][A-Za-z0-9 '&-]{2,60}? special)",
        r"(?P<name>[A-Z0-9][A-Za-z0-9 '&-]{2,60}? special)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group("name").strip(" .,!?")
    return ""


def _card(title: str, copy: str) -> str:
    return "\n".join(['    <article class="info-card">', f"      <h2>{html.escape(title)}</h2>", f"      <p>{html.escape(copy)}</p>", "    </article>"])


def _deal(title: str, copy: str) -> str:
    return "\n".join(['    <article class="info-card deal-card">', f"      <span>Special</span>", f"      <h2>{html.escape(title)}</h2>", f"      <p>{html.escape(copy)}</p>", "    </article>"])


def _contact(title: str, copy: str) -> str:
    return "\n".join(['    <article class="info-card contact-card">', f"      <h2>{html.escape(title)}</h2>", f"      <p>{html.escape(copy)}</p>", "    </article>"])


def _footer(business_name: str) -> str:
    return "\n".join(["<footer class=\"site-footer\">", f"  <span>{html.escape(business_name)}</span>", "  <span>Built with XV7 site bundle preview.</span>", "</footer>"])


def _css(business_name: str, palette: dict[str, str], requested_colors: list[str], styles: list[str], signals: dict[str, bool]) -> str:
    requested = " ".join(requested_colors) or "default"
    style_note = " ".join(styles) or "balanced"
    return f"""
/* XV7 polished website renderer for {business_name} */
/* requested-colors: {requested} */
/* requested-styles: {style_note} */
:root {{
  --bg: {palette['bg']};
  --panel: {palette['panel']};
  --text: {palette['text']};
  --muted: {palette['muted']};
  --accent: {palette['accent']};
  --accent-2: {palette['accent_2']};
  --ring: color-mix(in srgb, var(--accent) 52%, transparent);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 26%, transparent), transparent 34rem), linear-gradient(135deg, var(--bg), #111827); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
a {{ color: inherit; }}
.site-header {{ position: sticky; top: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem clamp(1rem, 4vw, 4rem); backdrop-filter: blur(18px); background: color-mix(in srgb, var(--bg) 82%, transparent); border-bottom: 1px solid color-mix(in srgb, var(--accent) 22%, transparent); }}
.brand-mark {{ display: inline-flex; align-items: center; justify-content: center; width: 3rem; height: 3rem; border-radius: 1rem; text-decoration: none; font-weight: 900; letter-spacing: .06em; background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #020617; box-shadow: 0 18px 50px color-mix(in srgb, var(--accent) 26%, transparent); }}
.site-nav {{ display: flex; flex-wrap: wrap; gap: .55rem; justify-content: flex-end; }}
.nav-link {{ text-decoration: none; padding: .7rem .9rem; border-radius: 999px; color: var(--muted); border: 1px solid transparent; }}
.nav-link.active, .nav-link:hover {{ color: var(--text); border-color: var(--ring); background: color-mix(in srgb, var(--panel) 76%, transparent); }}
.page-content {{ width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: clamp(2rem, 6vw, 5rem) 0; }}
.hero-section {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr); gap: clamp(1.25rem, 4vw, 3rem); align-items: center; min-height: 65vh; }}
.hero-copy h1, .page-hero h1 {{ margin: 0; font-size: clamp(3rem, 9vw, 7rem); line-height: .88; letter-spacing: -.08em; }}
.hero-lede {{ max-width: 64ch; color: var(--muted); font-size: clamp(1.05rem, 2vw, 1.35rem); line-height: 1.7; }}
.eyebrow {{ color: var(--accent); text-transform: uppercase; font-weight: 900; letter-spacing: .16em; font-size: .8rem; }}
.hero-actions {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1.5rem; }}
.button {{ display: inline-flex; align-items: center; justify-content: center; min-height: 3rem; padding: .9rem 1.15rem; border-radius: 999px; text-decoration: none; font-weight: 900; border: 1px solid var(--ring); }}
.button-primary {{ color: #020617; background: linear-gradient(135deg, var(--accent), var(--accent-2)); box-shadow: 0 18px 55px color-mix(in srgb, var(--accent) 28%, transparent); }}
.button-ghost {{ color: var(--text); background: color-mix(in srgb, var(--panel) 70%, transparent); }}
.hero-card, .info-card, .split-band, .premium-band, .custom-band, .spotlight-section, .cta-band {{ border: 1px solid color-mix(in srgb, var(--accent) 22%, transparent); background: linear-gradient(145deg, color-mix(in srgb, var(--panel) 92%, transparent), color-mix(in srgb, var(--bg) 84%, transparent)); box-shadow: 0 30px 90px rgba(0,0,0,.28); }}
.hero-card {{ border-radius: 2rem; padding: clamp(1.25rem, 4vw, 2rem); }}
.hero-card strong {{ display: block; margin: .75rem 0; font-size: clamp(1.8rem, 4vw, 3.35rem); line-height: .95; letter-spacing: -.05em; }}
.proof-strip {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .9rem; margin: 1.5rem 0; }}
.proof-strip span {{ padding: 1rem; border-radius: 1.2rem; background: color-mix(in srgb, var(--panel) 75%, transparent); color: var(--muted); border: 1px solid color-mix(in srgb, var(--accent) 16%, transparent); }}
.card-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }}
.info-card {{ border-radius: 1.35rem; padding: 1.25rem; }}
.info-card h2 {{ margin: 0 0 .5rem; font-size: 1.25rem; }}
.info-card p {{ margin: 0; color: var(--muted); line-height: 1.65; }}
.deal-card span {{ display: inline-flex; margin-bottom: .75rem; color: var(--accent); font-weight: 900; text-transform: uppercase; letter-spacing: .12em; font-size: .72rem; }}
.split-band, .premium-band, .custom-band, .spotlight-section, .cta-band {{ margin-top: 1.25rem; border-radius: 1.6rem; padding: clamp(1.25rem, 4vw, 2rem); }}
.split-band {{ display: grid; grid-template-columns: .9fr 1.1fr; gap: 1.25rem; align-items: center; }}
.split-band h2, .premium-band h2, .custom-band h2, .cta-band h2 {{ margin: 0; font-size: clamp(1.8rem, 4vw, 3rem); line-height: 1; letter-spacing: -.05em; }}
.compact-hero {{ min-height: auto; padding-bottom: 1.5rem; }}
.inner-page .card-grid {{ margin-top: 1rem; }}
.compact-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
.is-premium .hero-card, .is-premium .info-card {{ border-color: color-mix(in srgb, var(--accent) 48%, transparent); }}
.is-spacious .page-content {{ padding-top: clamp(3rem, 8vw, 7rem); }}
.is-bold .button-primary {{ transform: scale(1.04); }}
.is-bold .hero-copy h1 {{ text-shadow: 0 16px 50px color-mix(in srgb, var(--accent) 22%, transparent); }}
.is-playful .brand-mark, .is-playful .button {{ border-radius: 1.35rem; }}
.is-customized .custom-band {{ border-style: dashed; }}
.site-footer {{ display: flex; justify-content: space-between; gap: 1rem; padding: 2rem clamp(1rem, 4vw, 4rem); color: var(--muted); border-top: 1px solid color-mix(in srgb, var(--accent) 18%, transparent); }}
@media (max-width: 820px) {{ .hero-section, .split-band, .card-grid, .proof-strip {{ grid-template-columns: 1fr; }} .site-header {{ position: relative; align-items: flex-start; flex-direction: column; }} .site-footer {{ flex-direction: column; }} }}
""".strip() + "\n"


def _profile(text: str) -> str:
    lowered = (text or "").lower()
    for profile, hints in PROFILE_HINTS.items():
        if any(hint in lowered for hint in hints):
            return profile
    return "general"


def _signals(question: str, styles: list[str]) -> dict[str, bool]:
    lowered = f"{question or ''} {' '.join(styles)}".lower()
    return {
        "premium": any(term in lowered for term in ("premium", "luxury", "high end", "high-end", "polished")),
        "spacious": any(term in lowered for term in ("space", "spacing", "breathe", "roomy", "larger gaps")),
        "playful": any(term in lowered for term in ("fun", "playful", "friendly", "bright")),
        "bold": any(term in lowered for term in ("bold", "pop", "stronger hero", "hero stronger", "bigger buttons", "buttons pop", "make the buttons")),
        "specials": "special" in lowered or "deal" in lowered or "offer" in lowered,
        "less_template": any(term in lowered for term in ("less template", "not template", "template-looking", "less basic", "more custom", "customize")),
    }


def _palette(colors: list[str], styles: list[str], signals: dict[str, bool]) -> dict[str, str]:
    resolved = [_to_color(color) for color in colors if _to_color(color)]
    if not resolved:
        if "light" in styles:
            resolved = ["#f8fafc", "#0f172a", "#2563eb"]
        elif signals["playful"]:
            resolved = ["#111827", "#facc15", "#ef4444"]
        else:
            resolved = ["#050505", "#22c55e", "#ffffff"]
    bg = resolved[0]
    accent = resolved[1] if len(resolved) > 1 else "#22c55e"
    accent_2 = resolved[2] if len(resolved) > 2 else accent
    text = "#ffffff" if _is_dark(bg) else "#0f172a"
    muted = "#cbd5e1" if _is_dark(bg) else "#475569"
    panel = "rgba(15,23,42,.72)" if _is_dark(bg) else "rgba(255,255,255,.76)"
    return {"bg": bg, "panel": panel, "text": text, "muted": muted, "accent": accent, "accent_2": accent_2}


def _to_color(value: str) -> str:
    token = (value or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}(?:[0-9a-f]{3})?", token):
        return token
    return COLOR_HEX.get(token, "")


def _is_dark(color: str) -> bool:
    token = color.lstrip("#")
    if len(token) == 3:
        token = "".join(ch * 2 for ch in token)
    if len(token) != 6:
        return True
    red = int(token[0:2], 16)
    green = int(token[2:4], 16)
    blue = int(token[4:6], 16)
    return ((red * 299) + (green * 587) + (blue * 114)) / 1000 < 145


def _clean_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result


def _copy(profile: str, key: str) -> Any:
    return PROFILE_COPY.get(profile, PROFILE_COPY["general"])[key]


def _why(profile: str) -> str:
    return {
        "food": "Food businesses need speed, appetite, specials, and a clear catering/contact path.",
        "retail": "Retail sites need product clarity, trust, and polished offers that make inventory feel intentional.",
        "auto": "Automotive service sites need technical trust, a clear process, and proof that the shop is in capable hands.",
        "ministry": "Church and ministry sites need warmth, clarity, visitor guidance, and visible community connection.",
        "cyber": "Cybersecurity sites need credibility, clear services, risk language, and a strong assessment path.",
    }.get(profile, "The layout gives every page a role so edits can improve the site without starting over.")


def _short_brand(name: str) -> str:
    letters = "".join(part[0] for part in re.findall(r"[A-Za-z0-9]+", name or "X"))[:3]
    return letters.upper() or "XV7"


def _href(current_path: str, target_path: str | None) -> str:
    if not target_path:
        return "#"
    current_parent = PurePosixPath(current_path).parent
    if str(current_parent) == ".":
        return target_path
    depth = len(current_parent.parts)
    return "../" * depth + target_path
