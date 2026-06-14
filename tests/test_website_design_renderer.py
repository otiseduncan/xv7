from __future__ import annotations

from core.brain import site_bundle as sb


def test_site_bundle_renderer_replaces_generic_template_copy() -> None:
    pages = [
        "index.html",
        "menu.html",
        "specials.html",
        "contact.html",
        "assets/site.css",
        "assets/site.js",
    ]

    files = sb.build_bundle_files(
        business_name="Harry's Hot Dog Cart",
        slug="harrys-hot-dog-cart",
        pages=pages,
        style_hints={"colors": ["black", "gold", "white", "red"], "styles": ["premium", "fun"]},
        question=(
            "Build a multi-page website for Harry's Hot Dog Cart with menu, "
            "specials, catering, and contact. Use black, gold, white, and red."
        ),
    )

    by_path = {item["path"]: item["content"] for item in files}
    home = by_path["index.html"]
    menu = by_path["menu.html"]
    specials = by_path["specials.html"]
    css = by_path["assets/site.css"]

    assert "Harry's Hot Dog Cart" in home
    assert "hero-section" in home
    assert "proof-strip" in home
    assert "premier destination for an unforgettable experience" not in home.lower()
    assert "Classic Street Dog" in menu
    assert "Friday Chili Dog" in specials
    assert "--requested-1: black;" in css
    assert "--requested-2: gold;" in css
    assert "site-header" in css


def test_site_bundle_validation_requires_requested_colors_in_css() -> None:
    files = sb.build_bundle_files(
        business_name="Smoky Joe's Vape and CBD",
        slug="smoky-joes-vape-and-cbd",
        pages=["index.html", "products.html", "faq.html", "assets/site.css"],
        style_hints={"colors": ["black", "green", "white"], "styles": ["dark", "premium"]},
        question="Build a multi-page website with products and FAQ pages.",
    )

    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="Smoky Joe's Vape and CBD",
        style_hints={"colors": ["black", "green", "white"], "styles": ["dark", "premium"]},
    )

    assert passed, failures
