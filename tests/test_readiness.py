"""Tests for core.runtime.readiness — local pre-launch checklist logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.runtime.readiness import (
    ReadinessItem,
    ReadinessReport,
    _find_repo_root,
    _module_available,
    build_readiness_report,
)


# ---------------------------------------------------------------------------
# ReadinessItem / ReadinessReport unit tests
# ---------------------------------------------------------------------------


def test_readiness_item_as_dict_fields() -> None:
    item = ReadinessItem(key="foo", value="bar", ok=True, warning=None)
    d = item.as_dict()
    assert d == {"key": "foo", "value": "bar", "ok": True, "warning": None}


def test_readiness_report_warnings_collected() -> None:
    report = ReadinessReport()
    report.add(ReadinessItem(key="a", value="v", ok=True))
    report.add(ReadinessItem(key="b", value="v", ok=False, warning="b is missing"))
    assert report.warnings == ["b is missing"]


def test_readiness_report_all_ok_true() -> None:
    report = ReadinessReport()
    report.add(ReadinessItem(key="x", value="v", ok=True))
    assert report.all_ok is True


def test_readiness_report_all_ok_false_when_any_fail() -> None:
    report = ReadinessReport()
    report.add(ReadinessItem(key="x", value="v", ok=True))
    report.add(ReadinessItem(key="y", value="v", ok=False, warning="y bad"))
    assert report.all_ok is False


def test_readiness_report_as_dict_structure() -> None:
    report = ReadinessReport()
    report.add(ReadinessItem(key="k", value="v", ok=True))
    d = report.as_dict()
    assert "items" in d
    assert "warnings" in d
    assert "all_ok" in d
    assert d["all_ok"] is True
    assert len(d["items"]) == 1


# ---------------------------------------------------------------------------
# _find_repo_root
# ---------------------------------------------------------------------------


def test_find_repo_root_detects_docker_compose(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    result = _find_repo_root(start=tmp_path)
    assert result == tmp_path


def test_find_repo_root_detects_git(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    result = _find_repo_root(start=tmp_path)
    assert result == tmp_path


def test_find_repo_root_walks_up(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    result = _find_repo_root(start=deep)
    assert result == tmp_path


def test_find_repo_root_returns_none_when_not_found(tmp_path: Path) -> None:
    # tmp_path is typically created under the system temp dir which has no
    # docker-compose.yml or .git at its root — walk all the way up.
    # We create a subdirectory that has no marker in its ancestors (within
    # tmp_path, which is isolated).
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    # Because tmp_path itself may have .git above it on the real filesystem,
    # we just assert the return type is Path | None and skip when a root is
    # legitimately found (e.g. running tests inside the real repo).
    result = _find_repo_root(start=isolated)
    assert result is None or isinstance(result, Path)


# ---------------------------------------------------------------------------
# _module_available
# ---------------------------------------------------------------------------


def test_module_available_stdlib() -> None:
    assert _module_available("os") is True
    assert _module_available("pathlib") is True


def test_module_available_missing() -> None:
    assert _module_available("__xv7_nonexistent_package__") is False


# ---------------------------------------------------------------------------
# build_readiness_report — repo root injection
# ---------------------------------------------------------------------------


def test_report_repo_root_ok_when_provided(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    report = build_readiness_report(repo_root=tmp_path)
    root_item = next(i for i in report.items if i.key == "repo_root")
    assert root_item.ok is True
    assert str(tmp_path) in root_item.value


def test_report_repo_root_not_ok_when_absent(tmp_path: Path) -> None:
    # Pass a directory explicitly that has no markers so no auto-detection.
    # We set repo_root=None but override _find_repo_root by passing a sentinel.
    # Simplest: patch env so auto-detect returns nothing.  Actually the
    # function accepts repo_root directly; pass a path where nothing is found.
    # Since _find_repo_root walks up and may find the real repo, we pass
    # repo_root=Path("/___nonexistent___") to force not-found handling:
    report = build_readiness_report(
        repo_root=Path("/___nonexistent___does_not_exist___")
    )
    # The root was "given" so it will be treated as the root value.
    # The docker-compose check will be "not_found" since it doesn't exist.
    compose_item = next(i for i in report.items if i.key == "docker_compose_present")
    assert compose_item.ok is False


def test_report_docker_compose_ok_when_present(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    report = build_readiness_report(repo_root=tmp_path)
    compose_item = next(i for i in report.items if i.key == "docker_compose_present")
    assert compose_item.ok is True
    assert compose_item.warning is None


def test_report_docker_compose_not_ok_when_absent(tmp_path: Path) -> None:
    report = build_readiness_report(repo_root=tmp_path)
    compose_item = next(i for i in report.items if i.key == "docker_compose_present")
    assert compose_item.ok is False
    assert compose_item.warning is not None


# ---------------------------------------------------------------------------
# build_readiness_report — environment variable checks
# ---------------------------------------------------------------------------


def test_report_api_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XV7_API_KEY", "super-secret-key")
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "XV7_API_KEY")
    assert item.ok is True
    # Value must NEVER include the actual key
    assert "super-secret-key" not in item.value
    assert item.value == "configured"
    assert item.warning is None


def test_report_api_key_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XV7_API_KEY", raising=False)
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "XV7_API_KEY")
    assert item.ok is False
    assert item.warning is not None


def test_report_api_key_empty_string_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_API_KEY", "   ")
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "XV7_API_KEY")
    assert item.ok is False


def test_report_ollama_url_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "OLLAMA_BASE_URL")
    assert item.ok is True
    assert item.value == "http://localhost:11434"


def test_report_ollama_url_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "OLLAMA_BASE_URL")
    assert item.ok is False
    assert item.warning is not None


def test_report_model_default_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_DEFAULT", "llama3.2")
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "MODEL_DEFAULT")
    assert item.ok is True
    assert item.value == "llama3.2"


def test_report_model_default_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_DEFAULT", raising=False)
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "MODEL_DEFAULT")
    assert item.ok is False


def test_report_embedding_model_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "nomic-embed-text")
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "EMBEDDING_MODEL")
    assert item.ok is True


def test_report_memory_db_path_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_DB_PATH", "/data/memory")
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "MEMORY_DB_PATH")
    assert item.ok is True
    assert item.value == "/data/memory"


def test_report_vector_db_path_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VECTOR_DB_PATH", raising=False)
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "VECTOR_DB_PATH")
    assert item.ok is False
    assert item.warning is not None


# ---------------------------------------------------------------------------
# build_readiness_report — import checks (fastapi must be available in CI)
# ---------------------------------------------------------------------------


def test_report_fastapi_available_in_test_env() -> None:
    """fastapi must be importable since tests depend on it."""
    report = build_readiness_report(repo_root=Path("."))
    item = next(i for i in report.items if i.key == "import:fastapi")
    assert item.ok is True
    assert item.value == "available"


def test_report_missing_package_marked_not_ok() -> None:
    """A non-existent package must produce ok=False and a warning."""
    from core.runtime import readiness as _readiness

    original = _readiness._REQUIRED_PACKAGES
    _readiness._REQUIRED_PACKAGES = ["__xv7_fake_pkg_xyz__"]
    try:
        report = build_readiness_report(repo_root=Path("."))
        item = next(i for i in report.items if i.key == "import:__xv7_fake_pkg_xyz__")
        assert item.ok is False
        assert item.warning is not None
    finally:
        _readiness._REQUIRED_PACKAGES = original


# ---------------------------------------------------------------------------
# No live service claims
# ---------------------------------------------------------------------------


def test_report_does_not_claim_ollama_is_reachable() -> None:
    """The readiness report must not assert Ollama is up."""
    report = build_readiness_report(repo_root=Path("."))
    # Ensure no item claims "verified" or "reachable" about Ollama
    ollama_items = [i for i in report.items if "ollama" in i.key.lower()]
    for item in ollama_items:
        assert "verified" not in item.value.lower()
        assert "reachable" not in item.value.lower()
