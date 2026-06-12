# Code 9C Builder Readiness

Date: 2026-06-12

## Purpose

Define the minimum safe and truthful operator build loop before retrying Code 9 endpoint work.

## Required Build Loop

1. Operator Mode must be enabled before any repo mutation.
2. Normal chat build prompts must be routed/refused, never auto-saved as memory or preference.
3. Xoduz must inspect existing files before writing changes.
4. Xoduz must generate a valid patch payload before `/apply-patch`.
5. `/apply-patch` must remain confirmation-gated.
6. `/run-tests` should be used for validation where possible.
7. Build reporting must be evidence-backed only:
   - Files changed from git/operator tool output.
   - Tests run from command output.
   - Commit SHA from git output.
   - Push result from git output.
8. If verified evidence is missing, no completion claim is allowed.

## Code 9D Build-Task Gate

1. `/apply-patch` is only for valid approved patch payloads.
2. Natural-language feature requests are not valid patch payloads.
3. If `/apply-patch` receives a natural-language build request, it must fail safely with an invalid payload receipt and no pending confirmation stage.
4. Xoduz may inspect and plan, but must not claim implementation success without verified operator metadata.
5. Do not retry Code 9 endpoint work until Code 9D tests are green and the app has been restarted on latest code.

## Repo Hygiene Rule

Generated test artifacts must not be source-controlled. In particular:

- `node_modules/.vite/vitest/results.json` is local-only runtime output.
- This file must not be tracked in git.
- `.gitignore` must block re-tracking of this path.

## Pre-Retry Validation

Run from repo root:

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest tests/test_operator_chat_integration.py tests/test_conversation_quality.py tests/test_operator_mode_b97.py
pytest
npm test -- public/app.code8.test.js
npm test
git status --short
```

## Pass Criteria

- Targeted and full Python tests pass.
- Frontend test commands pass.
- `git status --short` has no generated Vitest result noise.
- No unverified build-completion claims are emitted.
