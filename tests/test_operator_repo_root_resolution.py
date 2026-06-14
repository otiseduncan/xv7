from __future__ import annotations

from pathlib import Path

from core.main import _resolve_operator_repo_root


def test_windows_env_repo_root_falls_back_on_non_windows_runtime(
    tmp_path: Path,
) -> None:
    fallback = tmp_path / "fallback"
    fallback.mkdir(parents=True, exist_ok=True)

    resolved = _resolve_operator_repo_root(
        env_value="X:\\XV7\\xv7",
        fallback=fallback,
        current_os_name="posix",
    )

    assert resolved == fallback.resolve()


def test_existing_env_repo_root_is_used(tmp_path: Path) -> None:
    fallback = tmp_path / "fallback"
    fallback.mkdir(parents=True, exist_ok=True)
    explicit = tmp_path / "repo-root"
    explicit.mkdir(parents=True, exist_ok=True)

    resolved = _resolve_operator_repo_root(
        env_value=str(explicit),
        fallback=fallback,
    )

    assert resolved == explicit.resolve()
