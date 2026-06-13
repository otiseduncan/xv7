from __future__ import annotations

from core.brain.website_seo_plan_manager import WebsiteSeoPlanManager


def test_clean_text_normalizes_whitespace_and_non_strings() -> None:
    assert (
        WebsiteSeoPlanManager.clean_text("  Harry's   Hot   Dogs  ")
        == "Harry's Hot Dogs"
    )
    assert WebsiteSeoPlanManager.clean_text(None) == ""


def test_truncate_keeps_word_boundaries() -> None:
    value = "This is a very long description that should not split the final word"

    assert WebsiteSeoPlanManager.truncate(value, 28) == "This is a very long"


def test_extract_title_prefers_business_name() -> None:
    prompt = 'Build a website called "Something Else".'

    assert WebsiteSeoPlanManager.extract_title(prompt, "Syfernetics") == "Syfernetics"


def test_extract_title_uses_quoted_name() -> None:
    prompt = 'Build a website for "Harry\'s Hot Dog Cart" with a menu page.'

    assert WebsiteSeoPlanManager.extract_title(prompt) == "Harry's Hot Dog Cart"


def test_extract_title_from_for_phrase() -> None:
    prompt = "Build a website for Smoky Joe's Vape and CBD with dark colors."

    assert WebsiteSeoPlanManager.extract_title(prompt) == "Smoky Joe's Vape"


def test_extract_meta_description_uses_explicit_description() -> None:
    prompt = "Meta description: Fast ADAS calibration and diagnostics for body shops."

    assert (
        WebsiteSeoPlanManager.extract_meta_description(prompt)
        == "Fast ADAS calibration and diagnostics for body shops"
    )


def test_extract_meta_description_infers_from_title() -> None:
    assert (
        WebsiteSeoPlanManager.extract_meta_description("Build a site", "Syfernetics")
        == "Explore Syfernetics services, highlights, and contact details."
    )


def test_extract_keywords_from_explicit_prompt() -> None:
    prompt = "Keywords: ADAS, calibration, diagnostics and body shop."

    assert WebsiteSeoPlanManager.extract_keywords(prompt)[:4] == [
        "adas",
        "calibration",
        "diagnostics",
        "body shop",
    ]


def test_extract_keywords_adds_context_and_defaults() -> None:
    prompt = "Build a cybersecurity website for Syfernetics."

    keywords = WebsiteSeoPlanManager.extract_keywords(prompt, "Syfernetics")

    assert "syfernetics" in keywords
    assert "cybersecurity" in keywords
    assert "website" in keywords


def test_build_plan_returns_json_safe_payload() -> None:
    plan = WebsiteSeoPlanManager.build_plan(
        "Build a restaurant website. Keywords: burgers, catering.",
        "Harry's Cart",
    )

    assert plan == {
        "title": "Harry's Cart",
        "description": "Explore Harry's Cart services, highlights, and contact details.",
        "keywords": [
            "burgers",
            "catering",
            "harry's",
            "cart",
            "restaurant",
            "menu",
            "food",
            "website",
            "services",
            "contact",
        ],
        "robots": "index, follow",
        "source": "website_seo_plan_manager",
    }
