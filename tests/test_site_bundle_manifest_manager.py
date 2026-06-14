from core.brain.site_bundle_manifest_manager import (
    SiteBundleManifest,
    SiteBundleManifestManager,
)


def test_normalize_path_cleans_backslashes_and_duplicate_slashes() -> None:
    assert (
        SiteBundleManifestManager.normalize_path(r"/generated-sites\\demo//index.html")
        == "generated-sites/demo/index.html"
    )


def test_unique_paths_preserves_order_and_drops_blanks() -> None:
    assert SiteBundleManifestManager.unique_paths(
        [
            "index.html",
            "",
            "assets/site.css",
            "index.html",
            None,
            "about.html",
        ]
    ) == ("index.html", "assets/site.css", "about.html")


def test_classify_paths_splits_html_assets_and_other_files() -> None:
    classified = SiteBundleManifestManager.classify_paths(
        [
            "index.html",
            "about.html",
            "assets/site.css",
            "assets/site.js",
            "README.md",
        ]
    )

    assert classified["html_pages"] == ("index.html", "about.html")
    assert classified["asset_files"] == ("assets/site.css", "assets/site.js")
    assert classified["other_files"] == ("README.md",)


def test_choose_entrypoint_prefers_index_html() -> None:
    assert (
        SiteBundleManifestManager.choose_entrypoint(
            ["about.html", "index.html", "assets/site.css"]
        )
        == "index.html"
    )


def test_choose_entrypoint_falls_back_to_first_html_page() -> None:
    assert (
        SiteBundleManifestManager.choose_entrypoint(
            ["services.html", "assets/site.css"]
        )
        == "services.html"
    )


def test_choose_entrypoint_defaults_when_empty() -> None:
    assert SiteBundleManifestManager.choose_entrypoint([]) == "index.html"


def test_build_manifest_returns_typed_manifest() -> None:
    manifest = SiteBundleManifestManager.build_manifest(
        ["index.html", "assets/site.css", "robots.txt"]
    )

    assert isinstance(manifest, SiteBundleManifest)
    assert manifest.entrypoint == "index.html"
    assert manifest.files == ("index.html", "assets/site.css", "robots.txt")
    assert manifest.html_pages == ("index.html",)
    assert manifest.asset_files == ("assets/site.css",)
    assert manifest.other_files == ("robots.txt",)


def test_manifest_metadata_is_json_safe() -> None:
    manifest = SiteBundleManifest(
        entrypoint="index.html",
        html_pages=("index.html",),
        asset_files=("assets/site.css",),
        other_files=("robots.txt",),
        files=("index.html", "assets/site.css", "robots.txt"),
    )

    assert manifest.to_metadata() == {
        "entrypoint": "index.html",
        "html_pages": ["index.html"],
        "asset_files": ["assets/site.css"],
        "other_files": ["robots.txt"],
        "files": ["index.html", "assets/site.css", "robots.txt"],
    }


def test_build_manifest_payload_adds_bundle_name_and_project_slug() -> None:
    payload = SiteBundleManifestManager.build_manifest_payload(
        bundle_name="Harry's Hot Dog Cart",
        paths=["index.html", "assets/site.css"],
        project_slug="harrys-hot-dog-cart",
    )

    assert payload["bundle_name"] == "Harry's Hot Dog Cart"
    assert payload["project_slug"] == "harrys-hot-dog-cart"
    assert payload["entrypoint"] == "index.html"
    assert payload["files"] == ["index.html", "assets/site.css"]
