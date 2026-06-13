from __future__ import annotations

from pathlib import Path

import pytest

from core.brain.answer_contract import AnswerContract
from core.brain.sandbox_writer import SandboxWriteManager


def test_resolve_safe_target_accepts_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"

    target, error = SandboxWriteManager.resolve_safe_target(
        root=root,
        target_path="demo/index.html",
    )

    assert error is None
    assert target == (root / "demo/index.html").resolve()


@pytest.mark.parametrize(
    ("target_path", "expected_error"),
    [
        ("", "target path is empty"),
        (None, "target path is empty"),
        ("../outside.html", "target path is unsafe"),
        ("demo/node_modules/app.js", "target path is blocked by safety policy"),
    ],
)
def test_resolve_safe_target_rejects_invalid_paths(
    tmp_path: Path,
    target_path: str | None,
    expected_error: str,
) -> None:
    target, error = SandboxWriteManager.resolve_safe_target(
        root=tmp_path / "sandbox",
        target_path="" if target_path is None else target_path,
    )

    assert target is None
    assert error == expected_error


def test_resolve_safe_target_rejects_absolute_path(tmp_path: Path) -> None:
    absolute_target = tmp_path / "outside.html"

    target, error = SandboxWriteManager.resolve_safe_target(
        root=tmp_path / "sandbox",
        target_path=str(absolute_target),
    )

    assert target is None
    assert error == "target path is unsafe"


def test_resolve_safe_target_rejects_path_that_resolves_outside_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "sandbox"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    escape_source = root / "escape.html"
    escaped_target = outside / "escape.html"
    original_resolve = Path.resolve

    def fake_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self == escape_source:
            return escaped_target
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    target, error = SandboxWriteManager.resolve_safe_target(
        root=root,
        target_path="escape.html",
    )

    assert target is None
    assert error == "target path escapes sandbox root"


def test_sanitize_filename_preserves_safe_and_fixes_unsafe_names() -> None:
    assert SandboxWriteManager.sanitize_filename("index.html", "html") == "index.html"
    assert (
        SandboxWriteManager.sanitize_filename("../bad name.js", "javascript")
        == "badname.js"
    )
    assert SandboxWriteManager.sanitize_filename("styles.html", "css") == "styles.css"
    assert SandboxWriteManager.sanitize_filename("", "python") == "main.py"


def test_relative_file_path_returns_project_slug_and_safe_filename() -> None:
    assert (
        SandboxWriteManager.relative_file_path(
            project_slug="demo-site",
            filename="../bad name.js",
            language="javascript",
        )
        == "demo-site/badname.js"
    )


def test_write_file_uses_temporary_sandbox_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path))

    relative_path, absolute_path = SandboxWriteManager.write_file(
        project_slug="demo",
        filename="index.html",
        content="<html>Demo</html>",
        language="html",
    )

    assert relative_path == "demo/index.html"
    target = Path(absolute_path)
    assert target == (tmp_path / "demo/index.html").resolve()
    assert target.read_text(encoding="utf-8") == "<html>Demo</html>"


def test_write_bundle_writes_safe_files_and_skips_unsafe_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path))

    written_relative, written_absolute = SandboxWriteManager.write_bundle(
        project_slug="demo",
        bundle_files=[
            {"path": "index.html", "content": "<html>Home</html>"},
            {"path": "assets/site.css", "content": "body { color: black; }"},
            {"path": "../escape.html", "content": "bad"},
            {"path": "/absolute.html", "content": "bad"},
        ],
    )

    assert written_relative == ["demo/index.html", "demo/assets/site.css"]
    assert written_absolute == [
        str((tmp_path / "demo/index.html").resolve()),
        str((tmp_path / "demo/assets/site.css").resolve()),
    ]
    assert (tmp_path / "demo/index.html").read_text(
        encoding="utf-8"
    ) == "<html>Home</html>"
    assert not (tmp_path / "escape.html").exists()


def test_answer_contract_wrappers_match_sandbox_write_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path))

    assert AnswerContract._sandbox_root() == SandboxWriteManager.sandbox_root()
    assert AnswerContract._sanitize_filename(
        "../bad name.js",
        "javascript",
    ) == SandboxWriteManager.sanitize_filename("../bad name.js", "javascript")
    contract_target, contract_error = AnswerContract._resolve_safe_sandbox_target(
        root=tmp_path,
        target_path="demo/index.html",
    )
    manager_target, manager_error = SandboxWriteManager.resolve_safe_target(
        root=tmp_path,
        target_path="demo/index.html",
    )
    assert (contract_target, contract_error) == (manager_target, manager_error)
    assert AnswerContract._sandbox_relative_file_path(
        project_slug="demo",
        filename="../bad name.js",
    ) == SandboxWriteManager.relative_file_path(
        project_slug="demo",
        filename="../bad name.js",
        language="javascript",
    )

    contract_file = AnswerContract._write_sandbox_file(
        project_slug="contract",
        filename="index.html",
        content="<html>Contract</html>",
    )
    manager_file = SandboxWriteManager.write_file(
        project_slug="manager",
        filename="index.html",
        content="<html>Manager</html>",
        language="html",
    )
    assert contract_file[0] == "contract/index.html"
    assert manager_file[0] == "manager/index.html"
    assert Path(contract_file[1]).read_text(encoding="utf-8") == "<html>Contract</html>"
    assert Path(manager_file[1]).read_text(encoding="utf-8") == "<html>Manager</html>"

    bundle_files = [{"path": "index.html", "content": "<html>Bundle</html>"}]
    assert AnswerContract._write_sandbox_bundle(
        project_slug="contract-bundle",
        bundle_files=bundle_files,
    ) == SandboxWriteManager.write_bundle(
        project_slug="contract-bundle",
        bundle_files=bundle_files,
    )
