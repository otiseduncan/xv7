from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import re
import subprocess

from fastapi.testclient import TestClient
import pytest

from core.brain.answer_contract import AnswerContract
from core.brain.manager import BrainContextManager
from core.memory.manager import PersistentMemoryManager
from core.memory.store import MemoryStore
from core.main import app
from core.runtime.schemas import SessionState
from core.runtime.model_registry import RuntimeRoleModelResolution


class _FailingAgent:
    personas = {"default": {"name": "default"}}

    async def generate_response(
        self, _session_state: SessionState
    ) -> tuple[str, dict[str, str]]:
        raise AssertionError("These prompts should be handled by answer contract")

    async def aclose(self) -> None:
        return None


async def _fake_query_similar_memories(
    _text: str, limit: int = 3
) -> list[dict[str, str]]:
    return []


async def _fake_persist_vector_memory_round_trip(
    *_args: Any, **_kwargs: Any
) -> dict[str, Any]:
    return {"status": "ok"}


async def _fake_artifact_connectivity() -> dict[str, Any]:
    return {
        "configured_endpoint": "http://ollama:11434",
        "endpoint_candidates": ["http://ollama:11434", "http://127.0.0.1:11434"],
        "resolved_model_tag": "qwen3:14b",
        "reachable_endpoint": "http://127.0.0.1:11434",
        "reachable": True,
        "checks": [
            {
                "endpoint": "http://ollama:11434",
                "reachable": False,
                "available_models": [],
                "error": "[Errno 11001] getaddrinfo failed",
            },
            {
                "endpoint": "http://127.0.0.1:11434",
                "reachable": True,
                "available_models": ["qwen3:14b"],
                "error": None,
            },
        ],
    }


def _setup_contract_only(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("XV7_API_KEY", "test-secret")
    monkeypatch.setattr("core.main.base_agent", _FailingAgent())

    memory_store = MemoryStore(records_dir=tmp_path / "memory_records")
    memory_manager = PersistentMemoryManager(store=memory_store)
    memory_manager.bootstrap_seed_records()
    monkeypatch.setattr("core.main.persistent_memory_manager", memory_manager)

    monkeypatch.setattr(
        "core.main.vector_store.query_similar_memories",
        _fake_query_similar_memories,
    )
    monkeypatch.setattr(
        "core.main.persist_vector_memory_round_trip",
        _fake_persist_vector_memory_round_trip,
    )
    return TestClient(app)


def _new_session(client: TestClient) -> str:
    session_response = client.post(
        "/sessions",
        headers={"X-XV7-API-Key": "test-secret"},
        json={"current_persona": "default"},
    )
    assert session_response.status_code == 201
    return session_response.json()["session_id"]


def _init_git_repo(root: Path) -> None:
    subprocess.run(
        ["git", "init"], cwd=root, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "XV7 Test"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "xv7-test@example.com"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _extract_business_name(prompt: str) -> str:
    quoted = re.search(r'"([^"]{2,80})"', prompt)
    if quoted:
        return quoted.group(1)
    unquoted = re.search(
        r"for\s+(.+?)(?:\s+(?:website|grooming|dog\s+grooming|pet\s+grooming|detailing|locksmiths?|arcade)\b|\s+using\b|$)",
        prompt,
        flags=re.IGNORECASE,
    )
    if unquoted:
        candidate = re.sub(r"\s+", " ", unquoted.group(1)).strip(" .,:;\"'“”‘’")
        if candidate:
            return candidate
    return "Local Business Website"


def _make_fake_model_html(prompt: str) -> str:
    name = _extract_business_name(prompt)
    lowered = prompt.lower()
    colors: list[str] = []
    for token in (
        "pink",
        "cream",
        "gold",
        "yellow",
        "black",
        "silver",
        "blue",
        "purple",
        "cyan",
        "red",
        "green",
        "white",
    ):
        if token in lowered:
            colors.append(token)
    color_css = ", ".join(colors) if colors else "slate, sky"
    mood = "elegant" if "elegant" in lowered else "bold"
    if "futuristic" in lowered:
        mood = "futuristic"
    if "trustworthy" in lowered:
        mood = "trustworthy"

    hero = f"{mood} one-page website for {name}."
    detail = "Generated from local model test double."
    lowered_name = name.lower()
    if "locksmith" in lowered_name:
        hero = f"{name} emergency locksmith security response."
        detail = (
            "Urgent trustworthy lockout, rekey, key security, and emergency service."
        )
    elif "flowers" in lowered_name or "flor" in lowered_name:
        hero = f"{name} elegant bouquet and floral studio."
        detail = "Seasonal blooms, bouquet design, and same-day floral delivery."
    elif "detailing" in lowered_name:
        hero = f"{name} bold automotive detailing and shine packages."
        detail = "Interior reset, exterior gloss, and mobile detailing appointments."
    elif "arcade" in lowered_name:
        hero = f"{name} neon retro arcade experience."
        detail = "Retro game grid, high scores, and futuristic arcade nights."
    elif any(
        token in lowered
        for token in (
            "grooming",
            "pet grooming",
            "dog grooming",
            "dog wash",
            "trim",
            "fur",
            "paw",
        )
    ):
        hero = f"{name} pet grooming, bath, trim, and fur care."
        detail = "Friendly dog grooming with bath, wash, paw tidy, coat care, and easy booking."

    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{name}</title>
    <style>
      body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, {color_css}); color: #111; }}
      .hero {{ max-width: 920px; margin: 2rem auto; padding: 1.5rem; border-radius: 14px; background: rgba(255,255,255,0.82); }}
      h1 {{ margin: 0 0 0.5rem; letter-spacing: 0.02em; }}
    </style>
  </head>
  <body>
    <main class=\"hero\">
      <h1>{name}</h1>
            <p>{hero}</p>
            <p>One-page website experience tuned for {name}.</p>
            <p>{detail}</p>
    </main>
  </body>
</html>"""


def _use_fake_local_model(
    monkeypatch, *, should_fail: bool = False, reason: str = "invalid_html"
) -> None:
    async def _fake_generate(
        self,
        *,
        question: str,
        filename: str,
        language: str,
        previewable: bool,
        apply_requested: bool,
        business_name: str,
        style_hints: dict[str, list[str]],
        layout_hints: list[str],
    ) -> tuple[str, str]:
        if should_fail:
            raise RuntimeError(reason)
        return _make_fake_model_html(question), "fake-code-model:test"

    monkeypatch.setattr(
        "core.brain.answer_contract.AnswerContract._generate_artifact_with_local_model",
        _fake_generate,
    )

















































































































































__all__ = [name for name in globals() if not name.startswith("__")]
