# Phase 2: `core/main.py` split plan

Status: started after CI run #351 went green.

## Purpose

This phase reduces `core/main.py` without changing runtime behavior. The goal is to make Xoduz smaller, safer to modify, and easier to test before any new feature work continues.

## Guardrails

- Do not change user-visible behavior in Phase 2 extraction commits.
- Do not start website design rewrites during this phase.
- Do not expand memory behavior during this phase.
- Keep each extraction small enough to validate with the existing full gate.
- Every extraction must preserve the current 885-test baseline.
- New source modules should target 300-500 lines and stay below 800 lines unless explicitly justified.
- Existing large files may shrink, but they should not grow.

## Current verified gate

The latest validated CI run shows:

- Lint & Type Check: pass
- Unit & Integration Tests: pass
- Docker Build: pass

Local and CI test baseline:

- 885 tests collected
- 885 tests passing after the learned-rule routing fix

## Split order

### Step 2.1 — Extract request and response schemas

Move FastAPI/Pydantic request and response models out of `core/main.py` into:

- `core/api/schemas.py`

Expected contents:

- session request models
- runtime model/profile request models
- brain record mutation request models
- operator request models
- any small response-shape models currently declared in `core/main.py`

Acceptance gate:

```powershell
python scripts/check_architecture_size.py
python -m ruff check core/
python -m ruff format --check core/
python -m mypy core/ --ignore-missing-imports
python -m pytest tests/ -v --tb=short --asyncio-mode=auto
```

### Step 2.2 — Extract brain record serialization and hygiene helpers

Move brain record helper functions out of `core/main.py` into:

- `core/api/brain_record_serialization.py`
- `core/api/brain_hygiene.py` if separation is cleaner

Expected contents:

- brain record JSON serialization helpers
- split/relevance helpers
- hygiene summary helpers
- record filtering/sorting helpers used by API routes

### Step 2.3 — Extract learning-rule/session-policy helpers

Move learned-rule and session-policy helpers out of `core/main.py` into:

- `core/services/session_learning_policy.py`

Expected contents:

- learned-rule detection
- learned-rule receipt construction helpers
- proof-required learned-rule handling
- speech-act to learning-layer mapping if not shared elsewhere

### Step 2.4 — Extract auto-memory route flow

Move auto-memory orchestration out of `core/main.py` into:

- `core/services/auto_memory_flow.py`

Expected contents:

- auto-memory intake decision handling
- active memory save flow
- pending-review memory flow
- clarification/protected-memory responses
- memory receipt metadata assembly

### Step 2.5 — Extract route modules

Move API endpoint groups into focused route modules:

- `core/api/session_routes.py`
- `core/api/brain_routes.py`
- `core/api/operator_routes.py`
- `core/api/runtime_routes.py`

`core/main.py` should become an app composition file only:

- app creation
- middleware
- lifespan
- dependency wiring
- router registration

## Stop conditions

Stop and repair before continuing if any of these occur:

- any test count changes unexpectedly
- any route behavior changes outside the intended extraction
- any generated/vendor/runtime output becomes tracked
- `core/main.py` grows during an extraction
- a new module exceeds the size guard policy without explicit justification

## Current next action

Begin Step 2.1 with a mechanical extraction of request/response schemas only. No behavior changes.
