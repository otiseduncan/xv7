from __future__ import annotations

from pathlib import Path


def resolve_target_path(raw: str, repo_root: Path) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def path_allowed(path: Path, repo_root: Path) -> bool:
    allowed_roots = [repo_root, repo_root.parent]
    return any(root == path or root in path.parents for root in allowed_roots)


def extract_read_target(question: str) -> str:
    original = question.strip()
    if len(original) <= 5:
        return ""
    return original[5:].strip().strip(".")
