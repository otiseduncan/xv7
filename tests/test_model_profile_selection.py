from __future__ import annotations

from core.runtime.model_profile_selection import (
    clear_runtime_profile_override,
    get_runtime_profile_override,
    get_runtime_profile_selection_state,
    set_runtime_profile_override,
)


def test_runtime_profile_selection_set_get_clear(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    assert get_runtime_profile_override() is None

    selected = set_runtime_profile_override(
        "balanced",
        {"low_resource", "balanced", "local_test", "large_code"},
    )

    assert selected == "balanced"
    assert get_runtime_profile_override() == "balanced"

    state = get_runtime_profile_selection_state()
    assert state.profile == "balanced"
    assert state.source == "runtime_override"

    clear_runtime_profile_override()
    assert get_runtime_profile_override() is None


def test_runtime_profile_selection_rejects_unknown_profile(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "XV7_RUNTIME_PROFILE_STATE_PATH",
        str(tmp_path / "runtime" / "model_profile_selection.json"),
    )

    try:
        set_runtime_profile_override("unknown", {"balanced"})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Unknown profile" in str(exc)
