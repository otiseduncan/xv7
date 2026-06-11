from fastapi.testclient import TestClient

import core.main as main


class _AsyncCloser:
    def __init__(self) -> None:
        self.calls = 0

    async def aclose(self) -> None:
        self.calls += 1


def test_lifespan_preserves_startup_and_shutdown(monkeypatch) -> None:
    startup_calls = {"ensure": 0, "bootstrap": 0}

    async def fake_ensure_session_facts_table() -> None:
        startup_calls["ensure"] += 1

    class _PersistentMemoryStub:
        def bootstrap_seed_records(self) -> None:
            startup_calls["bootstrap"] += 1

    base_agent_stub = _AsyncCloser()
    vector_store_stub = _AsyncCloser()

    monkeypatch.setattr(
        main, "ensure_session_facts_table", fake_ensure_session_facts_table
    )
    monkeypatch.setattr(main, "persistent_memory_manager", _PersistentMemoryStub())
    monkeypatch.setattr(main, "base_agent", base_agent_stub)
    monkeypatch.setattr(main, "vector_store", vector_store_stub)

    with TestClient(main.app) as client:
        response = client.get("/health")
        assert response.status_code == 200

    assert startup_calls["ensure"] == 1
    assert startup_calls["bootstrap"] == 1
    assert base_agent_stub.calls == 1
    assert vector_store_stub.calls == 1
