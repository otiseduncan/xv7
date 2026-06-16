from __future__ import annotations

from core.brain.site_bundle import apply_design_intent_to_css
from core.brain.website_style_plan_manager import DesignIntentInterpreter
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


def _design_css_fixture() -> str:
    return """
:root {
  --accent: #ef4444;
}
.hero-section { margin: 1rem; }
.hero-card { box-shadow: none; }
.card, .info-card { background: #101010; }
.button { border: 1px solid #ef4444; }
""".strip()


def test_design_receipt_and_css_for_translucent_cards_with_red_glow() -> None:
    prompt = "Make the cards translucent and add a red glow."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()
    css = apply_design_intent_to_css(_design_css_fixture(), mods).lower()

    assert intent["translucent"] is True
    assert intent["glow"] is True
    assert "cards: frosted glass" in receipt
    assert "glow: medium" in receipt
    assert "glass/translucency" in receipt
    assert "backdrop-filter: blur(" in css
    assert "drop-shadow" in css


def test_design_receipt_and_css_for_frosted_glass_cards() -> None:
    prompt = "Use frosted glass cards."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()
    css = apply_design_intent_to_css(_design_css_fixture(), mods).lower()

    assert intent["translucent"] is True
    assert "cards: frosted glass" in receipt
    assert "backdrop-filter: blur(" in css


def test_design_receipt_and_css_for_bigger_fonts() -> None:
    prompt = "Make the font bigger."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()
    css = apply_design_intent_to_css(_design_css_fixture(), mods).lower()

    assert intent["font_bigger"] is True
    assert "typography: increased heading/body scale" in receipt
    assert "--font-scale" in css
    assert "h1 { font-size: calc(2.4rem * var(--font-scale" in css


def test_design_receipt_and_css_for_spread_layout() -> None:
    prompt = "Spread the layout out more."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()
    css = apply_design_intent_to_css(_design_css_fixture(), mods).lower()

    assert intent["spacing_increase"] is True
    assert "layout: spacious card gaps" in receipt
    assert "--spacing-scale" in css
    assert "section, .section { margin: calc(2rem * var(--spacing-scale" in css


def test_design_colors_support_dark_black_and_cherry_red() -> None:
    plan = WebsiteStylePlanManager.build_style_plan("Use dark black and cherry red.")

    assert "black" in plan["colors"]
    assert "red" in plan["colors"]
    assert plan["theme"] == "dark"


def test_design_receipt_and_css_for_buttons_glow() -> None:
    prompt = "Make the buttons glow."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()
    css = apply_design_intent_to_css(_design_css_fixture(), mods).lower()

    assert intent["glow"] is True
    assert mods["button_glow"] is True
    assert "glow: medium" in receipt
    assert "button, .button, [role='button']" in css


def test_design_receipt_and_css_for_hero_pop() -> None:
    prompt = "Make the hero pop."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()
    css = apply_design_intent_to_css(_design_css_fixture(), mods).lower()

    assert intent["glow"] is True
    assert mods["hero_glow"] is True
    assert "glow: medium" in receipt
    assert ".hero-section, .hero-card" in css


def test_design_receipts_remain_concrete_not_vague() -> None:
    prompt = "Make the cards translucent and add a red glow."
    intent = DesignIntentInterpreter.extract_design_intent(prompt)
    mods = DesignIntentInterpreter.build_css_modifications(intent)
    receipt = DesignIntentInterpreter.build_design_change_receipt(intent, mods).lower()

    assert "made it better" not in receipt
    assert "updated site styling:" in receipt
