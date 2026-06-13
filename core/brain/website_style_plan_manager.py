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
            background = primary if primary in {"black", "white"} else cls.DEFAULT_PALETTE["background"]
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
