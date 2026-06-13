import json

from core.brain.website_build_plan_manager import (
    BundlePlan,
    ContentBlockPlan,
    StylePlan,
    WebsiteBuildPlanManager,
)


def _content_blocks() -> ContentBlockPlan:
    return {
        "profile": "food",
        "blocks": [
            {
                "id": "block-01-hero",
                "slug": "hero",
                "kind": "hero",
                "label": "Hero",
                "source": "inferred",
            },
            {
                "id": "block-02-menu",
                "slug": "menu",
                "kind": "menu",
                "label": "Menu",
                "source": "inferred",
            },
        ],
    }


def _bundle(entrypoint: str = "index.html") -> BundlePlan:
    return {
        "entrypoint": entrypoint,
        "html_files": ["index.html", "pages/menu.html"],
        "asset_files": ["assets/css/styles.css"],
        "page_routes": [
            {"slug": "index", "path": "index.html", "route": "/"},
            {"slug": "menu", "path": "pages/menu.html", "route": "/menu"},
        ],
        "warnings": [],
    }


def test_complete_build_plan_returns_ready() -> None:
    style: StylePlan = {"colors": ["black", "gold"], "tone": "bold"}
    payload = WebsiteBuildPlanManager.build_plan(
        project_name="Harry's Hot Dog Cart",
        project_slug="harrys-hot-dog-cart",
        business_type="food cart",
        pages=["index", "menu"],
        sections=["hero", "menu"],
        style_plan=style,
        cta_plan={"primary": "Book catering", "secondary": ["View menu"]},
        contact_plan={"phone": "555-0100", "hours": "Mon-Fri"},
        seo_plan={"title": "Harry's Hot Dog Cart", "keywords": ["hot dogs"]},
        content_block_plan=_content_blocks(),
        bundle_plan=_bundle(),
    )

    assert payload["ready"] is True
    assert payload["warnings"] == []
    assert payload["project"] == {
        "name": "Harry's Hot Dog Cart",
        "slug": "harrys-hot-dog-cart",
    }
    assert payload["bundle"]["entrypoint"] == "index.html"


def test_missing_project_slug_returns_not_ready_with_warning() -> None:
    payload = WebsiteBuildPlanManager.build_plan(
        project_name="Harry's Hot Dog Cart",
        pages=["index"],
        content_block_plan=_content_blocks(),
        bundle_plan=_bundle(),
    )

    assert payload["ready"] is False
    assert "missing project slug" in payload["warnings"]


def test_missing_pages_returns_not_ready_with_warning() -> None:
    payload = WebsiteBuildPlanManager.build_plan(
        project_slug="harrys-hot-dog-cart",
        content_block_plan=_content_blocks(),
        bundle_plan=_bundle(),
    )

    assert payload["ready"] is False
    assert "missing pages" in payload["warnings"]


def test_missing_content_blocks_returns_not_ready_with_warning() -> None:
    payload = WebsiteBuildPlanManager.build_plan(
        project_slug="harrys-hot-dog-cart",
        pages=["index"],
        bundle_plan=_bundle(),
    )

    assert payload["ready"] is False
    assert "missing content blocks" in payload["warnings"]


def test_missing_bundle_entrypoint_returns_not_ready_with_warning() -> None:
    payload = WebsiteBuildPlanManager.build_plan(
        project_slug="harrys-hot-dog-cart",
        pages=["index"],
        content_block_plan=_content_blocks(),
        bundle_plan=_bundle(entrypoint=""),
    )

    assert payload["ready"] is False
    assert "missing bundle entrypoint" in payload["warnings"]


def test_warning_dedupe() -> None:
    bundle = _bundle()
    bundle["warnings"] = ["asset skipped", "asset skipped"]

    payload = WebsiteBuildPlanManager.build_plan(
        project_slug="harrys-hot-dog-cart",
        pages=["index"],
        content_block_plan=_content_blocks(),
        bundle_plan=bundle,
        warnings=["asset skipped", "extra note", "extra note"],
    )

    assert payload["warnings"] == ["asset skipped", "extra note"]


def test_json_safe_payload() -> None:
    payload = WebsiteBuildPlanManager.build_plan(
        project_name="Harry's Hot Dog Cart",
        project_slug="harrys-hot-dog-cart",
        pages=["index"],
        content_block_plan=_content_blocks(),
        bundle_plan=_bundle(),
    )

    assert json.loads(json.dumps(payload)) == payload


def test_stable_ordering_and_string_dedupe() -> None:
    payload = WebsiteBuildPlanManager.build_plan(
        project_slug="site",
        pages=["menu", "index", "menu", "contact"],
        sections=["menu", "hero", "menu", "contact"],
        style_plan={"colors": ["gold", "black", "gold"]},
        content_block_plan=_content_blocks(),
        bundle_plan=_bundle(),
    )

    assert payload["pages"] == ["menu", "index", "contact"]
    assert payload["sections"] == ["menu", "hero", "contact"]
    assert payload["style"]["colors"] == ["gold", "black"]
