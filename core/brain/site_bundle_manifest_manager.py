from __future__ import annotations


class SiteBundleManifestManager:
    """Build deterministic metadata for generated multi-file site bundles."""

    @staticmethod
    def normalize_path(raw_path: object) -> str:
        path = str(raw_path or "").strip().replace("\\", "/")
        while "//" in path:
            path = path.replace("//", "/")
        return path.lstrip("/")
