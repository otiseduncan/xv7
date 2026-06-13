from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from core.brain import site_bundle as sb


class SandboxWriteManager:
    """Sandbox path safety and file writing for generated artifacts."""

    @staticmethod
    def _is_windows_style_path(path_text: str) -> bool:
        text = str(path_text or "").strip()
        return bool(re.match(r"^[A-Za-z]:[\\/]", text))

    @classmethod
    def sandbox_root(cls) -> Path:
        """Return the write root used inside the current runtime environment."""
        configured_write = str(os.getenv("XV7_SANDBOX_ROOT_WRITE", "")).strip()
        configured = str(os.getenv("XV7_SANDBOX_ROOT", "")).strip()
        if configured_write:
            return Path(configured_write).resolve()

        # On non-Windows runtimes (e.g., Docker/Linux), a Windows host path in
        # XV7_SANDBOX_ROOT should not be resolved into /app/X:/... . Prefer an
        # explicit container root when available, then a safe default mount path.
        if os.name != "nt" and cls._is_windows_style_path(configured):
            container_root = (
                str(os.getenv("XV7_SANDBOX_ROOT_CONTAINER", "")).strip()
                or "/xoduz-sandbox"
            )
            return Path(container_root).resolve()

        root = Path(configured) if configured else Path("X:/xoduz-sandbox")
        return root.resolve()

    @classmethod
    def sandbox_display_root(cls) -> str:
        """Return the user-visible sandbox root path for receipts/messages."""
        configured_display = str(os.getenv("XV7_SANDBOX_ROOT_DISPLAY", "")).strip()
        if configured_display:
            return configured_display

        configured = str(os.getenv("XV7_SANDBOX_ROOT", "")).strip()
        if configured and cls._is_windows_style_path(configured):
            return configured.replace("/", "\\")

        return str(cls.sandbox_root())

    @classmethod
    def display_path_for_write_target(cls, write_target_path: str) -> str:
        """Map an internal write path to a display path if roots differ."""
        target_text = str(write_target_path or "").strip()
        if not target_text:
            return ""

        write_root = cls.sandbox_root()
        display_root = cls.sandbox_display_root().rstrip("/\\")

        try:
            target = Path(target_text).resolve()
            relative = target.relative_to(write_root)
            rel_text = str(relative).replace("/", "\\")
            separator = "" if display_root.endswith(("/", "\\")) else "\\"
            return f"{display_root}{separator}{rel_text}"
        except Exception:
            return target_text

    @staticmethod
    def sanitize_filename(filename: str, language: str) -> str:
        language_defaults = {
            "html": "index.html",
            "css": "styles.css",
            "javascript": "app.js",
            "typescript": "app.ts",
            "python": "main.py",
        }
        fallback = language_defaults.get(language.lower(), "artifact.txt")
        candidate = str(filename or "").strip().split("/")[-1].split("\\")[-1]
        candidate = re.sub(r"[^A-Za-z0-9._-]", "", candidate)
        if not candidate:
            candidate = fallback
        _, ext = os.path.splitext(candidate)
        expected_ext = os.path.splitext(fallback)[1]
        if expected_ext and ext.lower() != expected_ext.lower():
            candidate = os.path.splitext(candidate)[0] + expected_ext
        return candidate

    @staticmethod
    def is_blocked_target(path_text: str) -> bool:
        lowered = path_text.lower().replace("\\", "/")
        blocked_segments = (
            "/.git",
            "/.env",
            "node_modules",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "runtime/logs",
            "data/memory",
            "data/vectors",
            "data/brain",
            "memories/",
        )
        return any(segment in lowered for segment in blocked_segments)

    @classmethod
    def resolve_safe_target(
        cls,
        *,
        root: Path,
        target_path: str,
    ) -> tuple[Path | None, str | None]:
        target_text = str(target_path or "")
        target_rel = Path(target_text.replace("\\", "/"))
        if not target_text.strip():
            return None, "target path is empty"
        if target_rel.is_absolute() or ".." in target_rel.parts:
            return None, "target path is unsafe"
        normalized_target = str(target_rel).replace("\\", "/")
        if cls.is_blocked_target(normalized_target):
            return None, "target path is blocked by safety policy"

        resolved = (root / target_rel).resolve()
        root_resolved = root.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            return None, "target path escapes sandbox root"
        return resolved, None

    @classmethod
    def relative_file_path(
        cls,
        *,
        project_slug: str,
        filename: str,
        language: str,
    ) -> str:
        clean_filename = cls.sanitize_filename(filename, language)
        return f"{project_slug}/{clean_filename}"

    @classmethod
    def write_file(
        cls,
        *,
        project_slug: str,
        filename: str,
        content: str,
        language: str | None = None,
    ) -> tuple[str, str]:
        sandbox_root = cls.sandbox_root()
        file_language = language or cls._language_from_filename(filename)
        relative_path = cls.relative_file_path(
            project_slug=project_slug,
            filename=filename,
            language=file_language,
        )
        target, error = cls.resolve_safe_target(
            root=sandbox_root,
            target_path=relative_path,
        )
        if target is None:
            raise RuntimeError(error or "sandbox_target_invalid")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return relative_path.replace("\\", "/"), str(target)

    @classmethod
    def write_bundle(
        cls,
        *,
        project_slug: str,
        bundle_files: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        sandbox_root = cls.sandbox_root()
        written_relative: list[str] = []
        written_absolute: list[str] = []
        for item in bundle_files:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").replace("\\", "/")
            content = str(item.get("content") or "")
            if not path or not sb.is_safe_bundle_path(path):
                continue
            relative_path = f"{project_slug}/{path}"
            target, error = cls.resolve_safe_target(
                root=sandbox_root,
                target_path=relative_path,
            )
            if target is None:
                raise RuntimeError(error or f"sandbox_target_invalid:{relative_path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written_relative.append(relative_path)
            written_absolute.append(str(target))
        return written_relative, written_absolute

    @staticmethod
    def _language_from_filename(filename: str) -> str:
        lowered = str(filename or "").lower()
        if lowered.endswith(".ts"):
            return "typescript"
        if lowered.endswith(".js"):
            return "javascript"
        if lowered.endswith(".css"):
            return "css"
        if lowered.endswith(".py"):
            return "python"
        return "html"
