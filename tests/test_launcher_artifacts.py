"""Tests for local launcher artifacts.

Verifies that the scripts and documentation referenced in
docs/LOCAL_RUN.md actually exist and contain the expected references.
These are filesystem and content checks — no PowerShell execution,
no network calls, no live service probes.
"""

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------------
# Repo root fixture
# ---------------------------------------------------------------------------


# Tests run from the repo root (pytest is invoked from there).  Walk up from
# this file's location to find the root that contains docker-compose.yml.
def _find_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        if (candidate / "docker-compose.yml").exists():
            return candidate
    raise FileNotFoundError(
        "Cannot locate repo root (no docker-compose.yml found in parent tree)."
    )


_REPO_ROOT = _find_repo_root()
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_DOCS_DIR = _REPO_ROOT / "docs"


# ---------------------------------------------------------------------------
# Script existence checks
# ---------------------------------------------------------------------------


def test_check_readiness_script_exists() -> None:
    """scripts/check_readiness.py must exist — it is referenced in LOCAL_RUN.md."""
    assert (_SCRIPTS_DIR / "check_readiness.py").is_file(), (
        "scripts/check_readiness.py is missing"
    )


def test_launcher_script_exists() -> None:
    """scripts/start_xv7_local.ps1 must exist — it is the documented launcher."""
    assert (_SCRIPTS_DIR / "start_xv7_local.ps1").is_file(), (
        "scripts/start_xv7_local.ps1 is missing"
    )


def test_init_env_script_exists() -> None:
    """scripts/init_xv7_env.ps1 must exist for first-run secret bootstrap."""
    assert (_SCRIPTS_DIR / "init_xv7_env.ps1").is_file(), (
        "scripts/init_xv7_env.ps1 is missing"
    )


# ---------------------------------------------------------------------------
# LOCAL_RUN.md existence and content checks
# ---------------------------------------------------------------------------


def test_local_run_doc_exists() -> None:
    """docs/LOCAL_RUN.md must exist."""
    assert (_DOCS_DIR / "LOCAL_RUN.md").is_file(), "docs/LOCAL_RUN.md is missing"


def _local_run_text() -> str:
    return (_DOCS_DIR / "LOCAL_RUN.md").read_text(encoding="utf-8")


def test_local_run_doc_references_check_readiness() -> None:
    """LOCAL_RUN.md must reference check_readiness.py."""
    assert "check_readiness.py" in _local_run_text()


def test_local_run_doc_references_launcher() -> None:
    """LOCAL_RUN.md must reference start_xv7_local.ps1."""
    assert "start_xv7_local.ps1" in _local_run_text()


def test_local_run_doc_references_init_script() -> None:
    """LOCAL_RUN.md must reference init_xv7_env.ps1."""
    assert "init_xv7_env.ps1" in _local_run_text()


def test_local_run_doc_references_force_rotate() -> None:
    """LOCAL_RUN.md must describe intentional secret rotation."""
    assert "-ForceRotate" in _local_run_text()


def test_local_run_doc_mentions_xv7_api_key() -> None:
    """LOCAL_RUN.md must document XV7_API_KEY for local dev."""
    assert "XV7_API_KEY" in _local_run_text()


def test_local_run_doc_mentions_core_api_key() -> None:
    """LOCAL_RUN.md must document CORE_API_KEY for Docker mode."""
    assert "CORE_API_KEY" in _local_run_text()


def test_local_run_doc_mentions_core_port() -> None:
    """LOCAL_RUN.md must mention the default Core API port (8000)."""
    assert "8000" in _local_run_text()


def test_local_run_doc_mentions_webui_port() -> None:
    """LOCAL_RUN.md must mention the default Open WebUI port (8080)."""
    assert "8080" in _local_run_text()


def test_local_run_doc_mentions_ollama_port() -> None:
    """LOCAL_RUN.md must mention the default Ollama port (11434)."""
    assert "11434" in _local_run_text()


def test_local_run_doc_mentions_docker_compose_down() -> None:
    """LOCAL_RUN.md must document how to stop the stack."""
    assert "docker compose down" in _local_run_text()


def test_local_run_doc_does_not_claim_api_key_value() -> None:
    """LOCAL_RUN.md must not hardcode any API key value."""
    text = _local_run_text()
    # Keys generated with secrets.token_hex(32) are 64-char hex strings.
    # Ensure no 64-char hex string appears in the docs.
    import re

    hardcoded = re.findall(r"\b[0-9a-f]{64}\b", text)
    assert not hardcoded, (
        f"LOCAL_RUN.md appears to contain a hardcoded secret: {hardcoded}"
    )


# ---------------------------------------------------------------------------
# Launcher script content checks (no execution — text only)
# ---------------------------------------------------------------------------


def _launcher_text() -> str:
    return (_SCRIPTS_DIR / "start_xv7_local.ps1").read_text(encoding="utf-8")


def test_launcher_runs_readiness_check() -> None:
    """Launcher must invoke check_readiness.py."""
    assert "check_readiness.py" in _launcher_text()


def test_launcher_references_init_script_on_preflight_failure() -> None:
    """Launcher must direct users to init_xv7_env.ps1 when secrets are invalid."""
    assert "init_xv7_env.ps1" in _launcher_text()


def test_launcher_runs_docker_compose_up() -> None:
    """Launcher must run docker compose up -d."""
    assert "docker compose up -d" in _launcher_text()


def test_launcher_polls_health_endpoint() -> None:
    """Launcher must probe /health before declaring success."""
    assert "/health" in _launcher_text()


def test_launcher_does_not_claim_ollama_verified() -> None:
    """Launcher must not assert Ollama is reachable without an actual check."""
    text = _launcher_text().lower()
    # The word 'verified' must not follow 'ollama' on the same line in a
    # success-claim context.  We allow the word in a warn/comment context.
    # Simple heuristic: 'ollama' and 'verified' must not appear together
    # on any non-comment, non-warn line.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # comments are fine
        if "warn" in stripped:
            continue  # warn lines are fine
        if "ollama" in stripped and "verified" in stripped:
            raise AssertionError(
                f"Launcher claims Ollama is verified outside of a warning context:\n  {line}"
            )


def test_launcher_exits_nonzero_on_compose_failure() -> None:
    """Launcher must exit 1 when docker compose fails."""
    assert "exit 1" in _launcher_text()


def test_launcher_prints_repo_root() -> None:
    """Launcher must print the detected repo root."""
    text = _launcher_text()
    assert "Repo root" in text or "repoRoot" in text
