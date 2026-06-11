# B7.3-B — FastAPI Lifespan Cleanup and npm Audit Documentation

## Status

B7.3-B completed with fresh command execution in this slice.

## Validation Command Results

- `python -m pytest -q`: 223 passed in 15.92s.
- `npm test -- --run`: 10 passed.
- `docker compose build xv7-core`: passed.
- `docker compose up -d --force-recreate xv7-core xv7-frontend`: passed.

## FastAPI Lifespan Migration

- Replaced deprecated `@app.on_event("startup")` and `@app.on_event("shutdown")` handlers in `core/main.py` with a FastAPI lifespan context manager.
- Preserved startup behavior:
	- `ensure_session_facts_table()`
	- `persistent_memory_manager.bootstrap_seed_records()`
- Preserved shutdown behavior:
	- `base_agent.aclose()`
	- `vector_store.aclose()`
- Added regression coverage for lifecycle behavior in `tests/test_main_lifespan.py`.

### Warning Status

- FastAPI `on_event` deprecation warning source in `core/main.py`: removed.
- Current backend run did not emit warnings in the test summary output.

## npm Audit Triage

- `npm audit` reports vulnerabilities in the Vite/Vitest development and test dependency chain, rooted in `esbuild`.
- Reported remediation path requires `npm audit fix --force`, which would upgrade to `vitest@4.1.8` (breaking major change).
- Decision: do not force-upgrade in B7.3-B.
- Safety check performed: `npm audit fix` (without force) made no safe non-breaking changes.

### Current Audit Snapshot

- 5 vulnerabilities total (4 moderate, 1 critical), associated with dev/test tooling chain.

## Live Smoke Checks (Post-Recreate)

- Check the repo: success (`repo_status`), branch `main`, working tree not clean, sync `ahead`.
- Is the runtime healthy?: success (`runtime_health`), health `ok`.
- Show the last operator receipt: success, last receipt references `runtime_health`.
- What operator actions have run?: success, returned recent action history references.

## Dependency Fix Decision

- Deferred force-based upgrade to avoid unplanned Vitest major migration in this slice.
- Follow-up should handle Vitest/Vite/esbuild compatibility as an explicit dependency-upgrade task with dedicated regression pass.

## Backend Full-Suite Status

- Previously interrupted state is closed out in this slice: full backend suite completed successfully (223 passed).

## B8 Readiness

- B8 is cleared to start.
- Note: npm audit findings remain documented and intentionally deferred until a planned compatibility-managed dependency upgrade.