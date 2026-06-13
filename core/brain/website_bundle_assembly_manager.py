"""Website bundle assembly planning helpers.

This module is intentionally standalone during the Code 22 split. It creates
deterministic manifest payloads only and never writes files.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Literal, TypedDict


FileKind = Literal["html", "asset"]


class PlannedBundleFile(TypedDict):
    path: str
    kind: FileKind
    source: str


class PageRoute(TypedDict):
    slug: str
    path: str
    route: str


class WebsiteBundlePlanPayload(TypedDict):
    entrypoint: str
    files: list[PlannedBundleFile]
    html_files: list[str]
    asset_files: list[str]
    page_routes: list[PageRoute]
    warnings: list[str]


class WebsiteBundleAssemblyManager:
    """Plan website bundle file manifests."""

    NON_WORD_RE = re.compile(r"[^a-z0-9]+")
    DEFAULT_CSS = "assets/css/styles.css"
    DEFAULT_JS = "assets/js/main.js"

    @classmethod
    def slug_for_page(cls, value: str) -> str:
        normalized = str(value or "").strip().lower().replace(".html", "")
        slug = cls.NON_WORD_RE.sub("-", normalized).strip("-")
        if slug in {"", "home", "homepage", "index"}:
            return "index"
        return slug

    @staticmethod
    def normalize_safe_path(path: str) -> tuple[str | None, str | None]:
        raw = str(path or "").strip().replace("\\", "/")
        if not raw:
            return None, "empty path skipped"
        if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
            return None, f"unsafe absolute path skipped: {raw}"
        parts = [part for part in PurePosixPath(raw).parts if part not in {"", "."}]
        if ".." in parts:
            return None, f"unsafe traversal path skipped: {raw}"
        normalized = str(PurePosixPath(*parts)) if parts else ""
        if not normalized:
            return None, "empty path skipped"
        return normalized, None

    @classmethod
    def html_path_for_page(cls, page: str) -> str:
        slug = cls.slug_for_page(page)
        if slug == "index":
            return "index.html"
        return f"pages/{slug}.html"

    @staticmethod
    def classify_path(path: str) -> FileKind:
        return "html" if path.lower().endswith(".html") else "asset"

    @classmethod
    def _add_file(
        cls,
        files: list[PlannedBundleFile],
        seen: set[str],
        warnings: list[str],
        path: str,
        source: str,
    ) -> None:
        safe_path, warning = cls.normalize_safe_path(path)
        if warning is not None:
            warnings.append(warning)
            return
        if safe_path is None or safe_path in seen:
            return
        seen.add(safe_path)
        files.append(
            {
                "path": safe_path,
                "kind": cls.classify_path(safe_path),
                "source": source,
            }
        )

    @classmethod
    def plan_bundle(
        cls,
        *,
        pages: Sequence[str] | None = None,
        content_files: Sequence[str] | None = None,
        asset_files: Sequence[str] | None = None,
        image_assets: Sequence[str] | None = None,
        font_assets: Sequence[str] | None = None,
    ) -> WebsiteBundlePlanPayload:
        warnings: list[str] = []
        files: list[PlannedBundleFile] = []
        seen: set[str] = set()

        page_values = list(pages or ["index"])
        html_paths = [cls.html_path_for_page(page) for page in page_values]
        if "index.html" not in html_paths:
            html_paths.insert(0, "index.html")

        for path in html_paths:
            cls._add_file(files, seen, warnings, path, "page")
        for path in content_files or ():
            cls._add_file(files, seen, warnings, path, "content")
        cls._add_file(files, seen, warnings, cls.DEFAULT_CSS, "default_asset")
        cls._add_file(files, seen, warnings, cls.DEFAULT_JS, "default_asset")
        for path in asset_files or ():
            cls._add_file(files, seen, warnings, path, "asset")
        for path in image_assets or ():
            cls._add_file(files, seen, warnings, path, "image_asset")
        for path in font_assets or ():
            cls._add_file(files, seen, warnings, path, "font_asset")

        html_files = [item["path"] for item in files if item["kind"] == "html"]
        asset_paths = [item["path"] for item in files if item["kind"] == "asset"]
        page_routes = [
            {
                "slug": "index" if path == "index.html" else PurePosixPath(path).stem,
                "path": path,
                "route": "/"
                if path == "index.html"
                else f"/{PurePosixPath(path).stem}",
            }
            for path in html_files
        ]
        entrypoint = "index.html" if "index.html" in html_files else html_files[0]
        return {
            "entrypoint": entrypoint,
            "files": files,
            "html_files": html_files,
            "asset_files": asset_paths,
            "page_routes": page_routes,
            "warnings": warnings,
        }
