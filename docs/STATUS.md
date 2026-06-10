# XV7 Stable Checkpoint

Date: 2026-06-10  
Branch: main  
Stable commit: dbf34ec  
Passing CI run: 27293921559  

## Current State

XV7 has a working GitHub Actions pipeline.

Verified:

- Working tree clean
- Local branch synced with origin/main
- CI passes
- Ruff lint passes
- Ruff format check passes
- Mypy passes
- Pytest smoke tests pass
- Docker build passes

## Fixes Completed

- Removed dependency conflict caused by pytest-httpx/httpx mismatch
- Added smoke tests
- Fixed repo-local data paths outside Docker
- Added manual workflow dispatch
- Restored full CI workflow
- Set PYTHONPATH for CI tests
- Verified full CI success

## Known Debt

- Local folder nesting is confusing: `X:\XV7\xv7`
- Git history has duplicate workflow commits from recovery
- Current tests are only smoke-level
- Memory design still needs a real architecture pass
- Runtime honesty still needs review
- API key enforcement still needs review
- Open WebUI integration still needs verification
- Microphone/voice pipeline still needs design and implementation
- GPU/Ollama runtime proof still needs hard validation

## Next Engineering Phase

Phase B1: Runtime Honesty and Security Foundation

Goals:

1. Remove misleading/fake telemetry
2. Enforce API key behavior honestly
3. Prove Ollama model availability
4. Prove GPU visibility where available
5. Prevent silent memory failures
6. Separate XV7 platform identity from Xoduz assistant identity
7. Add tests for each runtime claim

## Rule Going Forward

No fake pass states.
No fake telemetry.
No silent fallbacks.
No cloud fallback unless explicitly configured.
No memory writes without receipt or error.
No feature claim without a test or health check.
