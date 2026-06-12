# CODE 9F Scope-Aware Build-Task Planning

## Purpose

`/build-task` is a safe planning-only entry point for natural-language build requests.

It must not mutate files, apply patches, run tests, commit, push, or save the request as memory, knowledge, workflow habit, or communication preference.

## Scope-Aware Planning

Planning must match the request surface:

- `/runtime` endpoint tasks should recommend runtime API files and runtime endpoint tests.
- Operator command tasks should recommend operator manager, registry, and operator tests.
- Frontend/browser tasks should recommend public UI files and frontend tests.
- Docs-only tasks should stay inside docs and runbook files.

Wrong-file plans are planning failures even when the command remains mutation-safe.

## Intended Build Loop

```text
/build-task natural-language request
-> structured Build Plan only
-> human/VS Code/Copilot or future patch generator creates valid patch payload
-> /apply-patch valid payload
-> confirmation
-> /run-tests
-> verified report
```

## Required Output

Every `/build-task` response should include:

- Task summary
- Reason for file selection
- Files/directories inspected or recommended for inspection
- Likely files to change
- Tests to add/update
- Validation commands
- Risk notes
- Explicit no-side-effects statement:
  `No files were changed. No tests were run. No commit or push occurred.`
- Next valid operator step
