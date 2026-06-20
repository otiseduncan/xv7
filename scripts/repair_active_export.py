from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/operator/manager.py"

old = '''        active_export = session_metadata.get("active_exported_artifact")
        if isinstance(active_export, dict):
            preferred_value = ""
            for key in (
                "host_project_path",
                "relative_project_path",
                "container_project_path",
            ):
                value = active_export.get(key)
                if isinstance(value, str) and value.strip():
                    preferred_value = value
                    break

            normalized_candidate = (
                _normalized_candidate_path(preferred_value) if preferred_value else None
            )
            if not normalized_candidate:
                project_slug = active_export.get("project_slug")
                if isinstance(project_slug, str) and project_slug.strip():
                    normalized_candidate = str(
                        (
                            SandboxWriteManager.sandbox_root() / project_slug.strip()
                        ).resolve()
                    )

            if normalized_candidate:
                candidates.append(normalized_candidate)
'''

new = '''        active_export = session_metadata.get("active_exported_artifact")
        if isinstance(active_export, dict):
            for key in (
                "container_project_path",
                "relative_project_path",
                "entry_file",
            ):
                value = active_export.get(key)
                if isinstance(value, str):
                    normalized_candidate = _normalized_candidate_path(value)
                    if normalized_candidate:
                        candidates.append(normalized_candidate)

            project_slug = active_export.get("project_slug")
            if isinstance(project_slug, str) and project_slug.strip():
                candidates.append(
                    str(
                        (
                            SandboxWriteManager.sandbox_root() / project_slug.strip()
                        ).resolve()
                    )
                )
'''

content = PATH.read_text(encoding="utf-8")
if old not in content:
    raise SystemExit("expected active export block not found")
PATH.write_text(content.replace(old, new, 1), encoding="utf-8")
print("active export path precedence repaired")
