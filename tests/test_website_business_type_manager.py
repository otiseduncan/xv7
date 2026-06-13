from core.brain.website_business_type_manager import WebsiteBusinessTypeManager


def test_detect_hints_returns_unique_matches_in_priority_order() -> None:
    prompt = "Build Harry's hot dog food cart site with a menu and catering."

    assert WebsiteBusinessTypeManager.detect_hints(prompt) == [
        "hot dog",
        "food cart",
        "menu",
        "catering",
    ]


def test_infer_food_cart_before_restaurant_for_hot_dog_cart() -> None:
    result = WebsiteBusinessTypeManager.infer_business_type(
        "Create a site for Harry's Hot Dog Cart with a menu page."
    )

    assert result.kind == "food_cart"
    assert result.label == "Food cart"
    assert result.confidence == "medium"
    assert result.matched_hints == ("hot dog",)


def test_infer_vape_cbd_business() -> None:
    result = WebsiteBusinessTypeManager.infer_business_type(
        "Build Smoky Joe's Vape and CBD website."
    )

    assert result.kind == "vape_cbd"
    assert result.confidence == "high"
    assert result.matched_hints == ("vape", "cbd")


def test_infer_automotive_adas_business() -> None:
    result = WebsiteBusinessTypeManager.infer_business_type(
        "ADAS calibration and diagnostics for body shops."
    )

    assert result.kind == "automotive_adas"
    assert result.label == "Automotive ADAS service"
    assert result.confidence == "high"


def test_infer_church_ministry_business() -> None:
    result = WebsiteBusinessTypeManager.infer_business_type(
        "A church ministry site for sermons and Bible study."
    )

    assert result.kind == "church_ministry"
    assert result.matched_hints == ("church", "ministry", "bible", "sermon")


def test_infer_cybersecurity_it_business() -> None:
    result = WebsiteBusinessTypeManager.infer_business_type(
        "Cybersecurity and network security automation services."
    )

    assert result.kind == "cybersecurity_it"
    assert result.confidence == "high"


def test_general_business_fallback_for_unknown_prompt() -> None:
    result = WebsiteBusinessTypeManager.infer_business_type(
        "Build a clean modern landing page."
    )

    assert result.kind == "general_business"
    assert result.label == "General business"
    assert result.confidence == "low"
    assert result.matched_hints == ()


def test_build_business_type_payload_is_json_safe() -> None:
    payload = WebsiteBusinessTypeManager.build_business_type_payload(
        "Retail shop with products and inventory."
    )

    assert payload == {
        "kind": "retail",
        "label": "Retail business",
        "confidence": "high",
        "matched_hints": ["shop", "retail", "products", "inventory"],
    }
