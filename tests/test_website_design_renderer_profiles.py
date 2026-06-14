from __future__ import annotations

from core.brain.website_design_renderer import render_site_bundle_files


def _html(files: list[dict[str, str]], path: str = "index.html") -> str:
    return next(item["content"] for item in files if item["path"] == path)


def _css(files: list[dict[str, str]]) -> str:
    return next(item["content"] for item in files if item["path"] == "assets/site.css")


def test_automotive_adas_site_uses_technical_service_profile() -> None:
    files = render_site_bundle_files(
        business_name="Precision ADAS Calibration",
        slug="precision-adas-calibration",
        pages=["index.html", "services.html", "contact.html", "assets/site.css"],
        style_hints={"colors": ["black", "green", "white"], "styles": ["professional"]},
        question="Build a multi-page website for an ADAS calibration and diagnostics service.",
    )

    content = _html(files)
    assert "Precision automotive service" in content
    assert "ADAS-ready" in content
    assert "Calibration confidence" in content
    assert "OEM diagnostics" in _html(files, "services.html")


def test_church_ministry_site_uses_warm_visitor_profile() -> None:
    files = render_site_bundle_files(
        business_name="Smith Hill Bible Study",
        slug="smith-hill-bible-study",
        pages=["index.html", "events.html", "contact.html", "assets/site.css"],
        style_hints={"colors": ["white", "blue", "gold"], "styles": ["warm"]},
        question="Build a church ministry website with Bible teaching, events, fellowship, and contact.",
    )

    content = _html(files)
    assert "Faith community online" in content
    assert "Gather. Grow. Serve." in content
    assert "Visitor friendly" in content
    assert "Upcoming schedule" in _html(files, "events.html")


def test_cybersecurity_site_uses_assessment_and_monitoring_profile() -> None:
    files = render_site_bundle_files(
        business_name="Syfernetics",
        slug="syfernetics",
        pages=[
            "index.html",
            "services.html",
            "portfolio.html",
            "contact.html",
            "assets/site.css",
        ],
        style_hints={"colors": ["black", "green", "white"], "styles": ["futuristic"]},
        question="Build a cybersecurity IT service website with assessments, monitoring, automation, and consulting.",
    )

    content = _html(files)
    assert "Cybersecurity and automation" in content
    assert "Request assessment" in content
    assert "Monitoring focused" in content
    assert "Security assessment" in _html(files, "services.html")


def test_requested_colors_remain_visible_in_css_quality_markers() -> None:
    files = render_site_bundle_files(
        business_name="Harry's Hot Dog Cart",
        slug="harrys-hot-dog-cart",
        pages=["index.html", "menu.html", "specials.html", "assets/site.css"],
        style_hints={
            "colors": ["black", "gold", "white", "red"],
            "styles": ["premium"],
        },
        question="Make the site premium, less template-looking, and add a Friday Chili Dog Special.",
    )

    css = _css(files).lower()
    assert "requested-colors: black gold white red" in css
    assert "--bg:" in css
    assert "--accent:" in css
    assert "button-primary" in css
    assert "Friday Chili Dog Special" in _html(files)
    assert "Friday Chili Dog Special" in _html(files, "specials.html")
