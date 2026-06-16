"""Helpers for deriving deterministic website style plans from prompts.

This module is intentionally standalone during the Code 22 manager-only phase.
It does not mutate runtime state and is not wired into AnswerContract yet.
"""

from __future__ import annotations

import re
from typing import Any


class WebsiteStylePlanManager:
    """Build JSON-safe website style and palette planning payloads."""

    COLOR_ALIASES = {
        "bleu": "blue",
        "cherry": "red",
        "blu": "blue",
        "charcoal": "gray",
        "emerald": "green",
        "grey": "gray",
        "lime": "green",
        "purpel": "purple",
        "purp": "purple",
        "tealgreen": "teal",
        "whit": "white",
    }

    KNOWN_COLORS = (
        "black",
        "white",
        "green",
        "red",
        "blue",
        "purple",
        "orange",
        "yellow",
        "gray",
        "gold",
        "silver",
        "pink",
        "brown",
        "teal",
        "cyan",
    )

    STYLE_ALIASES = {
        "high end": "luxury",
        "high-end": "luxury",
        "minimalistic": "minimal",
        "premium": "luxury",
        "simple": "minimal",
        "sleek": "modern",
        "techy": "futuristic",
    }

    KNOWN_STYLES = (
        "modern",
        "clean",
        "luxury",
        "bold",
        "dark",
        "light",
        "futuristic",
        "rustic",
        "professional",
        "playful",
        "minimal",
        "neon",
        "cyberpunk",
    )

    DEFAULT_PALETTE = {
        "primary": "black",
        "secondary": "white",
        "accent": "green",
        "background": "black",
        "foreground": "white",
    }

    HEX_PATTERN = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b")
    TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z-]*|#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?")

    @classmethod
    def normalize_color_token(cls, token: str) -> str:
        """Return a canonical color token or an empty string."""

        value = token.strip().lower().strip(".,;:!?)('\"")
        if not value:
            return ""
        if cls.HEX_PATTERN.fullmatch(value):
            return value.lower()
        value = value.replace(" ", "")
        value = cls.COLOR_ALIASES.get(value, value)
        if value in cls.KNOWN_COLORS:
            return value
        return ""

    @classmethod
    def extract_requested_colors(cls, prompt: str) -> list[str]:
        """Extract unique color requests from prompt text."""

        colors: list[str] = []
        seen: set[str] = set()
        for token in cls.TOKEN_PATTERN.findall(prompt or ""):
            color = cls.normalize_color_token(token)
            if color and color not in seen:
                colors.append(color)
                seen.add(color)
        return colors

    @classmethod
    def normalize_style_keyword(cls, text: str) -> str:
        """Return a canonical style keyword or an empty string."""

        value = " ".join((text or "").lower().strip().split())
        if not value:
            return ""
        value = cls.STYLE_ALIASES.get(value, value)
        if value in cls.KNOWN_STYLES:
            return value
        return ""

    @classmethod
    def extract_style_keywords(cls, prompt: str) -> list[str]:
        """Extract unique style keywords from prompt text."""

        haystack = f" {(prompt or '').lower()} "
        styles: list[str] = []
        seen: set[str] = set()

        for alias, canonical in cls.STYLE_ALIASES.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", haystack):
                if canonical not in seen:
                    styles.append(canonical)
                    seen.add(canonical)

        for style in cls.KNOWN_STYLES:
            if re.search(rf"(?<![a-z0-9]){re.escape(style)}(?![a-z0-9])", haystack):
                if style not in seen:
                    styles.append(style)
                    seen.add(style)
        return styles

    @classmethod
    def infer_theme(cls, prompt: str) -> str:
        """Infer a broad visual theme from colors and style keywords."""

        colors = set(cls.extract_requested_colors(prompt))
        styles = set(cls.extract_style_keywords(prompt))
        if {"dark", "neon", "cyberpunk", "futuristic"} & styles:
            return "dark"
        if {"black", "purple", "cyan"} & colors and "white" not in colors:
            return "dark"
        if {"light", "clean", "minimal"} & styles:
            return "light"
        if {"white", "silver"} & colors and "black" not in colors:
            return "light"
        return "balanced"

    @classmethod
    def build_palette(cls, prompt: str) -> dict[str, str]:
        """Build a deterministic palette from requested colors."""

        colors = cls.extract_requested_colors(prompt)
        if not colors:
            return dict(cls.DEFAULT_PALETTE)

        primary = colors[0]
        secondary = colors[1] if len(colors) > 1 else cls.DEFAULT_PALETTE["secondary"]
        accent = colors[2] if len(colors) > 2 else cls.DEFAULT_PALETTE["accent"]
        theme = cls.infer_theme(prompt)

        if theme == "light":
            background = "white"
            foreground = "black"
        elif theme == "dark":
            background = "black"
            foreground = "white"
        else:
            background = (
                primary
                if primary in {"black", "white"}
                else cls.DEFAULT_PALETTE["background"]
            )
            foreground = "white" if background == "black" else "black"

        return {
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
            "background": background,
            "foreground": foreground,
        }

    @classmethod
    def build_style_plan(cls, prompt: str) -> dict[str, Any]:
        """Build a JSON-safe style plan payload."""

        colors = cls.extract_requested_colors(prompt)
        styles = cls.extract_style_keywords(prompt)
        theme = cls.infer_theme(prompt)
        return {
            "theme": theme,
            "colors": colors,
            "styles": styles,
            "palette": cls.build_palette(prompt),
        }


