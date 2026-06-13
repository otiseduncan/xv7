from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SiteBundleManifest:
    entrypoint: str
    html_pages: tuple[str, ...]
    asset_files: tuple[str, ...]
    other_files: tuple[str, ...]
    files: tuple[str, ...]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "entrypoint": self.entrypoint,
            "html_pages": list(self.html_pages),
            "asset_files": list(self.asset_files),
            "other_files": list(self.other_files),
            "files": list(self.files),
        }


class SiteBundleManifestManager:
    """Build deterministic metadata for generated multi-file site bundles."""

    @staticmethod
    def normalize_path(raw_path: object) -> str:
        path = str(raw_path or "").strip().replace("\\", "/")
        while "//" in path:
            path = path.replace("//", "/")
        return path.lstrip("/")

    @classmethod
    def unique_paths(cls, paths: list[object] | tuple[object, ...]) -> tuple[str, ...]:
        unique: list[str] = []
        seen: set[str] = set()
        for raw_path in paths:
            path = cls.normalize_path(raw_path)
            if not path or path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return tuple(unique)

    @classmethod
    def classify_paths(
        cls,
        paths: list[object] | tuple[object, ...],
    ) -> dict[str, tuple[str, ...]]:
        files = cls.unique_paths(paths)
        html_pages = tuple(path for path in files if path.endswith(".html"))
        asset_files = tuple(path for path in files if path.startswith("assets/"))
        other_files = tuple(
            path for path in files if path not in html_pages and path not in asset_files
        )
        return {
            "files": files,
            "html_pages": html_pages,
            "asset_files": asset_files,
            "other_files": other_files,
        }

    @classmethod
    def choose_entrypoint(
        cls,
        paths: list[object] | tuple[object, ...],
    ) -> str:
        files = cls.unique_paths(paths)
        if "index.html" in files:
            return "index.html"
        html_pages = [path for path in files if path.endswith(".html")]
        if html_pages:
            return html_pages[0]
        return files[0] if files else "index.html"

    @classmethod
    def build_manifest(
        cls,
        paths: list[object] | tuple[object, ...],
    ) -> SiteBundleManifest:
        classified = cls.classify_paths(paths)
        files = classified["files"]
        return SiteBundleManifest(
            entrypoint=cls.choose_entrypoint(files),
            html_pages=classified["html_pages"],
            asset_files=classified["asset_files"],
            other_files=classified["other_files"],
            files=files,
        )

    @classmethod
    def build_manifest_payload(
        cls,
        *,
        bundle_name: str,
        paths: list[object] | tuple[object, ...],
        project_slug: str | None = None,
    ) -> dict[str, Any]:
        manifest = cls.build_manifest(paths)
        payload = manifest.to_metadata()
        payload["bundle_name"] = str(bundle_name or "site-bundle").strip()
        if project_slug:
            payload["project_slug"] = str(project_slug).strip()
        return payload
