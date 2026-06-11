# CODE-04 — Test Runner Action Prompt

## Purpose

Give Xoduz a safe, repeatable way to run the correct tests after she inspects or patches the repo.

This is the fourth step in the code-operator loop:

```text
inspect -> plan -> approve -> patch -> test -> report
```

CODE-04 does **not** decide what to change. It runs validation commands and returns honest proof.

---

## Build instruction for VS Code / local AI

Implement CODE-04 as a read-only validation action.

### Goal

Create a `test_runner` operator action that can run approved test commands from a controlled allowlist and return structured results.

### Files to inspect first

- `core/operator/registry.py`
- `core/operator/manager.py`
- `core/operator/schema.py`
- `core/operator/actions/`
- `tests/test_operator_readonly_actions.py`
- `tests/test_operator_registry.py`
- `.github/workflows/ci.yml`
- `package.json`
- `pyproject.toml`

### Required behavior

Add a read-only action named:

```text
test_runner
```

The action must support these preset test groups:

```text
unit_backend
lint_backend
frontend_app
ci_core
ci_full_safe
single_pytest
```

The action must **not** accept arbitrary shell commands from the user.

Instead, map presets to known commands:

```text
unit_backend:
  python -m pytest tests/ -v --tb=short --asyncio-mode=auto

lint_backend:
  python -m ruff check core/ tests/
  python -m ruff format --check core/ tests/

frontend_app:
  npm test -- public/app.test.js

ci_core:
  python -m ruff check core/
  python -m ruff format --check core/
  python -m mypy core/ --ignore-missing-imports
  python -m pytest tests/ -v --tb=short --asyncio-mode=auto

ci_full_safe:
  python -m ruff check core/ tests/
  python -m ruff format --check core/ tests/
  python -m mypy core/ --ignore-missing-imports
  python -m pytest tests/ -v --tb=short --asyncio-mode=auto
  npm test -- public/app.test.js

single_pytest:
  python -m pytest <validated test path> -v --tb=short --asyncio-mode=auto
```

### Safety rules

- Read-only action.
- No file mutation.
- No git mutation.
- No Docker destructive commands.
- No raw user-provided shell string execution.
- Allow only known presets.
- For `single_pytest`, only allow paths under `tests/` ending in `.py` or containing `::` test selectors.
- Deny paths containing `..`, absolute drive paths, shell separators, pipes, redirects, backticks, `$()`, `;`, `&&`, or `||`.

### Output shape

Return an `OperatorActionResult` with:

```json
{
  "preset": "ci_core",
  "commands": ["..."],
  "passed": true,
  "failed_command": null,
  "exit_codes": [0, 0, 0, 0],
  "stdout_summary": "compact summary",
  "stderr_summary": "compact error summary",
  "duration_ms": 1234
}
```

### Chat behavior

When the user says:

```text
run the tests
run the backend tests
run the app test
run CI locally
validate this patch
```

Xoduz should route to `test_runner`, choose the safest matching preset, and include a compact receipt.

If the request is ambiguous, default to `ci_core` for backend work and `frontend_app` for frontend work when the patch touches `public/`.

### Tests to add

Add tests proving:

- `test_runner` is registered.
- `test_runner` is read-only.
- unknown preset is denied.
- `single_pytest` blocks unsafe paths.
- `single_pytest` allows a safe test selector.
- successful command produces `passed: true`.
- failing command produces `passed: false` and identifies `failed_command`.
- natural-language routing can route “run the tests” to the action.

### Acceptance

- `python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto` passes.
- `python -m pytest tests/test_operator_registry.py -v --tb=short --asyncio-mode=auto` passes.
- `python -m ruff check core/ tests/` passes.
- No mutation occurs when test_runner runs.

---

## Done means

Xoduz can run validation without guessing, without fake proof, and without turning user text into arbitrary shell execution.
