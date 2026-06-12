from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from core.brain.records import BrainRecordLoader
from core.brain.schema import BrainLayer


def _seed_copy(dst: Path) -> None:
    src = Path(__file__).resolve().parents[1] / "data" / "brain" / "records"
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.glob("*.json"):
        shutil.copy2(item, dst / item.name)


def test_focus_runtime_env_same_as_seed_uses_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed_dir = tmp_path / "seed"
    runtime_dir = tmp_path / "runtime"
    _seed_copy(seed_dir)

    monkeypatch.setenv("XV7_BRAIN_RUNTIME_RECORDS_PATH", str(seed_dir))
    monkeypatch.setenv("XV7_BRAIN_RUNTIME_FALLBACK_PATH", str(runtime_dir))
    monkeypatch.delenv("XV7_ALLOW_BRAIN_SEED_WRITES", raising=False)

    loader = BrainRecordLoader(records_dir=seed_dir)
    assert loader.runtime_records_dir == runtime_dir

    created = loader.apply_active_focus_instruction(
        "harden active focus runtime persistence"
    )

    assert (runtime_dir / f"{created.record_id}.json").exists()
    assert not (seed_dir / f"{created.record_id}.json").exists()

    seed_focus = json.loads(
        (seed_dir / "XV7-FOCUS-0004.json").read_text(encoding="utf-8")
    )
    assert seed_focus["status"] == "active"

    runtime_focus = json.loads(
        (runtime_dir / "XV7-FOCUS-0004.json").read_text(encoding="utf-8")
    )
    assert runtime_focus["status"] == "archived"
    assert runtime_focus["superseded_by"] == created.record_id

    active_ids = [
        record.record_id
        for record in loader.load_active_records(layer=BrainLayer.ACTIVE_FOCUS)
    ]
    assert active_ids == [created.record_id]


def test_focus_runtime_store_error_keeps_seed_focus(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seed"
    runtime_file = tmp_path / "runtime_file"
    _seed_copy(seed_dir)
    runtime_file.write_text("blocked", encoding="utf-8")

    loader = BrainRecordLoader(records_dir=seed_dir, runtime_records_dir=runtime_file)

    with pytest.raises(RuntimeError, match="runtime record store"):
        loader.apply_active_focus_instruction("harden active focus runtime persistence")

    seed_focus = json.loads(
        (seed_dir / "XV7-FOCUS-0004.json").read_text(encoding="utf-8")
    )
    assert seed_focus["status"] == "active"
    assert not (seed_dir / "XV7-FOCUS-0005.json").exists()
