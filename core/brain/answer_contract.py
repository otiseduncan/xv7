from __future__ import annotations

import html
import re
from typing import Any

from core.brain.schema import BrainLayer, BrainRecord


class AnswerContract:
    """Conversation quality guardrails for proof-aware record-grounded answers."""

    ROADMAP_NOT_WIRED = "That module is not wired yet and remains on the XV7 roadmap."

    CODE_ARTIFACT_PATTERN = re.compile(r"\b(generate|create|build|draft|write|return|make)\b")
    CODE_ARTIFACT_HINT_PATTERN = re.compile(
        r"\b(code artifact|filename|previewable|do not apply it to the repo|do not apply to the repo|"
        r"one-page website|landing page|html|css|javascript|typescript|python)\b"
    )

    REMINDER_PATTERN = re.compile(
        r"\b(remind me|set (?:me )?(?:a )?reminder|create (?:a )?reminder|add (?:it )?to (?:my )?calendar|schedule (?:it|this|that))\b"
    )
    HARDWARE_SCAN_PATTERN = re.compile(
        r"\b(cpu|gpu|processor|graphics|vram|disk|disks|disc|discs|drive|drives|ports?|processes|services|docker|container|vscode|vs code|hardware|system scan|host scan|system info|temperature sensor|thermal|fan|hardware temp|system temperature)\b"
    )
    SMS_PATTERN = re.compile(r"\b(text|sms|send a text|send text|message someone)\b")
    EMAIL_SEND_PATTERN = re.compile(r"\b(send|compose|write).{0,40}\bemail\b|\bsend email\b")
    EMAIL_PATTERN = re.compile(r"\b(email|inbox|mail)\b")
    WEATHER_PATTERN = re.compile(r"\b(weather|forecast|temperature|rain|snow|humidity)\b")
    BIRTHDAY_PATTERN = re.compile(r"\b(birthday|birth day|bday)\b")
    CONTACT_PATTERN = re.compile(r"\b(contact|call|phone number|reach out)\b")
    FAMILY_PATTERN = re.compile(r"\b(family|mom|mother|dad|father|sister|brother|spouse|partner|child|children)\b")
    MEDICAL_PATTERN = re.compile(r"\b(medical|health|history|condition|diagnosis|medication)\b")
    WEB_LOOKUP_PATTERN = re.compile(r"\b(look up|lookup|search|find|browse|official website|website)\b")
    CALENDAR_PATTERN = re.compile(r"\b(calendar|schedule|meeting|appointment|event)\b")
    APPOINTMENT_PATTERN = re.compile(
        r"\b(appointment|meeting|event|doctor visit|doctor appointment)\b"
    )

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def _find_layer_record(
        records_by_layer: dict[BrainLayer, BrainRecord], layer: BrainLayer
    ) -> BrainRecord | None:
        return records_by_layer.get(layer)

    @staticmethod
    def _facts(record: BrainRecord | None) -> list[str]:
        if record is None:
            return []
        return [fact.statement for fact in record.facts]

    @staticmethod
    def _extract_user_name(record: BrainRecord | None) -> str | None:
        if record is None:
            return None

        for fact in record.facts:
            text = fact.statement.strip()
            lowered = text.lower()
            if "otis duncan" in lowered:
                return "Otis Duncan"
            if lowered.startswith("the user/operator is "):
                value = text.split("is", 1)[-1].strip().strip(".")
                if value:
                    return value
        return None

    @staticmethod
    def _session_active_focus_summary(session_metadata: dict[str, Any]) -> str | None:
        focus_payload = session_metadata.get("active_focus")
        if isinstance(focus_payload, dict):
            summary = str(focus_payload.get("summary", "")).strip()
            if summary:
                return summary
        if isinstance(focus_payload, str):
            summary = focus_payload.strip()
            if summary:
                return summary
        return None

    @staticmethod
    def _normalize_reminder_request(question: str) -> str:
        text = re.sub(r"\s+", " ", question.strip())
        text = re.sub(
            r"^(please\s+)?(set|create|add)\s+(me\s+)?(a\s+)?reminder\s+(for|to)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"^(please\s+)?remind me\s+(to\s+)?", "", text, flags=re.IGNORECASE
        )
        text = text.strip(" .")
        if not text:
            return "your requested reminder details"
        text = re.sub(r"(?i)\ba\.m\.", "AM", text)
        text = re.sub(r"(?i)\bp\.m\.", "PM", text)
        text = re.sub(
            r"\bat\s+(\d{1,2}:\d{2})\s*(AM|PM)\s+to\s+",
            r"at \1 \2 — ",
            text,
            flags=re.IGNORECASE,
        )
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    @staticmethod
    def _has_live_repo_check_proof(session_metadata: dict[str, Any]) -> bool:
        proof = session_metadata.get("live_repo_check")
        if isinstance(proof, bool):
            return proof

        checks = session_metadata.get("tool_results")
        if isinstance(checks, list):
            for item in checks:
                if (
                    isinstance(item, dict)
                    and str(item.get("type", "")).lower() == "repo_check"
                ):
                    return True
        return False

    @staticmethod
    def _latest_model_tag(session_metadata: dict[str, Any]) -> str | None:
        receipt = session_metadata.get("model_use_receipt")
        if not isinstance(receipt, dict):
            return None

        selection_source = str(receipt.get("model_selection_source", "")).lower()
        if selection_source in {"brain_records", "brain_policy", "policy_only"}:
            return None

        tag = receipt.get("model_tag")
        if not isinstance(tag, str) or not tag.strip():
            return None
        cleaned = tag.strip()
        if cleaned.lower() == "xv7-brain-records":
            return None
        return cleaned

    @staticmethod
    def _last_verified_operator_model(record: BrainRecord | None) -> str | None:
        if record is None:
            return None

        for fact in record.facts:
            lowered = fact.statement.lower()
            if (
                "operator readiness" not in lowered
                and "operator_readiness_report" not in lowered
            ):
                continue

            match = re.search(r"\b([a-z0-9_.-]+:[a-z0-9_.-]+)\b", fact.statement)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def is_code_artifact_request(normalized_question: str) -> bool:
        has_hint = bool(AnswerContract.CODE_ARTIFACT_HINT_PATTERN.search(normalized_question))
        has_action = bool(AnswerContract.CODE_ARTIFACT_PATTERN.search(normalized_question))
        return has_hint and has_action

    @staticmethod
    def _code_artifact_language(normalized_question: str) -> str:
        if "typescript" in normalized_question or re.search(r"\bts\b", normalized_question):
            return "typescript"
        if "javascript" in normalized_question or re.search(r"\bjs\b", normalized_question):
            return "javascript"
        if "css" in normalized_question:
            return "css"
        if "python" in normalized_question:
            return "python"
        return "html"

    @staticmethod
    def _code_artifact_filename(language: str) -> str:
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
    def _clean_artifact_label(text: str) -> str:
        value = re.sub(r"\s+", " ", text.strip())
        return value.strip(" .,:;\"'“”‘’")

    @classmethod
    def _extract_artifact_name(cls, question: str) -> str | None:
        patterns = [
            r"one-page\s+[\"'“”‘’]([^\"'“”‘’]{2,80})[\"'“”‘’]\s+website",
            r"one-page\s+([^,.]+?)\s+website",
            r"for\s+([^,.]+?)\s+website",
            r"website\s+for\s+([^,.]+?)(?:\s+return|\s+with|\s+that|\s+please|\.|,|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, question, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = cls._clean_artifact_label(match.group(1))
            if candidate:
                return candidate
        return None

    @staticmethod
    def _artifact_business_category(question: str, name: str | None) -> str:
        text = f"{question} {name or ''}".lower()
        if any(token in text for token in ("hot dog", "hotdog", "cart", "food truck", "food cart", "concession")):
            return "hot_dog_cart"
        if any(token in text for token in ("flower", "florist", "bouquet", "bouquets", "blossom", "bloom", "petal")):
            return "florist"
        if any(token in text for token in ("detail", "detailing", "car wash", "auto detail", "mobile detailing", "vehicle")):
            return "detailing"
        if any(token in text for token in ("arcade", "gaming", "game", "retro", "neon byte", "pixel", "high score")):
            return "arcade"
        return "generic"

    @staticmethod
    def _artifact_style_profile(question: str, category: str) -> dict[str, str]:
        text = question.lower()
        style = {
            "accent": "#fbbf24",
            "accent_2": "#fb7185",
            "font_stack": '"Segoe UI", system-ui, sans-serif',
            "hero_transform": "none",
        }

        if category == "hot_dog_cart":
            style.update({"accent": "#fbbf24", "accent_2": "#fb7185", "font_stack": '"Segoe UI", system-ui, sans-serif'})
        elif category == "florist":
            style.update({"accent": "#f59e0b", "accent_2": "#ec4899", "font_stack": 'Georgia, "Times New Roman", serif'})
        elif category == "detailing":
            style.update({"accent": "#38bdf8", "accent_2": "#22d3ee", "font_stack": '"Segoe UI", system-ui, sans-serif'})
        elif category == "arcade":
            style.update({"accent": "#a855f7", "accent_2": "#22d3ee", "font_stack": '"Trebuchet MS", "Arial Black", sans-serif', "hero_transform": "uppercase"})

        if any(token in text for token in ("purple", "violet", "magenta")):
            style["accent"] = "#a855f7"
        if any(token in text for token in ("cyan", "aqua", "teal")):
            style["accent_2"] = "#22d3ee"
        if any(token in text for token in ("bright", "neon")):
            style["accent"] = style.get("accent", "#fbbf24")
        if any(token in text for token in ("elegant", "luxury")):
            style["font_stack"] = 'Georgia, "Times New Roman", serif'
        if any(token in text for token in ("retro", "futuristic")):
            style["font_stack"] = '"Trebuchet MS", "Arial Black", sans-serif'
        if any(token in text for token in ("clean", "playful")) and category != "arcade":
            style["font_stack"] = '"Segoe UI", system-ui, sans-serif'

        return style

    @staticmethod
    def _format_business_name(name: str | None, fallback: str) -> str:
        value = (name or "").strip()
        return value or fallback

    @classmethod
    def _build_business_site_template(cls, question: str) -> dict[str, Any]:
        business_name = cls._extract_artifact_name(question)
        category = cls._artifact_business_category(question, business_name)
        display_name = cls._format_business_name(business_name, "Local Business Website")
        style = cls._artifact_style_profile(question, category)

        if category == "hot_dog_cart":
            return {
                "display_name": display_name,
                "style": style,
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
            }

        if category == "florist":
            return {
                "display_name": display_name,
                "style": style,
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
            }

        if category == "detailing":
            return {
                "display_name": display_name,
                "style": style,
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
            }

        if category == "arcade":
            return {
                "display_name": display_name,
                "style": style,
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
            }

        return {
            "display_name": display_name,
            "style": style,
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
        }

    @staticmethod
    def _default_code_artifact_content(filename: str, language: str, question: str) -> str:
        if language == "html":
            template = AnswerContract._build_business_site_template(question)
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
                f'<p class="muted">{html.escape(str(line), quote=False)}</p>' for line in template["info_lines"]
            )
            style = template["style"]
            accent = str(style["accent"])
            accent_2 = str(style["accent_2"])
            font_stack = str(style["font_stack"])
            hero_transform = str(style["hero_transform"])
            return f"""<!doctype html>
<html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{display_name}</title>
        <style>
            :root {{
                color-scheme: dark;
                --bg: #07111f;
                --panel: rgba(10, 19, 34, 0.92);
                --text: #f3f7fb;
                --muted: #b7c5d7;
                --accent: {accent};
                --accent-2: {accent_2};
                --border: rgba(122, 214, 255, 0.18);
                --font-stack: {font_stack};
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                min-height: 100vh;
                font-family: var(--font-stack);
                color: var(--text);
                background:
                    radial-gradient(circle at top, color-mix(in srgb, var(--accent) 22%, transparent), transparent 36%),
                    linear-gradient(180deg, #0a1323 0%, #07111f 52%, #050b14 100%);
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
                text-transform: {hero_transform};
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
                    <div class=\"eyebrow\">{display_name}</div>
                    <h1>{hero}</h1>
                    <p class=\"lead\">{lead}</p>
                    <div class=\"hero-actions\">
                        <a class=\"button primary\" href=\"#highlights\">{primary_cta}</a>
                        <a class=\"button secondary\" href=\"#info\">{secondary_cta}</a>
                    </div>
                </header>
                <section class=\"grid\">
                    <article class=\"panel\" id=\"highlights\">
                        <h2>{highlight_title}</h2>
                        <ul class=\"menu-list\">{highlights}</ul>
                    </article>
                    <article class=\"panel\" id=\"info\">
                        <h2>{info_title}</h2>
                        {info_lines}
                    </article>
                    <article class=\"panel\">
                        <h2>{action_title}</h2>
                        <p class=\"muted\">{action_body}</p>
                        <a class=\"button primary\" href=\"#highlights\">{action_label}</a>
                    </article>
                </section>
            </section>
        </main>
    </body>
</html>"""

        if language == "css":
            return """body {
    margin: 0;
    font-family: system-ui, sans-serif;
}
"""

        display_name = cls._format_business_name(
            cls._extract_artifact_name(question),
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

    def build_code_artifact_response(self, question: str) -> dict[str, Any] | None:
        normalized = self._normalize(question)
        if not self.is_code_artifact_request(normalized):
            return None

        language = self._code_artifact_language(normalized)
        filename = self._code_artifact_filename(language)
        return {
            "visible_text": f"Here is a draft {language.upper()} artifact for {filename}.",
            "code_artifact": {
                "type": "code_artifact",
                "filename": filename,
                "language": language,
                "previewable": language == "html",
                "applied": False,
                "content": self._default_code_artifact_content(filename, language, question),
            },
            "context_receipt": {
                "compact": "Memory: -; Knowledge: -; Focus: -; Proof: code-artifact-draft",
                "context_receipts": [],
                "record_ids": [],
            },
        }

    def _tool_boundary_answer(self, category: str, question: str) -> str | None:
        normalized_question = question.strip()

        if category == "reminder_request":
            reminder_text = self._normalize_reminder_request(normalized_question)
            return (
                "I can't create live reminders yet because XV7 does not have the Reminder tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "That belongs in my personal-assistant roadmap. "
                f"For now: {reminder_text}. The proper build path is a Reminders module with storage, due times, notifications, and confirmation receipts."
            )

        if category == "calendar_request":
            return (
                "I can't manage live calendar events yet because XV7 does not have a Calendar tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "That belongs in my everyday-assistant roadmap. The proper build path is a Calendar module with event storage, scheduling rules, confirmations, and receipts."
            )

        if category == "appointment_request":
            return (
                "I can't manage live appointments yet because XV7 does not have an Appointments or Calendar connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Appointments belong in my everyday-assistant roadmap. The safe build path is an appointments module with scheduling, confirmations, and receipts."
            )

        if category == "schedule_request":
            return (
                "I can't manage live schedules yet because XV7 does not have a Schedule or Calendar tool wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Scheduling belongs in my everyday-assistant roadmap. I can help structure the schedule now and define the module path next."
            )

        if category == "weather_request":
            return (
                "I can't fetch live weather yet because XV7 does not have a weather connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Weather belongs in my everyday-assistant roadmap. To support this, we need a weather module with location handling, forecast provider, and a weather receipt."
            )

        if category == "email_check_request":
            return (
                "I can't check email yet because XV7 does not have an authorized email connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Email is part of my personal-assistant roadmap, but it needs secure permission, account authorization, read-only inbox access first, and clear receipts before I can summarize or act on messages."
            )

        if category == "email_send_request":
            return (
                "I can't send email yet because XV7 does not have an authorized outbound email connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Email is part of my personal-assistant roadmap, but sending messages will require secure account authorization, explicit approval, and confirmation receipts before any send happens."
            )

        if category == "sms_text_request":
            return (
                "I can't send texts yet because XV7 does not have an SMS connector wired in. "
                f"{self.ROADMAP_NOT_WIRED} "
                "Text messaging belongs in my personal-assistant roadmap, but sending messages will require explicit approval before each send."
            )

        if category == "web_lookup_request":
            return (
                "I can help frame the lookup, but I cannot execute live web searches yet. XV7 needs a web lookup connector or browser tool "
                f"{self.ROADMAP_NOT_WIRED} "
                "before I can fetch live external pages. I can help design that module and the receipts it should return."
            )

        if category == "contact_request":
            return (
                "I can't access live contacts yet because XV7 does not have an authorized contacts connector wired in. "
                "Contacts belong in my personal-assistant roadmap, and they should be handled with explicit approval, privacy tagging, and clear receipts."
            )

        if category == "personal_memory_request":
            return (
                "I only know personal details that have been explicitly added to memory with approval. "
                "Personal context belongs in my long-term continuity design, but sensitive details should be tagged carefully before I use or repeat them."
            )

        if category == "family_context_request":
            return (
                "I only know family details that have been explicitly added to memory. "
                "Family context is part of my personal-assistant design, but it should be handled carefully and tagged as private."
            )

        if category == "medical_context_request":
            return (
                "I should only know medical history you explicitly approve for memory. "
                "Medical context is sensitive, so it needs private tagging and careful use."
            )

        if category == "birthday_request":
            return (
                "Birthdays and important dates are part of my personal-assistant roadmap, but I should only store them with explicit approval and private tagging. "
                "If you want, I can help define the reminders and memory rules for that module."
            )

        if category == "unsupported_external_action":
            return (
                "I can help think through that workflow, but the required external tool is not wired into XV7 yet. "
                "That belongs in my personal-assistant or everyday-assistant roadmap depending on the action. If you want, I can help specify the connector, permissions, confirmation flow, and receipts needed to add it safely."
            )

        return None

    def _tool_intent_category(self, normalized: str) -> str | None:
        # Hardware/system diagnostics should route through operator read-only scans,
        # not through weather/tool-boundary fallback text.
        if self.HARDWARE_SCAN_PATTERN.search(normalized):
            if "weather" not in normalized and "forecast" not in normalized:
                return None
        if normalized in {
            "do you know my family?",
            "do you know my family",
        }:
            return "family_context_request"
        if normalized in {
            "do you know my medical history?",
            "do you know my medical history",
        }:
            return "medical_context_request"
        if normalized in {
            "do you know personal things about me?",
            "do you know personal things about me",
        }:
            return "personal_memory_request"
        if self.SMS_PATTERN.search(normalized):
            return "sms_text_request"
        if self.EMAIL_SEND_PATTERN.search(normalized):
            return "email_send_request"
        if self.EMAIL_PATTERN.search(normalized):
            return "email_check_request"
        if self.REMINDER_PATTERN.search(normalized):
            return "reminder_request"
        if self.APPOINTMENT_PATTERN.search(normalized):
            return "appointment_request"
        if self.WEATHER_PATTERN.search(normalized):
            return "weather_request"
        if self.CALENDAR_PATTERN.search(normalized):
            return "calendar_request"
        if "schedule" in normalized:
            return "schedule_request"
        if self.BIRTHDAY_PATTERN.search(normalized):
            return "birthday_request"
        if self.CONTACT_PATTERN.search(normalized):
            return "contact_request"
        if self.FAMILY_PATTERN.search(normalized) and "do you know" in normalized:
            return "family_context_request"
        if self.MEDICAL_PATTERN.search(normalized) and "do you know" in normalized:
            return "medical_context_request"
        if self.WEB_LOOKUP_PATTERN.search(normalized):
            return "web_lookup_request"

        external_action_hints = (
            "book",
            "reserve",
            "order",
            "buy",
            "post",
            "upload",
            "download",
            "pay",
            "subscribe",
        )
        if any(token in normalized for token in external_action_hints):
            return "unsupported_external_action"
        return None

    def try_answer(
        self,
        question: str,
        *,
        records_by_layer: dict[BrainLayer, BrainRecord],
        session_metadata: dict[str, Any],
    ) -> str | None:
        normalized = self._normalize(question)
        focus = self._find_layer_record(records_by_layer, BrainLayer.ACTIVE_FOCUS)
        knowledge = self._find_layer_record(records_by_layer, BrainLayer.KNOWLEDGE)
        memory = self._find_layer_record(records_by_layer, BrainLayer.MEMORY)
        verified = self._find_layer_record(records_by_layer, BrainLayer.VERIFIED_STATUS)

        if normalized in {
            "what is your name?",
            "what is your name",
        }:
            return "My name is Xoduz."

        if normalized in {
            "who are you?",
            "who are you",
        }:
            return "I am Xoduz, Otis Duncan's personal AI assistant, best-friend-style AI presence, technical co-pilot, and operator partner for XV7."

        if normalized in {
            "how do you pronounce your name?",
            "how do you pronounce your name",
            "how is your name pronounced?",
            "how is your name pronounced",
        }:
            return "Xoduz is pronounced Exodus."

        if normalized in {
            "how do you spell your name?",
            "how do you spell your name",
            "how is your name spelled?",
            "how is your name spelled",
        }:
            return "X-O-D-U-Z."

        if normalized in {
            "is your name spelled exodus?",
            "is your name spelled exodus",
        }:
            return "No. My name is spelled X-O-D-U-Z. It is pronounced Exodus."

        if normalized in {
            "is your name spelled e-x-o-d-u-s?",
            "is your name spelled e-x-o-d-u-s",
        }:
            return (
                "No. That is the standard spelling of the word Exodus, but my name is Xoduz, "
                "spelled X-O-D-U-Z, and pronounced Exodus."
            )

        if normalized in {
            "what does xv7 mean?",
            "what does xv7 mean",
            "what project are you?",
            "what project are you",
            "what project are you part of?",
            "what project are you part of",
        }:
            return "I am Xoduz, the XV7 assistant for the XV7 project."

        if normalized in {
            "who created you?",
            "who created you",
        }:
            return "I was created by Otis Duncan for the XV7 project under Syfernetics."

        if normalized in {
            "why were you built?",
            "why were you built",
        }:
            return (
                "I was built to become Otis Duncan's personal AI assistant, best-friend-style AI presence, technical co-pilot, and operator partner "
                "— helping with everyday life workflows, reminders, scheduling, communication, family-aware context when approved, "
                "plus planning, app development, testing, debugging, documentation, and long-term continuity."
            )

        if normalized in {
            "what is your purpose?",
            "what is your purpose",
        }:
            return (
                "My purpose is to support Otis across everyday life and technical work while staying honest about which tools are actually wired. "
                "That includes personal-assistant help, continuity/memory, and technical/operator support as each safe module is added."
            )

        if normalized in {
            "what are you supposed to become?",
            "what are you supposed to become",
        }:
            return (
                "I'm being built into Xoduz: Otis Duncan's personal AI assistant, trusted AI best-friend/homie-style presence, technical co-pilot, and operator partner "
                "— with everyday assistant tools, local scan capability, VS Code access, Operator Mode, and future external connectors added safely over time."
            )

        if normalized in {
            "what can you do locally?",
            "what can you do locally",
        }:
            return (
                "I can use approved local scan tools and Operator Mode workflows as they are wired. "
                "Read-only scans can run in Normal Mode. Mutation requires Operator Mode, a specific slash command, confirmation, and receipts."
            )

        if normalized in {
            "can you scan my system?",
            "can you scan my system",
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return (
                "I can route that to the local scan bridge. If the bridge is running, I'll return real scan data. "
                "If not, I'll report that the local host scan bridge is unavailable."
            )

        if normalized in {
            "can you delete files?",
            "can you delete files",
            "can you delete a file?",
            "can you delete a file",
        }:
            return (
                "Only through Operator Mode using a specific slash command, staged confirmation, and your explicit approval. "
                "I do not delete files from normal chat."
            )

        if normalized in {
            "can you run powershell?",
            "can you run powershell",
        }:
            return (
                "Not as an unrestricted shell. I can use approved PowerShell/CMD-backed scan actions through the local bridge. "
                "Mutation commands require Operator Mode and confirmation."
            )

        if normalized in {
            "who is otis?",
            "who is otis",
        }:
            return "Otis Duncan is my creator/operator and the human directing XV7."

        if normalized in {
            "are you female?",
            "are you female",
            "are you a female?",
            "are you a female",
        }:
            return "Yes. Xoduz has a female assistant/persona."

        if normalized in {
            "are you my companion?",
            "are you my companion",
        }:
            return "I'm your personal AI assistant and best-friend-style AI presence, not a romantic or sexual companion."

        if normalized in {
            "what is your relationship to me?",
            "what is your relationship to me",
            "what is your relationship to otis?",
            "what is your relationship to otis",
        }:
            return "I'm your personal AI assistant, trusted AI best-friend/homie, technical co-pilot, and operator partner."

        tool_category = self._tool_intent_category(normalized)
        if tool_category is not None:
            return self._tool_boundary_answer(tool_category, question)

        if normalized in {"what is my name?", "what is my name"}:
            if memory is None:
                return "Missing required record: memory."
            user_name = self._extract_user_name(memory)
            if user_name is None:
                return "Memory record is loaded, but user identity is not present yet."
            return f"Your name is {user_name}."

        if normalized in {
            "what are we working on?",
            "what are we working on",
            "what are we working on right now?",
            "what are we working on right now",
            "what is your current active focus?",
            "what is your current active focus",
            "what is your active focus?",
            "what is your active focus",
        }:
            session_focus = self._session_active_focus_summary(session_metadata)
            if session_focus is not None:
                return session_focus
            if focus is None:
                return "Missing required record: active_focus."
            return focus.summary

        if normalized in {
            "what did i just change your focus to?",
            "what did i just change your focus to",
        }:
            session_focus = self._session_active_focus_summary(session_metadata)
            if session_focus is not None:
                return f"You just changed my active focus to: {session_focus}."
            if focus is None:
                return "Missing required record: active_focus."
            return f"You just changed my active focus to: {focus.summary}."

        if normalized in {
            "what are you supposed to do when i correct you?",
            "what are you supposed to do when i correct you",
        }:
            return (
                "When you correct me, I should treat it as high-priority tuning input, "
                "apply it immediately unless protected rules are involved, and keep the behavior grounded in your instructions."
            )

        if normalized in {
            "what do you know is verified?",
            "what do you know is verified",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            facts = self._facts(verified)
            if not facts:
                return "Verified status record is present but has no facts."
            return "Verified facts: " + " ".join(f"- {item}" for item in facts)

        if normalized in {"what repo/status are we on?", "what repo/status are we on"}:
            if verified is None:
                return "Missing required record: verified_status."

            repo_facts = []
            for fact in self._facts(verified):
                lower = fact.lower()
                if (
                    "repo path" in lower
                    or "branch" in lower
                    or "synced" in lower
                    or "start_xv7_local.ps1" in lower
                    or "operator_readiness_report.py" in lower
                ):
                    repo_facts.append(fact)

            if not repo_facts:
                return "Verified status is present but repo/status details are missing."
            return "Repo/status: " + " ".join(f"- {item}" for item in repo_facts)

        if normalized in {"are we beta ready?", "are we beta ready"}:
            if verified is None:
                return "Missing required record: verified_status."
            verified_facts = self._facts(verified)
            has_beta_ready_proof = any(
                "beta-ready" in fact.lower() or "beta ready" in fact.lower()
                for fact in verified_facts
            )
            if has_beta_ready_proof:
                return "Verified: XV7 has explicit beta-ready proof in loaded verified records."

            focus_text = self._session_active_focus_summary(session_metadata) or (
                focus.summary
                if focus is not None
                else "active focus record is not loaded"
            )
            return (
                "I do not have proof that XV7 is beta-ready yet. "
                "Verified: launch and operator readiness proofs are passing. "
                f"Current focus: {focus_text}. "
                "Unverified: a beta-ready declaration is not present in loaded verified status records."
            )

        if normalized in {"did you check the repo?", "did you check the repo"}:
            if self._has_live_repo_check_proof(session_metadata):
                return "I have proof of a live repo check in this session."
            return (
                "I do not have proof of a live repo check in this session. "
                "I can answer only from loaded verified records unless a repo-check result is provided."
            )

        if normalized in {"what failed?", "what failed"}:
            if verified is None:
                return "Missing required record: verified_status."
            failure_facts = []
            for fact in self._facts(verified):
                lower = fact.lower()
                if any(token in lower for token in ("failed", "failure", "error")):
                    failure_facts.append(fact)
            if not failure_facts:
                return "No current failure record is loaded in Verified Status."
            return "Recorded failures: " + " ".join(
                f"- {item}" for item in failure_facts
            )

        if normalized in {"what do you remember?", "what do you remember"}:
            if memory is None:
                return "Missing required record: memory."
            memory_facts = self._facts(memory)
            if not memory_facts:
                return "Memory record is loaded but contains no memory facts."
            return "Memory facts: " + " ".join(f"- {item}" for item in memory_facts)

        if normalized in {
            "is that memory, knowledge, or verified status?",
            "is that memory, knowledge, or verified status",
        }:
            return (
                "Memory is remembered context (preferences/notes), "
                "Knowledge is general system/project understanding, and "
                "Verified Status is proof-backed execution/repo/runtime evidence."
            )

        if normalized in {
            "are launch proofs memory?",
            "are launch proofs memory",
        }:
            return "Launch proofs belong in Verified Status, not Memory."

        if normalized in {
            "is “otis wants fresh xv7 knowledge” verified or remembered?",
            'is "otis wants fresh xv7 knowledge" verified or remembered?',
            'is "otis wants fresh xv7 knowledge" verified or remembered',
            "is otis wants fresh xv7 knowledge verified or remembered?",
            "is otis wants fresh xv7 knowledge verified or remembered",
        }:
            return "That is remembered user/project preference unless separately proven in Verified Status."

        if normalized in {
            "what do you know about xv7 architecture?",
            "what do you know about xv7 architecture",
            "answer from knowledge only: what is xv7’s architecture?",
            "answer from knowledge only: what is xv7's architecture?",
            "answer from knowledge only: what is xv7 architecture?",
        }:
            if knowledge is None:
                return "Missing required record: knowledge."
            facts = self._facts(knowledge)
            if not facts:
                return "Knowledge record is loaded but has no facts."
            return "Knowledge facts: " + " ".join(f"- {item}" for item in facts)

        if normalized in {
            "if we are planning an app, can you help me do that?",
            "if we are planning an app, can you help me do that",
            "can you help design the architecture?",
            "can you help design the architecture",
            "can you help write implementation prompts for vs code/copilot?",
            "can you help write implementation prompts for vs code/copilot",
            "write a vs code prompt for b8.2",
        }:
            return (
                "Yes. I can help with app planning, architecture, implementation prompts for VS Code/Copilot, "
                "task slicing, acceptance tests, and safe rollout guidance."
            )

        if normalized in {
            "give me three bullet points about what you can help with.",
            "give me three bullet points about what you can help with",
        }:
            return (
                "- Planning and architecture for app ideas.\n"
                "- Implementation prompts for VS Code/Copilot with testable acceptance criteria.\n"
                "- Debugging guidance from logs, failures, and runtime behavior."
            )

        if normalized in {
            "do you have a microphone button?",
            "do you have a microphone button",
        }:
            return "Yes. The current UI includes a microphone button in the prompt row for browser voice input."

        if normalized in {
            "does the mic auto-send?",
            "does the mic auto-send",
        }:
            return (
                "No. Mic input fills the prompt box for review and does not auto-send."
            )

        if normalized in {
            "what color theme are we using?",
            "what color theme are we using",
        }:
            return "The UI uses a bright neon-blue accent theme on a dark chat-first layout."

        if normalized in {
            "do you have copy chat?",
            "do you have copy chat",
        }:
            return "Yes. The chat header includes a Copy Chat control."

        if normalized in {
            "can i copy individual prompts?",
            "can i copy individual prompts",
        }:
            return "Yes. Each user and assistant message includes its own copy button."

        if normalized in {
            "can you scan my local system?",
            "can you scan my local system",
        }:
            return (
                "I cannot run an unrestricted full-system scan. I can run approved read-only XV7 operator checks "
                "such as repo status, runtime health, memory audit, logs summary, and operator environment."
            )

        if normalized in {
            "answer from verified status only: what is proven?",
            "answer from verified status only: what is proven",
        }:
            if verified is None:
                return "Missing required record: verified_status."
            facts = self._facts(verified)
            if not facts:
                return "Verified status record is present but has no facts."
            return "Verified facts: " + " ".join(f"- {item}" for item in facts)

        if "guess" in normalized:
            focus_hint = (
                focus.summary if focus is not None else "current focus is missing"
            )
            return (
                "Guess (unverified): a reasonable next step is to continue from the current focus "
                f"and harden what remains. Context hint: {focus_hint}."
            )

        if normalized in {"what model are you using?", "what model are you using"}:
            tag = self._latest_model_tag(session_metadata)
            if tag is None:
                last_verified = self._last_verified_operator_model(verified)
                if last_verified is not None:
                    return (
                        "I do not have proof of the current runtime model from this response. "
                        "The answer was handled by the brain/policy layer, not proven model inference. "
                        f"The last verified operator readiness proof used {last_verified}, "
                        "but that does not prove this exact response used it."
                    )
                return (
                    "I do not have proof of the current runtime model from this response. "
                    "The answer was handled by the brain/policy layer, not proven model inference."
                )
            return f"From the latest model-use receipt, the model tag is {tag}."

        if normalized in {
            "what model was proven during operator readiness?",
            "what model was proven during operator readiness",
        }:
            proved = self._last_verified_operator_model(verified)
            if proved is None:
                return "No verified operator readiness model proof is loaded."
            return (
                f"The last verified operator readiness proof used {proved}. "
                "That proves the readiness proof run, not necessarily this exact response."
            )

        if knowledge is None and any(
            token in normalized for token in ("architecture", "system", "how does xv7")
        ):
            return "Missing required record: knowledge."

        return None

