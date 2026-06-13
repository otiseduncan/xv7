from core.brain.website_section_plan_manager import WebsiteSectionPlanManager


def test_normalize_section_title_maps_aliases_to_canonical_titles() -> None:
    assert WebsiteSectionPlanManager.normalize_section_title("our story") == "About"
    assert WebsiteSectionPlanManager.normalize_section_title("featured items") == "Menu Highlights"
    assert WebsiteSectionPlanManager.normalize_section_title("cta") == "Order / Catering CTA"


def test_slugify_section_creates_stable_anchor_slugs() -> None:
    assert WebsiteSectionPlanManager.slugify_section("Visit / Hours") == "visit-hours"
    assert WebsiteSectionPlanManager.slugify_section("Order & Catering CTA") == "order-and-catering-cta"
    assert WebsiteSectionPlanManager.slugify_section("") == "section"


def test_extract_requested_sections_uses_request_context() -> None:
    prompt = "Build a site with sections: hero, menu, specials, reviews, contact."

    assert WebsiteSectionPlanManager.extract_requested_sections(prompt) == [
        "Hero",
        "Menu Highlights",
        "Specials",
        "Reviews",
        "Contact",
    ]


def test_extract_requested_sections_does_not_match_ordinary_prose() -> None:
    prompt = "The owner reviews invoices and orders supplies after hours."

    assert WebsiteSectionPlanManager.extract_requested_sections(prompt) == ["Hero"]


def test_extract_requested_sections_allows_list_style_boundaries() -> None:
    prompt = "Hero, services, portfolio, contact"

    assert WebsitePagePlanTitles(prompt) == ["Hero", "Services", "Portfolio", "Contact"]


def test_infer_business_sections_for_hot_dog_cart() -> None:
    prompt = "Build a website for Harry's Hot Dog Cart."

    assert WebsiteSectionPlanManager.infer_business_sections(prompt) == [
        "Hero",
        "Menu Highlights",
        "Specials",
        "Visit / Hours",
        "Order / Catering CTA",
    ]


def test_infer_business_sections_for_automotive_service() -> None:
    prompt = "Create an ADAS calibration and diagnostic service website."

    assert WebsiteSectionPlanManager.infer_business_sections(prompt) == [
        "Hero",
        "Services",
        "Portfolio",
        "Reviews",
        "Contact",
    ]


def test_build_section_plan_uses_inferred_sections_without_explicit_request() -> None:
    plan = WebsiteSectionPlanManager.build_section_plan("Build a CBD vape shop website.")

    assert [section["title"] for section in plan] == [
        "Hero",
        "Products",
        "Specials",
        "Reviews",
        "Contact",
    ]
    assert plan[0] == {
        "title": "Hero",
        "slug": "hero",
        "anchor": "#hero",
        "kind": "hero",
        "source": "inferred",
    }


def test_build_section_plan_dedupes_and_prepends_hero() -> None:
    plan = WebsiteSectionPlanManager.build_section_plan(
        "Build a website.",
        requested_sections=["services", "Services", "booking", "contact"],
    )

    assert [section["title"] for section in plan] == [
        "Hero",
        "Services",
        "Booking",
        "Contact",
    ]
    assert [section["kind"] for section in plan] == [
        "hero",
        "content",
        "action",
        "contact",
    ]


def test_classify_section_groups_proof_contact_and_action_roles() -> None:
    assert WebsiteSectionPlanManager.classify_section("Reviews") == "proof"
    assert WebsiteSectionPlanManager.classify_section("Visit / Hours") == "contact"
    assert WebsiteSectionPlanManager.classify_section("Order / Catering CTA") == "action"
    assert WebsiteSectionPlanManager.classify_section("Services") == "content"


def WebsitePagePlanTitles(prompt: str) -> list[str]:
    return WebsiteSectionPlanManager.extract_requested_sections(prompt)
