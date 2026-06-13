from core.brain.website_project_name_manager import WebsiteProjectNameManager


def test_extract_project_name_from_for_prompt() -> None:
    prompt = "Build a website for Harry's Hot Dog Cart with a menu and red buttons."

    assert WebsiteProjectNameManager.extract_project_name(prompt) == "Harry's Hot Dog Cart"


def test_extract_project_name_prefers_quoted_name() -> None:
    prompt = 'Create a site called "The Ville Nutrition" with green and white colors.'

    assert WebsiteProjectNameManager.extract_project_name(prompt) == "The Ville Nutrition"


def test_extract_project_name_from_named_prompt() -> None:
    prompt = "Generate a website named Smoky Joe's Vape and CBD featuring a gallery."

    assert WebsiteProjectNameManager.extract_project_name(prompt) == "Smoky Joe's Vape and CBD"


def test_normalize_display_name_removes_generic_request_prefix() -> None:
    assert (
        WebsiteProjectNameManager.normalize_display_name("Build me a website for Apex ADAS.")
        == "Apex ADAS"
    )


def test_normalize_display_name_uses_fallback_for_empty_or_generic() -> None:
    assert WebsiteProjectNameManager.normalize_display_name("") == "Website"
    assert WebsiteProjectNameManager.normalize_display_name("website") == "Website"


def test_slugify_project_name_removes_apostrophes_and_symbols() -> None:
    assert WebsiteProjectNameManager.slugify_project_name("Harry's Hot Dog Cart!") == "harrys-hot-dog-cart"


def test_slugify_project_name_handles_curly_apostrophes() -> None:
    assert WebsiteProjectNameManager.slugify_project_name("Ubi’s RC Lab") == "ubis-rc-lab"


def test_safe_folder_name_avoids_reserved_windows_names() -> None:
    assert WebsiteProjectNameManager.safe_folder_name("CON") == "project-con"
    assert WebsiteProjectNameManager.safe_folder_name("LPT1") == "project-lpt1"


def test_slugify_project_name_limits_length() -> None:
    long_name = "A" * 120

    assert len(WebsiteProjectNameManager.slugify_project_name(long_name)) <= 64


def test_build_project_name_payload_is_json_safe() -> None:
    payload = WebsiteProjectNameManager.build_project_name_payload(
        "Build a site for Ecclesia Koinonia with sermon pages."
    )

    assert payload == {
        "display_name": "Ecclesia Koinonia",
        "slug": "ecclesia-koinonia",
        "folder_name": "ecclesia-koinonia",
    }
