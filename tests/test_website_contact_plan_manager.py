from __future__ import annotations

from core.brain.website_contact_plan_manager import WebsiteContactPlanManager


def test_extract_emails_dedupes_case_insensitively() -> None:
    prompt = "Email OTIS@EXAMPLE.COM or otis@example.com and support@example.com."

    assert WebsiteContactPlanManager.extract_emails(prompt) == [
        "OTIS@EXAMPLE.COM",
        "support@example.com",
    ]


def test_extract_phone_numbers_normalizes_us_numbers() -> None:
    prompt = "Call 478-555-1212, (478) 555-1212, or +1 404.555.2020."

    assert WebsiteContactPlanManager.extract_phone_numbers(prompt) == [
        "(478) 555-1212",
        "(404) 555-2020",
    ]


def test_normalize_phone_number_leaves_invalid_values_alone() -> None:
    assert WebsiteContactPlanManager.normalize_phone_number("555") == "555"


def test_contact_hints_detect_address_form_and_social_links() -> None:
    prompt = "Add our location, a booking form, Facebook, and Instagram."

    assert WebsiteContactPlanManager.has_address_hint(prompt) is True
    assert WebsiteContactPlanManager.wants_contact_form(prompt) is True
    assert WebsiteContactPlanManager.wants_social_links(prompt) is True


def test_contact_hints_ignore_unrelated_words() -> None:
    prompt = "The office team forms a plan for social progress."

    assert WebsiteContactPlanManager.has_address_hint(prompt) is False
    assert WebsiteContactPlanManager.wants_contact_form(prompt) is False
    assert WebsiteContactPlanManager.wants_social_links(prompt) is False


def test_build_mailto_and_tel_links() -> None:
    assert WebsiteContactPlanManager.build_mailto(" hello@example.com ") == "mailto:hello@example.com"
    assert WebsiteContactPlanManager.build_tel("(478) 555-1212") == "tel:+14785551212"
    assert WebsiteContactPlanManager.build_tel("555") == "#contact"


def test_infer_contact_methods_defaults_when_no_contact_details_exist() -> None:
    assert WebsiteContactPlanManager.infer_contact_methods("Build a clean website.") == [
        "contact"
    ]


def test_infer_contact_methods_preserves_stable_order() -> None:
    prompt = "Call 478-555-1212, email info@example.com, add location and contact form."

    assert WebsiteContactPlanManager.infer_contact_methods(prompt) == [
        "email",
        "phone",
        "address",
        "form",
    ]


def test_build_plan_returns_json_safe_contact_payload() -> None:
    plan = WebsiteContactPlanManager.build_plan(
        "Smoky Joe's site with info@smoky.example, 478-555-1212, address, and social links."
    )

    assert plan == {
        "emails": ["info@smoky.example"],
        "phone_numbers": ["(478) 555-1212"],
        "primary_email": "info@smoky.example",
        "primary_phone": "(478) 555-1212",
        "mailto": "mailto:info@smoky.example",
        "tel": "tel:+14785551212",
        "has_address_hint": True,
        "wants_contact_form": False,
        "wants_social_links": True,
        "methods": ["email", "phone", "address", "social"],
    }
