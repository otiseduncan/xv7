from core.brain.website_asset_reference_manager import (
    AssetReference,
    WebsiteAssetReferenceManager,
)


def test_normalize_asset_path_removes_root_and_dot_prefixes() -> None:
    assert WebsiteAssetReferenceManager.normalize_asset_path(r"/assets\\site.css") == "assets/site.css"
    assert WebsiteAssetReferenceManager.normalize_asset_path("./assets/site.js") == "assets/site.js"


def test_remote_reference_detection_covers_common_remote_forms() -> None:
    assert WebsiteAssetReferenceManager.is_remote_reference("https://cdn.example/site.css")
    assert WebsiteAssetReferenceManager.is_remote_reference("//cdn.example/site.css")
    assert WebsiteAssetReferenceManager.is_remote_reference("data:image/png;base64,abc")
    assert WebsiteAssetReferenceManager.is_remote_reference("javascript:alert(1)")
    assert not WebsiteAssetReferenceManager.is_remote_reference("assets/site.css")


def test_safe_local_reference_rejects_empty_remote_and_traversal() -> None:
    assert WebsiteAssetReferenceManager.is_safe_local_reference("assets/site.css")
    assert not WebsiteAssetReferenceManager.is_safe_local_reference("")
    assert not WebsiteAssetReferenceManager.is_safe_local_reference("https://cdn.example/site.css")
    assert not WebsiteAssetReferenceManager.is_safe_local_reference("../secrets.txt")
    assert not WebsiteAssetReferenceManager.is_safe_local_reference("assets/../secret.txt")


def test_extension_for_path_is_lowercase_and_handles_missing_extension() -> None:
    assert WebsiteAssetReferenceManager.extension_for_path("assets/SITE.CSS") == ".css"
    assert WebsiteAssetReferenceManager.extension_for_path("assets/site") == ""


def test_classify_asset_by_extension() -> None:
    assert WebsiteAssetReferenceManager.classify_asset("assets/site.css") == "stylesheet"
    assert WebsiteAssetReferenceManager.classify_asset("assets/site.js") == "script"
    assert WebsiteAssetReferenceManager.classify_asset("assets/logo.svg") == "image"
    assert WebsiteAssetReferenceManager.classify_asset("assets/font.woff2") == "font"
    assert WebsiteAssetReferenceManager.classify_asset("assets/data.json") == "asset"


def test_make_reference_returns_model_for_safe_local_asset() -> None:
    reference = WebsiteAssetReferenceManager.make_reference("/assets/logo.PNG")

    assert reference == AssetReference(
        path="assets/logo.PNG",
        kind="image",
        extension=".png",
    )


def test_make_reference_rejects_unsafe_asset() -> None:
    assert WebsiteAssetReferenceManager.make_reference("https://cdn.example/logo.png") is None
    assert WebsiteAssetReferenceManager.make_reference("../logo.png") is None


def test_asset_href_uses_assets_folder_and_filename_only() -> None:
    assert WebsiteAssetReferenceManager.asset_href("site.css") == "assets/site.css"
    assert WebsiteAssetReferenceManager.asset_href("nested/site.css") == "assets/site.css"
    assert WebsiteAssetReferenceManager.asset_href("site.css", folder="./public/assets") == "public/assets/site.css"


def test_stylesheet_and_script_tags_are_bundle_relative() -> None:
    assert (
        WebsiteAssetReferenceManager.stylesheet_link("/assets/site.css")
        == '<link rel="stylesheet" href="assets/site.css">'
    )
    assert (
        WebsiteAssetReferenceManager.script_tag("/assets/site.js")
        == '<script src="assets/site.js" defer></script>'
    )
    assert (
        WebsiteAssetReferenceManager.script_tag("assets/site.js", defer=False)
        == '<script src="assets/site.js"></script>'
    )


def test_rewrite_bundle_relative_references_removes_root_prefixes() -> None:
    html = '<link href="/assets/site.css"><script src="./assets/site.js"></script>'

    assert WebsiteAssetReferenceManager.rewrite_bundle_relative_references(html) == (
        '<link href="assets/site.css"><script src="assets/site.js"></script>'
    )


def test_collect_remote_references_from_html_attrs() -> None:
    html = """
    <link href="https://cdn.example/site.css">
    <script src='//cdn.example/site.js'></script>
    <img src="assets/logo.svg">
    """

    assert WebsiteAssetReferenceManager.collect_remote_references(html) == [
        "https://cdn.example/site.css",
        "//cdn.example/site.js",
    ]
