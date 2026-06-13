from core.brain.website_cta_plan_manager import WebsiteCallToActionManager


def test_normalize_label_title_cases_and_preserves_acronyms() -> None:
    assert (
        WebsiteCallToActionManager.normalize_label("request-quote") == "Request Quote"
    )
    assert WebsiteCallToActionManager.normalize_label("adas service") == "ADAS Service"
    assert WebsiteCallToActionManager.normalize_label("") == "Contact Us"


def test_slug_for_label_is_stable() -> None:
    assert WebsiteCallToActionManager.slug_for_label("Request Quote") == "request-quote"
    assert WebsiteCallToActionManager.slug_for_label("  Book Now! ") == "book-now"


def test_extract_requested_labels_requires_cta_context() -> None:
    prompt = "People can book online and contact the shop later."

    assert WebsiteCallToActionManager.extract_requested_labels(prompt) == []


def test_extract_requested_labels_from_button_request() -> None:
    prompt = "Add buttons for Book Now, Order Online, and Contact Us."

    assert WebsiteCallToActionManager.extract_requested_labels(prompt) == [
        "Book Now",
        "Contact Us",
        "Order Online",
    ]


def test_extract_requested_labels_dedupes_aliases() -> None:
    prompt = "Use CTA buttons for contact, get in touch, and request quote."

    assert WebsiteCallToActionManager.extract_requested_labels(prompt) == [
        "Contact Us",
        "Request Quote",
    ]


def test_infer_profile_from_prompt() -> None:
    assert WebsiteCallToActionManager.infer_profile("Harry's hot dog cart") == "food"
    assert (
        WebsiteCallToActionManager.infer_profile("ADAS calibration website") == "auto"
    )
    assert WebsiteCallToActionManager.infer_profile("Bible study ministry") == "church"
    assert WebsiteCallToActionManager.infer_profile("Network security firm") == "cyber"
    assert WebsiteCallToActionManager.infer_profile("General landing page") == "default"


def test_infer_default_labels_for_food_cart() -> None:
    assert WebsiteCallToActionManager.infer_default_labels("hot dog food cart") == [
        "View Menu",
        "Order Catering",
        "Get Directions",
    ]


def test_href_for_common_labels() -> None:
    assert WebsiteCallToActionManager.href_for_label("Call Now") == "tel:+10000000000"
    assert WebsiteCallToActionManager.href_for_label("Contact Us") == "#contact"
    assert WebsiteCallToActionManager.href_for_label("Get Directions") == "#location"
    assert WebsiteCallToActionManager.href_for_label("Donate") == "#giving"


def test_build_cta_plan_uses_requested_actions() -> None:
    payload = WebsiteCallToActionManager.build_cta_plan(
        "Add CTA buttons for call now and request quote.",
        business_type="auto",
    )

    assert payload == {
        "profile": "auto",
        "source": "requested",
        "actions": [
            {
                "label": "Call Now",
                "slug": "call-now",
                "href": "tel:+10000000000",
                "source": "requested",
            },
            {
                "label": "Request Quote",
                "slug": "request-quote",
                "href": "#contact",
                "source": "requested",
            },
        ],
    }


def test_build_cta_plan_falls_back_to_profile_defaults() -> None:
    payload = WebsiteCallToActionManager.build_cta_plan("Build a vape and CBD site")

    assert payload["profile"] == "vape"
    assert payload["source"] == "inferred"
    assert [action["label"] for action in payload["actions"]] == [
        "Shop Now",
        "Get Directions",
        "Contact Us",
    ]
