from __future__ import annotations

import re
from pathlib import Path

from receipts import WORKSPACE_DIR


def safe_workspace_path(raw_path: str) -> Path:
    if not raw_path.strip():
        raise ValueError("workspace path is required")
    if re.match(r"^[A-Za-z]:", raw_path):
        raise ValueError("Windows drive prefixes are not allowed")
    candidate = Path(raw_path.replace("\\", "/"))
    if candidate.is_absolute():
        raise ValueError("absolute paths are not allowed")
    if ".." in candidate.parts:
        raise ValueError("path traversal is not allowed")
    resolved = (WORKSPACE_DIR / candidate).resolve()
    workspace_root = WORKSPACE_DIR.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("path outside workspace is not allowed") from exc
    if resolved.is_symlink():
        raise ValueError("workspace target symlinks are not allowed")
    parent = resolved.parent
    while parent != workspace_root:
        if parent.exists() and parent.is_symlink():
            raise ValueError("workspace parent symlinks are not allowed")
        parent = parent.parent
    return resolved
