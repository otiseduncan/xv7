import json

from core.brain.website_bundle_assembly_manager import WebsiteBundleAssemblyManager


def test_single_page_bundle() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(pages=["index"])

    assert payload["entrypoint"] == "index.html"
    assert payload["html_files"] == ["index.html"]
    assert payload["asset_files"] == [
        "assets/css/styles.css",
        "assets/js/main.js",
    ]


def test_multi_page_bundle() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(
        pages=["home", "about us", "contact"]
    )

    assert payload["html_files"] == [
        "index.html",
        "pages/about-us.html",
        "pages/contact.html",
    ]
    assert payload["page_routes"] == [
        {"slug": "index", "path": "index.html", "route": "/"},
        {"slug": "about-us", "path": "pages/about-us.html", "route": "/about-us"},
        {"slug": "contact", "path": "pages/contact.html", "route": "/contact"},
    ]


def test_safe_path_normalization_uses_posix_style() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(
        pages=["index"],
        asset_files=[r"assets\images\hero.png"],
    )

    assert "assets/images/hero.png" in payload["asset_files"]
    assert all("\\" not in item["path"] for item in payload["files"])


def test_rejects_traversal_paths() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(
        pages=["index"],
        asset_files=["../secrets.env", "assets/images/hero.png"],
    )

    assert "../secrets.env" not in payload["asset_files"]
    assert "assets/images/hero.png" in payload["asset_files"]
    assert payload["warnings"] == ["unsafe traversal path skipped: ../secrets.env"]


def test_dedupes_repeated_files() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(
        pages=["index", "home"],
        asset_files=["assets/css/styles.css", "assets/css/styles.css"],
    )

    paths = [item["path"] for item in payload["files"]]
    assert paths.count("index.html") == 1
    assert paths.count("assets/css/styles.css") == 1


def test_stable_entrypoint_when_pages_omit_home() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(pages=["about", "contact"])

    assert payload["entrypoint"] == "index.html"
    assert payload["html_files"][0] == "index.html"


def test_asset_classification_for_images_and_fonts() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(
        pages=["index"],
        image_assets=["assets/images/hero.webp"],
        font_assets=["assets/fonts/site.woff2"],
    )

    assert "assets/images/hero.webp" in payload["asset_files"]
    assert "assets/fonts/site.woff2" in payload["asset_files"]
    assert all(
        item["kind"] == "asset"
        for item in payload["files"]
        if item["path"].startswith("assets/")
    )


def test_json_safe_payload() -> None:
    payload = WebsiteBundleAssemblyManager.plan_bundle(
        pages=["index", "faq"],
        content_files=["pages/faq.html"],
        asset_files=["assets/images/logo.svg"],
    )

    assert json.loads(json.dumps(payload)) == payload
