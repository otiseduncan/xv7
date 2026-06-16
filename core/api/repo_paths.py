from __future__ import annotations

import os
import re
from pathlib import Path


def resolve_operator_repo_root(
    *,
    env_value: str | None = None,
    fallback: Path | None = None,
    current_os_name: str | None = None,
) -> Path:
    fallback_root = (fallback or Path.cwd()).resolve()
    raw = str(
        env_value
        if env_value is not None
        else os.getenv("XV7_OPERATOR_REPO_ROOT", str(fallback_root))
    ).strip()
    if not raw:
        return fallback_root

    os_name = current_os_name or os.name
    if os_name != "nt" and re.match(r"^[A-Za-z]:[\\/]", raw):
        return fallback_root

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = fallback_root / candidate

    try:
        resolved = candidate.resolve()
    except OSError:
        return fallback_root

    if not resolved.exists():
        return fallback_root

    return resolved
