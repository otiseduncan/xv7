from __future__ import annotations

import html
import re
from typing import Any


class CodeArtifactBuilder:
    """Deterministic parsing and default content for single-file code artifacts."""

    @staticmethod
    def code_artifact_language(normalized_question: str) -> str:
        if "typescript" in normalized_question or re.search(
            r"\bts\b", normalized_question
        ):
            return "typescript"
        if "javascript" in normalized_question or re.search(
            r"\bjs\b", normalized_question
        ):
            return "javascript"
        if "css" in normalized_question:
            return "css"
        if "python" in normalized_question:
            return "python"
        return "html"

    @staticmethod
    def code_artifact_filename(language: str) -> str:
        if language == "css":
            return "styles.css"
        if language == "javascript":
            return "app.js"
        if language == "typescript":
            return "app.ts"
        if language == "python":
            return "main.py"
        return "index.html"

    @staticmethod
    def clean_artifact_label(text: str) -> str:
        value = re.sub(r"\s+", " ", text.strip())
        return value.strip(" .,:;\"'“”‘’")

    @classmethod
    def extract_artifact_name(cls, question: str) -> str | None:
        quoted_patterns = [
            r"one-page\s+[\"'“”‘’]([^\"'“”‘’]{2,80})[\"'“”‘’]\s+website",
            r"website\s+for\s+[\"'“”‘’]([^\"'“”‘’]{2,80})[\"'“”‘’]",
            r"for\s+[\"'“”‘’]([^\"'“”‘’]{2,80})[\"'“”‘’]",
        ]
        for pattern in quoted_patterns:
            match = re.search(pattern, question, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = cls.clean_artifact_label(match.group(1))
            if candidate:
                return candidate

        patterns = [
            (
                r"website\s+preview\s+for\s+([^,.]+?)(?:\s+return|\s+with|\s+that|\s+please|\.|,|$)",
                False,
            ),
            (r"one-page\s+([^,.]+?)\s+website", False),
            (r"for\s+([^,.]+?)\s+website", False),
            (
                r"for\s+([^,.]+?)\s+(?:grooming|dog\s+grooming|pet\s+grooming|detailing|locksmiths?|arcade|florist|flowers?)\b",
                True,
            ),
            (r"for\s+([^,.]+?)\s+using\b", True),
            (
                r"(?:html\s+)?artifact\s+([^,.]+?)\s+and\s+(?:a\s+)?(?:biker\s+bar|bar|grooming|dog\s+grooming|pet\s+grooming|detailing|locksmiths?|arcade|florist|flowers?)\b",
                True,
            ),
            (r"(?:html\s+)?artifact\s+([^,.]+?)\s+using\b", True),
            (
                r"website\s+for\s+([^,.]+?)(?:\s+return|\s+with|\s+that|\s+please|\.|,|$)",
                False,
            ),
            (r"\bfor\s+([^,.]+?)(?:\.|,|$)", False),
        ]

        suffixes = (
            " dog grooming",
            " pet grooming",
            " grooming",
            " detailing",
            " locksmiths",
            " locksmith",
            " arcade",
            " florist",
            " flowers",
            " website",
            " site",
        )
        banned_full = {
            "website",
            "site",
            "local business",
            "local business website",
            "one-page website",
            "one page website",
            "small html artifact",
            "html artifact",
            "code artifact",
            "grooming",
            "pet grooming",
            "dog grooming",
            "detailing",
            "locksmith",
            "locksmiths",
            "arcade",
            "florist",
            "flowers",
        }

        for pattern, trim_suffix in patterns:
            match = re.search(pattern, question, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = cls.clean_artifact_label(match.group(1))
            lowered = candidate.lower()
            if trim_suffix:
                for suffix in suffixes:
                    if lowered.endswith(suffix):
                        candidate = cls.clean_artifact_label(candidate[: -len(suffix)])
                        lowered = candidate.lower()
                        break
            if lowered in banned_full:
                continue
            if candidate:
                return candidate
        return None

    @staticmethod
    def artifact_business_category(question: str, name: str | None) -> str:
        text = f"{question} {name or ''}".lower()
        category_tokens = [
            (
                "locksmith",
                ("locksmith", "lockout", "rekey", "deadbolt", "key", "security lock"),
            ),
            (
                "grooming",
                (
                    "dog grooming",
                    "pet grooming",
                    "grooming",
                    "puppy",
                    "dog wash",
                    "bath",
                    "trim",
                    "fur",
                    "paw",
                    "kennel",
                    "pet spa",
                    "groomer",
                ),
            ),
            (
                "hot_dog_cart",
                ("hot dog", "hotdog", "cart", "food truck", "food cart", "concession"),
            ),
            (
                "florist",
                (
                    "flower",
                    "florist",
                    "bouquet",
                    "bouquets",
                    "blossom",
                    "bloom",
                    "petal",
                ),
            ),
            (
                "detailing",
                (
                    "detail",
                    "detailing",
                    "car wash",
                    "auto detail",
                    "mobile detailing",
                    "vehicle",
                ),
            ),
            (
                "arcade",
                (
                    "arcade",
                    "gaming",
                    "game",
                    "retro",
                    "neon byte",
                    "pixel",
                    "high score",
                ),
            ),
            ("biker_bar", ("biker bar", "bar", "tavern", "pub", "alehouse")),
        ]
        for category, tokens in category_tokens:
            if any(token in text for token in tokens):
                return category
        return "generic"

    @staticmethod
    def artifact_style_profile(question: str, category: str) -> dict[str, str]:
        text = question.lower()
        style = {
            "accent": "#fbbf24",
            "accent_2": "#fb7185",
            "font_stack": '"Segoe UI", system-ui, sans-serif',
            "hero_transform": "none",
            "bg": "#07111f",
            "panel": "rgba(10, 19, 34, 0.92)",
            "text": "#f3f7fb",
            "muted": "#b7c5d7",
            "border": "rgba(122, 214, 255, 0.18)",
        }

        profiles = {
            "locksmith": {"accent": "#dc2626", "accent_2": "#9ca3af"},
            "grooming": {
                "accent": "#7c3aed",
                "accent_2": "#22c55e",
                "bg": "#ffffff",
                "panel": "rgba(255, 255, 255, 0.96)",
                "text": "#1f2937",
                "muted": "#4b5563",
                "border": "rgba(124, 58, 237, 0.22)",
            },
            "hot_dog_cart": {"accent": "#fbbf24", "accent_2": "#fb7185"},
            "florist": {
                "accent": "#f59e0b",
                "accent_2": "#ec4899",
                "font_stack": 'Georgia, "Times New Roman", serif',
            },
            "detailing": {"accent": "#38bdf8", "accent_2": "#22d3ee"},
            "arcade": {
                "accent": "#a855f7",
                "accent_2": "#22d3ee",
                "font_stack": '"Trebuchet MS", "Arial Black", sans-serif',
                "hero_transform": "uppercase",
            },
            "biker_bar": {
                "accent": "#f97316",
                "accent_2": "#facc15",
                "font_stack": '"Trebuchet MS", "Arial Black", sans-serif',
                "bg": "#070707",
                "panel": "rgba(12, 12, 12, 0.96)",
                "text": "#f5f5f5",
                "muted": "#d4d4d4",
                "border": "rgba(249, 115, 22, 0.24)",
            },
        }
        style.update(profiles.get(category, {}))

        if any(token in text for token in ("purple", "violet", "magenta")):
            style["accent"] = "#a855f7"
        if "yellow" in text:
            style["accent"] = "#facc15"
        if "gold" in text:
            style["accent"] = "#d4af37"
        if "red" in text:
            style["accent"] = "#dc2626"
        if "orange" in text:
            style["accent"] = "#f97316"
        if "blue" in text:
            style["accent"] = "#2563eb"
        if any(token in text for token in ("green", "mint", "lime")):
            style["accent_2"] = "#22c55e"
        if "black" in text:
            style.update(
                {
                    "bg": "#070707",
                    "panel": "rgba(12, 12, 12, 0.96)",
                    "text": "#f5f5f5",
                    "muted": "#d4d4d4",
                    "border": "rgba(250, 204, 21, 0.24)",
                }
            )
        if "white" in text:
            style.update(
                {
                    "bg": "#ffffff",
                    "panel": "rgba(255, 255, 255, 0.96)",
                    "text": "#111827",
                    "muted": "#4b5563",
                }
            )
        if "silver" in text:
            style["accent_2"] = "#c0c0c0"
        if any(token in text for token in ("cyan", "aqua", "teal")):
            style["accent_2"] = "#22d3ee"
        if any(token in text for token in ("elegant", "luxury")):
            style["font_stack"] = 'Georgia, "Times New Roman", serif'
        if any(token in text for token in ("retro", "futuristic")):
            style["font_stack"] = '"Trebuchet MS", "Arial Black", sans-serif'
        if (
            any(token in text for token in ("clean", "playful"))
            and category != "arcade"
        ):
            style["font_stack"] = '"Segoe UI", system-ui, sans-serif'

        if any(token in text for token in ("white", "cream")) and any(
            token in text for token in ("black", "dark")
        ):
            style["text"] = "#111827"
            style["panel"] = "rgba(255, 255, 255, 0.94)"

        return style

    @staticmethod
    def format_business_name(name: str | None, fallback: str) -> str:
        value = (name or "").strip()
        return value or fallback

    @classmethod
    def build_business_site_template(cls, question: str) -> dict[str, Any]:
        business_name = cls.extract_artifact_name(question)
        category = cls.artifact_business_category(question, business_name)
        display_name = cls.format_business_name(business_name, "Local Business Website")
        style = cls.artifact_style_profile(question, category)
        return cls._template_for_category(question, category, display_name, style)

    @classmethod
    def default_code_artifact_content(
        cls, filename: str, language: str, question: str
    ) -> str:
        if language == "html":
            return cls._default_html_content(question)

        if language == "css":
            return """body {
    margin: 0;
    font-family: system-ui, sans-serif;
}
"""

        display_name = cls.format_business_name(
            cls.extract_artifact_name(question),
            "Local Business Website" if language == "html" else "Draft Artifact",
        )

        if language == "javascript":
            return f'const brand = "{display_name}";\nconsole.log(brand);'
        if language == "typescript":
            return f'const brand: string = "{display_name}";\nconsole.log(brand);'
        if language == "python":
            return f"""def main() -> None:
    print(\"{display_name}\")


if __name__ == \"__main__\":
    main()
"""
        return f"# Draft artifact for {filename}\n"

    @classmethod
    def extract_requested_filename(cls, question: str, language: str) -> str:
        match = re.search(
            r"\bfilename\s*[=:]?\s*[\"'“”‘’]?([a-zA-Z0-9._-]{1,80})[\"'“”‘’]?",
            question,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return cls.code_artifact_filename(language)

    @staticmethod
    def extract_requested_previewable(question: str, language: str) -> bool:
        match = re.search(
            r"\bpreviewable\s*[=:]?\s*(true|false)\b", question, flags=re.IGNORECASE
        )
        if match:
            return match.group(1).lower() == "true"
        return language == "html"

    @staticmethod
    def extract_apply_intent(question: str) -> bool:
        lowered = question.lower()
        if "do not apply" in lowered or "don't apply" in lowered:
            return False
        if "apply it to the repo" in lowered or "apply to the repo" in lowered:
            return True
        return False

    @staticmethod
    def extract_style_hints(question: str) -> dict[str, list[str]]:
        lowered = question.lower()
        known_colors = (
            "black",
            "white",
            "red",
            "blue",
            "green",
            "yellow",
            "orange",
            "purple",
            "pink",
            "cream",
            "gold",
            "silver",
            "cyan",
            "teal",
            "magenta",
        )
        colors = [
            color
            for color in known_colors
            if re.search(rf"\b{re.escape(color)}\b", lowered)
        ]
        colors.extend(re.findall(r"#[0-9a-f]{3,8}\b", lowered))

        style_keywords = (
            "elegant",
            "script",
            "futuristic",
            "retro",
            "bold",
            "playful",
            "trustworthy",
            "urgent",
            "automotive",
            "clean",
            "modern",
            "minimal",
            "neon",
        )
        styles = [
            token
            for token in style_keywords
            if re.search(rf"\b{re.escape(token)}\b", lowered)
        ]
        return {
            "colors": list(dict.fromkeys(colors)),
            "styles": list(dict.fromkeys(styles)),
        }

    @staticmethod
    def extract_layout_hints(question: str) -> list[str]:
        candidates = re.findall(
            r"\b(include|with|featuring|highlight|show)\s+([^.;]{3,140})",
            question,
            flags=re.IGNORECASE,
        )
        hints: list[str] = []
        for _, value in candidates:
            cleaned = value.strip(" .")
            if cleaned:
                hints.append(cleaned)
        return hints[:6]

    @staticmethod
    def artifact_intent_label(question: str) -> str:
        lowered = question.lower()
        if "small html artifact" in lowered:
            return "small HTML artifact"
        if "one-page" in lowered and "website" in lowered:
            return "one-page website"
        if "html" in lowered:
            return "HTML artifact"
        return "code artifact"

    @classmethod
    def _template_for_category(
        cls, question: str, category: str, display_name: str, style: dict[str, str]
    ) -> dict[str, Any]:
        palette = ", ".join(cls.extract_style_hints(question).get("colors", []))
        palette_line = (
            f"Requested palette applied across grooming stations and CTA accents: {palette}."
            if palette
            else "Requested palette applied across grooming stations and CTA accents."
        )
        templates: dict[str, dict[str, Any]] = {
            "locksmith": {
                "hero": "Locked out? Fast, verified locksmith response when every minute matters.",
                "lead": f"An urgent, trust-first one-page locksmith website for {display_name} focused on emergency lockout service, rekeying, and home security.",
                "primary_cta": "Call emergency lockout now",
                "secondary_cta": "View security services",
                "highlight_title": "Emergency & Security Services",
                "highlights": [
                    (
                        "24/7 Emergency Lockout",
                        "Rapid dispatch for home, office, and vehicle lockouts",
                    ),
                    (
                        "Rekey & Key Duplication",
                        "Secure key control without full lock replacement",
                    ),
                    (
                        "Deadbolt & Entry Security",
                        "Reinforced hardware and break-in response",
                    ),
                ],
                "info_title": "Why Residents Trust Us",
                "info_lines": [
                    "Licensed local locksmith technicians with verified ID on arrival.",
                    "Upfront pricing before work starts. No hidden after-hours surprises.",
                    "Priority dispatch for urgent lockout and compromised-lock situations.",
                ],
                "action_title": "Need Help Right Now?",
                "action_body": "Call now for immediate emergency lockout support and on-site security restoration.",
                "action_label": "Dispatch Technician",
            },
            "grooming": {
                "hero": "Pet grooming that keeps every pup clean, calm, and camera-ready.",
                "lead": f"A friendly one-page pet grooming website for {display_name} featuring gentle bath, trim, and coat care with easy booking.",
                "primary_cta": "Book a grooming appointment",
                "secondary_cta": "See bath & trim services",
                "highlight_title": "Dog & Pet Grooming Services",
                "highlights": [
                    (
                        "Bath & Wash",
                        "Deep clean wash with pet-safe shampoo and careful rinse",
                    ),
                    (
                        "Trim & Paw Care",
                        "Breed-aware trim, nail touch-up, and paw tidy service",
                    ),
                    (
                        "Coat & Fur Care",
                        "Deshed, brush-out, and coat conditioning for comfort",
                    ),
                ],
                "info_title": "Why Pet Parents Choose Us",
                "info_lines": [
                    "Calm, pet-safe handling for puppies and adult dogs.",
                    palette_line,
                    "Simple appointment booking and clear service timing.",
                ],
                "action_title": "Ready for a Fresh Groom?",
                "action_body": "Book your pet grooming appointment for bath, trim, fur care, and a happy return home.",
                "action_label": "Book Grooming",
            },
            "hot_dog_cart": {
                "hero": "Fresh dogs, fast service, neighborhood flavor.",
                "lead": f"A one-page local website for {display_name} with quick pickup, bold toppings, and a friendly street-side feel.",
                "primary_cta": "See the menu",
                "secondary_cta": "Plan your visit",
                "highlight_title": "Menu Highlights",
                "highlights": [
                    ("Classic Cart Dog", "Mustard, relish, onion"),
                    ("Chicago-Style Dog", "Pickle, tomato, sport peppers"),
                    ("Loaded Chili Dog", "Cheese, onion, jalapeno"),
                ],
                "info_title": "Location & Hours",
                "info_lines": [
                    "Main Street corner near the park.",
                    "Mon-Sat, 11:00 AM - 7:00 PM",
                    "Sunday by event schedule",
                ],
                "action_title": "Order Ahead",
                "action_body": "Call ahead, swing by for pickup, or ask about catering for local events.",
                "action_label": "Call Now",
            },
            "florist": {
                "hero": "Fresh blooms, thoughtful arrangements, same-day smiles.",
                "lead": f"A one-page florist website for {display_name} with bouquets, seasonal stems, and delivery-ready service.",
                "primary_cta": "Browse bouquets",
                "secondary_cta": "Schedule delivery",
                "highlight_title": "Featured Arrangements",
                "highlights": [
                    ("Seasonal Bouquets", "Hand-tied color stories for every room"),
                    ("Event Florals", "Weddings, showers, and celebrations"),
                    ("Daily Bloom Bar", "Fresh picks ready to go"),
                ],
                "info_title": "Shop Info",
                "info_lines": [
                    "Neighborhood studio with local pickup.",
                    "Mon-Sat, 9:00 AM - 6:00 PM",
                    "Same-day delivery available in town",
                ],
                "action_title": "Send Flowers",
                "action_body": "Choose a bouquet, add a note, and let the blooms do the talking.",
                "action_label": "Order Flowers",
            },
            "detailing": {
                "hero": "Mobile shine, showroom finish, driveway convenience.",
                "lead": f"A one-page mobile detailing website for {display_name} with on-site wash, interior refresh, and protective finishes.",
                "primary_cta": "Book a detail",
                "secondary_cta": "View packages",
                "highlight_title": "Detailing Packages",
                "highlights": [
                    ("Interior Reset", "Vacuum, wipe-down, glass, and trim"),
                    ("Exterior Wash", "Paint-safe wash and wheel cleaning"),
                    ("Protection Add-On", "Sealant for longer-lasting shine"),
                ],
                "info_title": "Service Area",
                "info_lines": [
                    "Mobile appointments at home or work.",
                    "Mon-Sat, 8:00 AM - 6:00 PM",
                    "Serving cars, trucks, and SUVs",
                ],
                "action_title": "Schedule Service",
                "action_body": "Pick a package, choose a time, and get a clean ride without the wait.",
                "action_label": "Book Now",
            },
            "arcade": {
                "hero": "Play fast, chase high scores, and keep the neon glowing.",
                "lead": f"A one-page arcade website for {display_name} with cabinets, tournaments, and a bold retro-futuristic feel.",
                "primary_cta": "Start playing",
                "secondary_cta": "See the games",
                "highlight_title": "Featured Games",
                "highlights": [
                    ("Pixel Runner", "Fast reflexes, bright lights, leaderboard chase"),
                    ("Neon Drift", "Racing lanes with glowing city vibes"),
                    ("Boss Battle", "High-score challenge for night owls"),
                ],
                "info_title": "Arcade Info",
                "info_lines": [
                    "Open late with classic cabinets and modern favorites.",
                    "Friday-Sunday tournaments and free-play nights.",
                    "Bring friends, grab tokens, and push the high score.",
                ],
                "action_title": "Join the Game",
                "action_body": "Drop in, power up, and claim a spot on the scoreboard.",
                "action_label": "Play Now",
            },
            "biker_bar": {
                "hero": "Heavy bikes, loud riffs, cold pours, and a road-ready crowd.",
                "lead": f"A one-page biker bar website for {display_name} with live music nights, tap highlights, and rally-friendly events.",
                "primary_cta": "See tonight's lineup",
                "secondary_cta": "View tap list",
                "highlight_title": "Biker Bar Highlights",
                "highlights": [
                    (
                        "Live Music Nights",
                        "Weekly sets with local hard rock and blues bands",
                    ),
                    (
                        "House Tap Picks",
                        "Rotating drafts, whiskey pours, and rider specials",
                    ),
                    (
                        "Road Crew Events",
                        "Bike meetups, poker runs, and weekend rally starts",
                    ),
                ],
                "info_title": "The Tavern Vibe",
                "info_lines": [
                    "Leather jackets welcome, helmets by the door, good times on tap.",
                    "Black, orange, and yellow palette tuned for a bold late-night biker bar look.",
                    "Open late with food, drinks, and event nights built for the ride-in crowd.",
                ],
                "action_title": "Roll In Tonight",
                "action_body": "Check the live set, lock in your crew, and ride over for the next round.",
                "action_label": "Plan Your Night",
            },
        }
        data = templates.get(
            category,
            {
                "hero": "A clean one-page website with a clear offer and simple call to action.",
                "lead": f"A one-page business website for {display_name} with a bold hero, useful details, and a clear next step.",
                "primary_cta": "Explore services",
                "secondary_cta": "Get in touch",
                "highlight_title": "Key Services",
                "highlights": [
                    ("Service One", "Simple summary of the main offer"),
                    ("Service Two", "Supporting option or package"),
                    ("Service Three", "Another helpful detail for visitors"),
                ],
                "info_title": "Business Info",
                "info_lines": [
                    "Local service with a friendly, direct approach.",
                    "Open by appointment or posted hours.",
                    "Reach out for pricing, availability, or booking.",
                ],
                "action_title": "Contact Us",
                "action_body": "Call, email, or send a quick message to get started.",
                "action_label": "Contact",
            },
        )
        return {"display_name": display_name, "style": style, **data}

    @classmethod
    def _default_html_content(cls, question: str) -> str:
        template = cls.build_business_site_template(question)
        display_name = html.escape(str(template["display_name"]), quote=False)
        hero = html.escape(str(template["hero"]), quote=False)
        lead = html.escape(str(template["lead"]), quote=False)
        highlight_title = html.escape(str(template["highlight_title"]), quote=False)
        info_title = html.escape(str(template["info_title"]), quote=False)
        action_title = html.escape(str(template["action_title"]), quote=False)
        action_body = html.escape(str(template["action_body"]), quote=False)
        primary_cta = html.escape(str(template["primary_cta"]), quote=False)
        secondary_cta = html.escape(str(template["secondary_cta"]), quote=False)
        action_label = html.escape(str(template["action_label"]), quote=False)
        highlights = "".join(
            f'<li><span>{html.escape(str(left), quote=False)}</span><span class="muted">{html.escape(str(right), quote=False)}</span></li>'
            for left, right in template["highlights"]
        )
        info_lines = "".join(
            f'<p class="muted">{html.escape(str(line), quote=False)}</p>'
            for line in template["info_lines"]
        )
        requested_colors = cls.extract_style_hints(question).get("colors", [])
        if requested_colors:
            palette_text = html.escape(
                ", ".join(str(color) for color in requested_colors),
                quote=False,
            )
            info_lines += f'<p class="muted">Requested palette: {palette_text}</p>'
        style = template["style"]
        return cls._html_shell(
            display_name=display_name,
            hero=hero,
            lead=lead,
            highlight_title=highlight_title,
            info_title=info_title,
            action_title=action_title,
            action_body=action_body,
            primary_cta=primary_cta,
            secondary_cta=secondary_cta,
            action_label=action_label,
            highlights=highlights,
            info_lines=info_lines,
            style=style,
        )

    @staticmethod
    def _html_shell(**data: Any) -> str:
        style = data["style"]
        bg = str(style.get("bg", "#07111f"))
        panel = str(style.get("panel", "rgba(10, 19, 34, 0.92)"))
        text_color = str(style.get("text", "#f3f7fb"))
        muted = str(style.get("muted", "#b7c5d7"))
        border = str(style.get("border", "rgba(122, 214, 255, 0.18)"))
        return f"""<!doctype html>
<html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{data["display_name"]}</title>
        <style>
            :root {{
                color-scheme: dark;
                --bg: {bg};
                --panel: {panel};
                --text: {text_color};
                --muted: {muted};
                --accent: {style["accent"]};
                --accent-2: {style["accent_2"]};
                --border: {border};
                --font-stack: {style["font_stack"]};
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                min-height: 100vh;
                font-family: var(--font-stack);
                color: var(--text);
                background:
                    radial-gradient(circle at top, color-mix(in srgb, var(--accent) 22%, transparent), transparent 36%),
                    linear-gradient(180deg, color-mix(in srgb, var(--bg) 88%, #0a1323) 0%, var(--bg) 52%, color-mix(in srgb, var(--bg) 80%, #050b14) 100%);
            }}
            .page {{
                min-height: 100vh;
                display: grid;
                place-items: center;
                padding: 24px;
            }}
            .card {{
                width: min(960px, 100%);
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 28px;
                overflow: hidden;
                box-shadow: 0 30px 70px rgba(0, 0, 0, 0.35);
            }}
            .hero {{
                padding: 40px 28px 28px;
                background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 20%, transparent), color-mix(in srgb, var(--accent-2) 14%, transparent));
            }}
            .eyebrow {{
                display: inline-flex;
                padding: 8px 12px;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.08);
                color: var(--muted);
                font-size: 0.82rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }}
            h1 {{
                margin: 18px 0 12px;
                font-size: clamp(2.4rem, 7vw, 4.8rem);
                line-height: 0.95;
                letter-spacing: -0.05em;
                text-transform: {style["hero_transform"]};
            }}
            .lead {{
                max-width: 62ch;
                margin: 0;
                color: var(--muted);
                font-size: clamp(1rem, 2.2vw, 1.15rem);
                line-height: 1.6;
            }}
            .hero-actions {{
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 24px;
            }}
            .button {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 48px;
                padding: 0 18px;
                border-radius: 999px;
                text-decoration: none;
                font-weight: 700;
            }}
            .button.primary {{
                color: #111827;
                background: linear-gradient(135deg, var(--accent), var(--accent-2));
            }}
            .button.secondary {{
                color: var(--text);
                border: 1px solid rgba(255, 255, 255, 0.14);
                background: rgba(255, 255, 255, 0.05);
            }}
            .grid {{
                display: grid;
                gap: 20px;
                padding: 28px;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            }}
            .panel {{
                padding: 20px;
                border-radius: 22px;
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            .panel h2 {{
                margin: 0 0 10px;
                font-size: 1.1rem;
            }}
            .menu-list {{
                margin: 0;
                padding: 0;
                list-style: none;
                display: grid;
                gap: 10px;
            }}
            .menu-list li {{
                display: flex;
                justify-content: space-between;
                gap: 16px;
                padding-bottom: 10px;
                border-bottom: 1px dashed rgba(255, 255, 255, 0.12);
            }}
            .muted {{ color: var(--muted); }}
            @media (max-width: 640px) {{
                .hero, .grid {{ padding-left: 18px; padding-right: 18px; }}
                .button {{ width: 100%; }}
            }}
        </style>
    </head>
    <body>
        <main class=\"page\">
            <section class=\"card\">
                <header class=\"hero\">
                    <div class=\"eyebrow\">{data["display_name"]}</div>
                    <h1>{data["hero"]}</h1>
                    <p class=\"lead\">{data["lead"]}</p>
                    <div class=\"hero-actions\">
                        <a class=\"button primary\" href=\"#highlights\">{data["primary_cta"]}</a>
                        <a class=\"button secondary\" href=\"#info\">{data["secondary_cta"]}</a>
                    </div>
                </header>
                <section class=\"grid\">
                    <article class=\"panel\" id=\"highlights\">
                        <h2>{data["highlight_title"]}</h2>
                        <ul class=\"menu-list\">{data["highlights"]}</ul>
                    </article>
                    <article class=\"panel\" id=\"info\">
                        <h2>{data["info_title"]}</h2>
                        {data["info_lines"]}
                    </article>
                    <article class=\"panel\">
                        <h2>{data["action_title"]}</h2>
                        <p class=\"muted\">{data["action_body"]}</p>
                        <a class=\"button primary\" href=\"#highlights\">{data["action_label"]}</a>
                    </article>
                </section>
            </section>
        </main>
    </body>
</html>"""
