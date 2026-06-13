from __future__ import annotations

import os
import re
from pathlib import Path


class RepoSafetyPolicy:
    """Repo patch and commit safety checks for artifact apply flows."""

    @staticmethod
    def workspace_root() -> Path:
        configured = str(os.getenv("XV7_ARTIFACT_PATCH_ROOT", "")).strip()
        root = Path(configured) if configured else Path.cwd()
        return root.resolve()

    @staticmethod
    def is_blocked_patch_target(path_text: str) -> bool:
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

    @staticmethod
    def is_blocked_commit_target(path_text: str) -> bool:
        lowered = path_text.lower().replace("\\", "/")
        path_parts = [part for part in Path(lowered).parts if part not in {"/", "\\"}]
        blocked_top_level = {
            ".git",
            ".env",
            ".pytest_cache",
            "__pycache__",
            "brain_runtime_records",
            "brain_seed_records",
            "data",
            "memories",
            "memory_records",
            "node_modules",
            "runtime",
        }
        blocked_segments = (
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
        )
        if path_parts and path_parts[0] in blocked_top_level:
            return True
        return any(segment in lowered for segment in blocked_segments)

    @staticmethod
    def is_absolute_path_text(path_text: str) -> bool:
        normalized = str(path_text or "").strip().replace("\\", "/")
        return bool(
            Path(normalized).is_absolute()
            or normalized.startswith("/")
            or normalized.startswith("//")
            or re.match(r"^[a-zA-Z]:/", normalized)
        )

    @classmethod
    def resolve_safe_patch_target(
        cls,
        *,
        root: Path,
        target_path: str,
    ) -> tuple[Path | None, str | None]:
        target_path_text = str(target_path or "")
        target_rel = Path(target_path_text.replace("\\", "/"))
        if not target_path_text.strip():
            return None, "target path is empty"
        if cls.is_absolute_path_text(target_path_text) or ".." in target_rel.parts:
            return None, "target path is unsafe"

        normalized_target = str(target_rel).replace("\\", "/")
        if not normalized_target.startswith("generated-sites/"):
            return None, "target path must stay under generated-sites/"
        if cls.is_blocked_patch_target(normalized_target):
            return None, "target path is blocked by safety policy"

        resolved = (root / target_rel).resolve()
        root_resolved = root.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            return None, "target path escapes repo root"
        return resolved, None

    @classmethod
    def validate_patch_proposal(
        cls,
        *,
        root: Path,
        target_path: str,
        content: str,
        language: str,
        business_name: str,
        operation: str,
    ) -> tuple[str, list[dict[str, str]], list[str]]:
        checks: list[dict[str, str]] = []
        failures: list[str] = []

        def _add_check(name: str, passed: bool, detail: str) -> None:
            checks.append(
                {
                    "name": name,
                    "status": "passed" if passed else "failed",
                    "detail": detail,
                }
            )
            if not passed:
                failures.append(f"{name}: {detail}")

        target = Path(target_path)
        target_text = target_path.replace("\\", "/")
        _add_check(
            "operation_allowed",
            operation in {"create", "update"},
            "operation must be create or update",
        )
        _add_check(
            "target_path_prefix",
            target_text.startswith("generated-sites/"),
            "target path must stay under generated-sites/",
        )
        _add_check(
            "target_path_relative",
            not cls.is_absolute_path_text(target_path),
            "target path must be relative",
        )
        _add_check(
            "target_path_no_traversal",
            ".." not in target.parts,
            "target path cannot include traversal",
        )
        _add_check(
            "target_path_not_blocked",
            not cls.is_blocked_patch_target(target_text),
            "target path cannot target protected files or folders",
        )

        try:
            resolved = (root / target).resolve()
            root_resolved = root.resolve()
            try:
                resolved.relative_to(root_resolved)
                inside_repo = True
            except ValueError:
                inside_repo = False
            _add_check(
                "target_path_inside_repo",
                inside_repo,
                "target path must resolve inside repo root",
            )
        except Exception:
            _add_check(
                "target_path_inside_repo",
                False,
                "target path failed canonical resolution",
            )

        language = language.lower()
        expected_ext = {
            "html": ".html",
            "css": ".css",
            "javascript": ".js",
            "typescript": ".ts",
            "python": ".py",
        }.get(language)
        ext = os.path.splitext(target_path)[1].lower()
        _add_check(
            "target_extension",
            expected_ext is None or ext == expected_ext,
            "target file extension must match artifact language",
        )

        _add_check(
            "content_non_empty", bool(content.strip()), "content cannot be empty"
        )
        _add_check(
            "content_no_markdown_fence",
            "```" not in content,
            "content cannot contain markdown fences",
        )
        _add_check(
            "content_no_shell_commands",
            not re.search(
                r"\b(rm\s+-rf|git\s+reset|powershell\s+-|bash\s+-|curl\s+|wget\s+)\b",
                content.lower(),
            ),
            "content cannot contain shell automation commands",
        )
        _add_check(
            "content_no_repo_automation",
            not re.search(
                r"\b(git\s+add|git\s+commit|git\s+push|npm\s+test|pytest)\b",
                content.lower(),
            ),
            "content cannot include repo automation directives",
        )
        _add_check(
            "content_no_external_script",
            not re.search(
                r"<script[^>]+src\s*=\s*['\"]https?://", content, flags=re.IGNORECASE
            ),
            "content cannot include external script src URLs",
        )
        _add_check(
            "content_no_remote_urls",
            not re.search(r"https?://", content, flags=re.IGNORECASE),
            "content cannot include remote URLs",
        )

        if language == "html":
            target_is_site_bundle = target_path.replace("\\", "/").startswith(
                "generated-sites/"
            )
            _add_check(
                "html_shell",
                "<!doctype html" in content.lower() or "<html" in content.lower(),
                "html artifacts need a full html document shell",
            )
            _add_check(
                "html_inline_css",
                "<style" in content.lower()
                or (
                    target_is_site_bundle
                    and "<link" in content.lower()
                    and "stylesheet" in content.lower()
                ),
                "html artifacts must include inline style content",
            )

        if business_name:
            _add_check(
                "business_name_present",
                business_name.lower() in content.lower(),
                "artifact business name should remain in content",
            )

        status = "failed" if failures else "passed"
        return status, checks, failures