class DesignIntentInterpreter:
    """Maps user visual design phrases to concrete CSS token modifications."""

    # Visual intent phrases and their CSS/design token mappings
    DARKER_PHRASES = (
        "make it darker", "darker theme", "darker background", "dim the colors",
        "less bright", "reduce brightness", "make it moody", "darker mood"
    )
    LIGHTER_PHRASES = (
        "make it lighter", "lighter theme", "lighter background", "brighter colors",
        "more bright", "increase brightness", "make it airy"
    )
    GLOW_PHRASES = (
        "add glow", "glowing", "add glowing", "make it glow", "glow effects",
        "add glowing effects", "make buttons glow", "make cards glow", "hero glow",
        "make the buttons glow", "add a red glow", "red glow",
        "make the hero pop", "hero pop"
    )
    TRANSLUCENT_PHRASES = (
        "make translucent", "translucent cards", "glass effect", "frosted cards",
        "frosted glass", "transparent cards", "make it transparent", "blur effect",
        "backdrop blur", "frosted border", "cards translucent"
    )
    FONT_SIZE_PHRASES = (
        "make font bigger", "bigger text", "larger text", "increase font size",
        "make text bigger", "make font size bigger", "bigger headings",
        "make the font bigger",
        "make it smaller", "smaller text", "decrease font size"
    )
    SPACING_PHRASES = (
        "spread layout out", "increase spacing", "more space", "looser layout",
        "spread the layout out more",
        "compact layout", "tight spacing", "dense layout", "decrease spacing"
    )
    CARD_PHRASES = (
        "card layout", "card density", "card padding", "card design", "cards",
        "more cards", "fewer cards", "card grid"
    )
    PREMIUM_PHRASES = (
        "make it premium", "premium look", "luxurious", "high end", "upscale",
        "polished", "refined", "elegant", "sophisticated"
    )
    MODERN_PHRASES = (
        "make it modern", "modern design", "contemporary", "sleek", "clean lines"
    )

    @classmethod
    def extract_design_intent(cls, prompt: str) -> dict[str, Any]:
        """Extract design intent signals from a user request."""

        lower_prompt = (prompt or "").lower()
        intent = {
            "darker": False,
            "lighter": False,
            "glow": False,
            "translucent": False,
            "font_bigger": False,
            "font_smaller": False,
            "spacing_increase": False,
            "spacing_decrease": False,
            "premium": False,
            "modern": False,
            "intensity": "medium",  # subtle, medium, strong
        }

        for phrase in cls.DARKER_PHRASES:
            if phrase in lower_prompt:
                intent["darker"] = True
                break

        for phrase in cls.LIGHTER_PHRASES:
            if phrase in lower_prompt:
                intent["lighter"] = True
                break

        for phrase in cls.GLOW_PHRASES:
            if phrase in lower_prompt:
                intent["glow"] = True
                break

        for phrase in cls.TRANSLUCENT_PHRASES:
            if phrase in lower_prompt:
                intent["translucent"] = True
                break

        for phrase in cls.FONT_SIZE_PHRASES:
            if "smaller" in phrase and phrase in lower_prompt:
                intent["font_smaller"] = True
            elif phrase in lower_prompt:
                intent["font_bigger"] = True

        for phrase in cls.SPACING_PHRASES:
            if "decrease" in phrase or "tight" in phrase or "compact" in phrase or "dense" in phrase:
                if phrase in lower_prompt:
                    intent["spacing_decrease"] = True
            elif phrase in lower_prompt:
                intent["spacing_increase"] = True

        for phrase in cls.PREMIUM_PHRASES:
            if phrase in lower_prompt:
                intent["premium"] = True
                break

        for phrase in cls.MODERN_PHRASES:
            if phrase in lower_prompt:
                intent["modern"] = True
                break

        # Determine overall intensity
        if any(word in lower_prompt for word in ("very", "much", "lot", "really", "strong")):
            intent["intensity"] = "strong"
        elif any(word in lower_prompt for word in ("slightly", "little", "bit", "subtle")):
            intent["intensity"] = "subtle"

        return intent

    @classmethod
    def build_css_modifications(cls, intent: dict[str, Any]) -> dict[str, Any]:
        """Convert design intent into CSS modifications."""

        mods = {
            "background_brightness": None,  # -0.2 (darker), +0.2 (lighter)
            "text_contrast": None,
            "glow_strength": None,  # 0-1
            "translucent_alpha": None,  # 0.1-0.9
            "backdrop_blur": None,  # px
            "font_scale": 1.0,
            "spacing_scale": 1.0,
            "shadow_strength": 1.0,
            "accent_glow": False,
            "button_glow": False,
            "card_glow": False,
            "hero_glow": False,
        }

        intensity_scale = {"subtle": 0.5, "medium": 1.0, "strong": 1.5}[intent.get("intensity", "medium")]

        if intent["darker"]:
            mods["background_brightness"] = -0.2 * intensity_scale
            mods["text_contrast"] = 1.1
            mods["shadow_strength"] = 1.3

        if intent["lighter"]:
            mods["background_brightness"] = 0.2 * intensity_scale
            mods["text_contrast"] = 0.9

        if intent["glow"]:
            mods["glow_strength"] = 0.6 * intensity_scale
            mods["button_glow"] = True
            mods["accent_glow"] = True
            mods["card_glow"] = True
            mods["hero_glow"] = True

        if intent["translucent"]:
            mods["translucent_alpha"] = 0.7 * intensity_scale
            mods["backdrop_blur"] = 12 * intensity_scale

        if intent["font_bigger"]:
            mods["font_scale"] = 1.15 * intensity_scale

        if intent["font_smaller"]:
            mods["font_scale"] = 0.85 / intensity_scale

        if intent["spacing_increase"]:
            mods["spacing_scale"] = 1.2 * intensity_scale

        if intent["spacing_decrease"]:
            mods["spacing_scale"] = 0.8 / intensity_scale

        if intent["premium"]:
            mods["shadow_strength"] = 1.4
            mods["text_contrast"] = 1.05
            mods["button_glow"] = True
            mods["card_glow"] = True

        if intent["modern"]:
            mods["shadow_strength"] = 1.1
            mods["spacing_scale"] = 1.05

        return mods

    @classmethod
    def build_design_change_receipt(cls, intent: dict[str, Any], mods: dict[str, Any]) -> str:
        """Build a human-readable receipt of design changes."""

        changes: list[str] = []

        if intent["darker"]:
            changes.append("colors: darker")

        if intent["lighter"]:
            changes.append("colors: lighter")

        if intent["glow"]:
            intensity = intent.get("intensity", "medium")
            changes.append(f"glow: {intensity}")

        if mods.get("shadow_strength") and mods["shadow_strength"] != 1.0:
            shadow_strength = str(mods["shadow_strength"])
            changes.append(f"shadow: strength {shadow_strength}")

        if intent["translucent"]:
            blur_px = int(float(mods.get("backdrop_blur") or 0))
            changes.append("cards: frosted glass")
            changes.append(f"glass/translucency: blur {blur_px}px")

        if intent["font_bigger"]:
            changes.append("typography: increased heading/body scale")

        if intent["font_smaller"]:
            changes.append("typography: decreased heading/body scale")

        if intent["spacing_increase"]:
            changes.append("layout: spacious card gaps")

        if intent["spacing_decrease"]:
            changes.append("layout: compact card gaps")

        if intent["premium"]:
            changes.append("card style: premium depth")

        if intent["modern"]:
            changes.append("card style: modern clean")

        if not changes:
            return "No visual changes applied."

        receipt = "Updated site styling: " + "; ".join(changes) + "."
        return receipt

