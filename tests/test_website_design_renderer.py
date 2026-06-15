from __future__ import annotations

from core.brain import site_bundle as sb
from core.brain.website_design_renderer import build_site_design_spec


def _bundle_by_path(
    *,
    business_name: str = "Harry's Hot Dog Cart",
    question: str,
    colors: list[str] | None = None,
    styles: list[str] | None = None,
) -> dict[str, str]:
    files = sb.build_bundle_files(
        business_name=business_name,
        slug="harrys-hot-dog-cart",
        pages=[
            "index.html",
            "menu.html",
            "specials.html",
            "contact.html",
            "assets/site.css",
            "assets/site.js",
        ],
        style_hints={
            "colors": colors or ["black", "gold", "white", "red"],
            "styles": styles or ["premium", "fun"],
        },
        question=question,
    )
    return {item["path"]: item["content"] for item in files}


def test_site_bundle_renderer_replaces_generic_template_copy() -> None:
    by_path = _bundle_by_path(
        question=(
            "Build a multi-page website for Harry's Hot Dog Cart with menu, "
            "specials, catering, and contact. Use black, gold, white, and red."
        )
    )

    home = by_path["index.html"]
    menu = by_path["menu.html"]
    specials = by_path["specials.html"]
    css = by_path["assets/site.css"]

    assert "Harry's Hot Dog Cart" in home
    assert "hero-section" in home
    assert "proof-strip" in home
    assert "premier destination for an unforgettable experience" not in home.lower()
    assert "Classic Street Dog" in menu
    assert "Loaded Chili Dog Special" in specials
    assert "--requested-1: black;" in css
    assert "--requested-2: gold;" in css
    assert "site-header" in css


def test_site_bundle_renderer_makes_premium_revision_visibly_different() -> None:
    by_path = _bundle_by_path(
        question=(
            "Make this site look more premium, less template-looking, give the "
            "hero stronger hierarchy, make the buttons pop, and add a Friday "
            "Chili Dog special."
        ),
        colors=["#050505", "#f59e0b", "#ffffff"],
        styles=["premium", "bold"],
    )

    home = by_path["index.html"]
    menu = by_path["menu.html"]
    specials = by_path["specials.html"]
    css = by_path["assets/site.css"]

    assert 'class="xv7-site is-premium is-bold"' in home
    assert "Premium revision applied" in home
    assert "Not a blank template" in home
    assert "Friday Chili Dog Special" in home
    assert "Friday Chili Dog Special" in menu
    assert "Friday Chili Dog Special" in specials
    assert "--button-scale: 1.08;" in css
    assert ".is-premium .hero-card" in css
    assert ".is-bold h1" in css


def test_site_bundle_validation_requires_requested_colors_in_css() -> None:
    files = sb.build_bundle_files(
        business_name="Smoky Joe's Vape and CBD",
        slug="smoky-joes-vape-and-cbd",
        pages=["index.html", "products.html", "faq.html", "assets/site.css"],
        style_hints={
            "colors": ["black", "green", "white"],
            "styles": ["dark", "premium"],
        },
        question="Build a multi-page website with products and FAQ pages.",
    )

    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="Smoky Joe's Vape and CBD",
        style_hints={
            "colors": ["black", "green", "white"],
            "styles": ["dark", "premium"],
        },
    )

    assert passed, failures


def test_site_bundle_quality_gate_rejects_generic_duplicate_templates() -> None:
    generic_html = (
        "<!doctype html><html><body><header>Harry's Hot Dog Cart</header>"
        "<main>Harry's Hot Dog Cart is your premier destination for an "
        "unforgettable experience.</main></body></html>"
    )
    files = [
        {"path": "index.html", "language": "html", "content": generic_html},
        {"path": "menu.html", "language": "html", "content": generic_html},
        {"path": "assets/site.css", "language": "css", "content": "body{color:black;}"},
    ]

    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="Harry's Hot Dog Cart",
        style_hints={"colors": ["gold"], "styles": []},
    )

    assert not passed
    joined = " | ".join(failures)
    assert "generic template copy" in joined
    assert "html pages must not be duplicate template copies" in joined
    assert "css quality marker missing" in joined
    assert "requested color missing from css" in joined


def test_hot_dog_cart_design_spec_is_business_specific_and_color_compliant() -> None:
    spec = build_site_design_spec(
        business_name="Harry's Hot Dog Cart",
        slug="harrys-hot-dog-cart",
        pages=[
            "index.html",
            "menu.html",
            "specials.html",
            "contact.html",
            "assets/site.css",
        ],
        style_hints={"colors": ["red", "yellow"], "styles": ["fun"]},
        question="generate a website for Harry's Hot Dog Cart, bright red and yellow, fun street-food style",
    )

    assert spec.business_type == "food"
    assert spec.tone == "fun street-food"
    assert spec.layout_variant == "street-poster"
    assert spec.cta_strategy.primary == "Order catering"
    assert "Classic Street Dog" in [item.title for item in spec.content_blocks]
    assert spec.palette.requested_colors == ("red", "yellow")


def test_representative_business_prompts_have_distinct_copy_and_sections() -> None:
    cases = [
        (
            "Smoky Joe's Vape and CBD",
            "generate a website for Smoky Joe's Vape and CBD, dark smoky premium retail style",
            "retail",
            ("Age-aware shopping", "Visit the shop"),
        ),
        (
            "The Ville Nutrition",
            "generate a website for The Ville Nutrition, bright healthy smoothie nutrition shop style",
            "nutrition",
            ("Smoothie menu", "View smoothie menu"),
        ),
        (
            "Syfernetics",
            "generate a website for Syfernetics, cybersecurity AI professional style",
            "cyber",
            ("Security assessment", "Request assessment"),
        ),
    ]

    rendered_home_pages: list[str] = []
    for business_name, prompt, expected_type, expected_copy in cases:
        files = sb.build_bundle_files(
            business_name=business_name,
            slug=business_name.lower().replace(" ", "-"),
            pages=["index.html", "services.html", "products.html", "assets/site.css"],
            style_hints={"colors": [], "styles": []},
            question=prompt,
        )
        home = next(item["content"] for item in files if item["path"] == "index.html")
        joined = "\n".join(item["content"] for item in files)
        spec = build_site_design_spec(
            business_name=business_name,
            slug=business_name.lower().replace(" ", "-"),
            pages=["index.html", "services.html", "products.html", "assets/site.css"],
            style_hints={"colors": [], "styles": []},
            question=prompt,
        )

        assert spec.business_type == expected_type
        for phrase in expected_copy:
            assert phrase in joined
        assert "Your Business" not in joined
        assert "Lorem ipsum" not in joined
        rendered_home_pages.append(home)

    assert len(set(rendered_home_pages)) == len(rendered_home_pages)
