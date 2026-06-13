from __future__ import annotations

from core.brain.website_style_plan_manager import WebsiteStylePlanManager


def test_normalize_color_token_handles_typos_and_aliases() -> None:
    assert WebsiteStylePlanManager.normalize_color_token("whit") == "white"
    assert WebsiteStylePlanManager.normalize_color_token("bleu") == "blue"
    assert WebsiteStylePlanManager.normalize_color_token("purpel") == "purple"
    assert WebsiteStylePlanManager.normalize_color_token("grey") == "gray"


def test_normalize_color_token_keeps_hex_values_lowercase() -> None:
    assert WebsiteStylePlanManager.normalize_color_token("#ABC123") == "#abc123"


def test_extract_requested_colors_deduplicates_in_order() -> None:
    prompt = "Make it black, green, whit, and green again."

    assert WebsiteStylePlanManager.extract_requested_colors(prompt) == [
        "black",
        "green",
        "white",
    ]


def test_extract_requested_colors_ignores_non_colors() -> None:
    prompt = "Build a calm shop site with a booking button."

    assert WebsiteStylePlanManager.extract_requested_colors(prompt) == []


def test_extract_style_keywords_handles_aliases() -> None:
    prompt = "Make a high-end sleek futuristic site."

    assert WebsiteStylePlanManager.extract_style_keywords(prompt) == [
        "luxury",
        "modern",
        "futuristic",
    ]


def test_extract_style_keywords_deduplicates_canonical_styles() -> None:
    prompt = "A sleek modern and modern website."

    assert WebsiteStylePlanManager.extract_style_keywords(prompt) == ["modern"]


def test_infer_theme_prefers_dark_cyber_styles() -> None:
    prompt = "Build a black neon cyberpunk security site."

    assert WebsiteStylePlanManager.infer_theme(prompt) == "dark"


def test_infer_theme_prefers_light_clean_styles() -> None:
    prompt = "Build a clean white minimal wellness site."

    assert WebsiteStylePlanManager.infer_theme(prompt) == "light"


def test_build_palette_uses_requested_colors() -> None:
    prompt = "Use black, green, and gold."

    assert WebsiteStylePlanManager.build_palette(prompt) == {
        "primary": "black",
        "secondary": "green",
        "accent": "gold",
        "background": "black",
        "foreground": "white",
    }


def test_build_palette_uses_defaults_without_colors() -> None:
    assert WebsiteStylePlanManager.build_palette("Build a site") == {
        "primary": "black",
        "secondary": "white",
        "accent": "green",
        "background": "black",
        "foreground": "white",
    }


def test_build_style_plan_is_json_safe() -> None:
    prompt = "Build a sleek site using black, green, and white."

    assert WebsiteStylePlanManager.build_style_plan(prompt) == {
        "theme": "balanced",
        "colors": ["black", "green", "white"],
        "styles": ["modern"],
        "palette": {
            "primary": "black",
            "secondary": "green",
            "accent": "white",
            "background": "black",
            "foreground": "white",
        },
    }
