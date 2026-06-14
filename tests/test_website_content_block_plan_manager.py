import json

from core.brain.website_content_block_plan_manager import (
    WebsiteContentBlockPlanManager,
)


def _kinds(prompt: str) -> list[str]:
    payload = WebsiteContentBlockPlanManager.build_content_block_plan(prompt)
    return [block["kind"] for block in payload["blocks"]]


def test_food_cart_prompt_infers_menu_blocks() -> None:
    assert _kinds("Build a hot dog food cart website with a menu") == [
        "hero",
        "menu",
        "specials",
        "hours",
        "contact",
    ]


def test_automotive_adas_prompt_infers_service_blocks() -> None:
    assert _kinds("ADAS calibration and automotive diagnostics website") == [
        "hero",
        "services",
        "process",
        "diagnostics",
        "contact",
    ]


def test_church_ministry_prompt_infers_ministry_blocks() -> None:
    assert _kinds("Church ministry website for sermons and Bible study") == [
        "hero",
        "sermons",
        "bible_study",
        "events",
        "contact",
    ]


def test_cyber_it_prompt_infers_security_blocks() -> None:
    assert _kinds("Cyber security and IT services website") == [
        "hero",
        "services",
        "trust_security",
        "contact",
    ]


def test_explicit_section_ordering_is_preserved() -> None:
    payload = WebsiteContentBlockPlanManager.build_content_block_plan(
        "Build a website.",
        requested_blocks=["hero", "faq", "contact", "services"],
    )

    assert [block["kind"] for block in payload["blocks"]] == [
        "hero",
        "faq",
        "contact",
        "services",
    ]
    assert {block["source"] for block in payload["blocks"]} == {"requested"}


def test_dedupe_behavior_preserves_first_occurrence() -> None:
    payload = WebsiteContentBlockPlanManager.build_content_block_plan(
        "Include sections for hero, menu, food menu, contact and get in touch.",
        requested_blocks=["hero", "menu", "contact"],
    )

    assert [block["kind"] for block in payload["blocks"]] == [
        "hero",
        "menu",
        "contact",
    ]


def test_slug_id_stability() -> None:
    payload = WebsiteContentBlockPlanManager.build_content_block_plan(
        "Build a site.",
        requested_blocks=["call to action", "FAQ"],
    )

    assert payload["blocks"] == [
        {
            "id": "block-01-call-to-action",
            "slug": "call-to-action",
            "kind": "call_to_action",
            "label": "Call To Action",
            "source": "requested",
        },
        {
            "id": "block-02-faq",
            "slug": "faq",
            "kind": "faq",
            "label": "FAQ",
            "source": "requested",
        },
    ]


def test_json_safe_output() -> None:
    payload = WebsiteContentBlockPlanManager.build_content_block_plan(
        "Build a vape and CBD site"
    )

    assert json.loads(json.dumps(payload)) == payload


def test_unrelated_prompt_does_not_over_infer_aggressively() -> None:
    payload = WebsiteContentBlockPlanManager.build_content_block_plan(
        "Write a short note about our plans."
    )

    assert payload["profile"] == "default"
    assert [block["kind"] for block in payload["blocks"]] == [
        "hero",
        "intro",
        "contact",
    ]
