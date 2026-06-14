from core.brain.website_page_plan_manager import (
    WebsitePagePlan,
    WebsitePagePlanManager,
)


def test_normalize_title_cleans_spacing_and_case() -> None:
    assert WebsitePagePlanManager.normalize_title("  guided   tours ") == "Guided Tours"
    assert WebsitePagePlanManager.normalize_title("after-care") == "After Care"
    assert WebsitePagePlanManager.normalize_title("") == "Home"


def test_page_slug_normalizes_symbols() -> None:
    assert WebsitePagePlanManager.page_slug("Guided Tours") == "guided-tours"
    assert WebsitePagePlanManager.page_slug("Reviews & Pricing") == "reviews-pricing"
    assert WebsitePagePlanManager.page_slug(None) == "home"


def test_page_path_uses_index_for_home() -> None:
    assert WebsitePagePlanManager.page_path("Home") == "index.html"
    assert WebsitePagePlanManager.page_path("Menu") == "menu.html"


def test_is_multipage_request_detects_common_phrases() -> None:
    assert WebsitePagePlanManager.is_multipage_request("Build a multi-page site")
    assert WebsitePagePlanManager.is_multipage_request("Make a full site")
    assert not WebsitePagePlanManager.is_multipage_request("Make a quick landing page")


def test_extract_requested_titles_always_includes_home() -> None:
    assert WebsitePagePlanManager.extract_requested_titles("one page site") == ["Home"]


def test_extract_requested_titles_detects_known_common_pages() -> None:
    prompt = "Build a site with menu, specials, catering, reviews, and contact."

    assert WebsitePagePlanManager.extract_requested_titles(prompt) == [
        "Home",
        "Menu",
        "Specials",
        "Catering",
        "Reviews",
        "Contact",
    ]


def test_extract_requested_titles_detects_pr29_page_terms() -> None:
    prompt = (
        "Make pages for pricing, portfolio, booking, aftercare, rentals, "
        "safety, locations, and guided tours."
    )

    assert WebsitePagePlanManager.extract_requested_titles(prompt) == [
        "Home",
        "Locations",
        "Pricing",
        "Portfolio",
        "Booking",
        "Aftercare",
        "Rentals",
        "Safety",
        "Guided Tours",
    ]


def test_extract_requested_titles_dedupes_aliases() -> None:
    prompt = "Add contact and contact us plus prices and pricing."

    assert WebsitePagePlanManager.extract_requested_titles(prompt) == [
        "Home",
        "Pricing",
        "Contact",
    ]


def test_alias_matching_does_not_match_inside_words() -> None:
    prompt = "A bookkeeper reviews vehicles at a safehouse."

    assert WebsitePagePlanManager.extract_requested_titles(prompt) == ["Home"]


def test_build_page_plan_returns_dataclass_entries() -> None:
    plan = WebsitePagePlanManager.build_page_plan("Menu and contact pages")

    assert plan == [
        WebsitePagePlan(title="Home", path="index.html", source="default"),
        WebsitePagePlan(title="Menu", path="menu.html", source="prompt"),
        WebsitePagePlan(title="Contact", path="contact.html", source="prompt"),
    ]


def test_build_manifest_pages_returns_json_safe_dicts() -> None:
    assert WebsitePagePlanManager.build_manifest_pages("reviews and guided tours") == [
        {"title": "Home", "path": "index.html", "source": "default"},
        {"title": "Reviews", "path": "reviews.html", "source": "prompt"},
        {
            "title": "Guided Tours",
            "path": "guided-tours.html",
            "source": "prompt",
        },
    ]
