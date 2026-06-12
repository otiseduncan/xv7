# CODE 9E Build-Task Planning Lane

## Purpose

`/build-task` is a safe Operator-Mode planning entry point for natural-language repo build requests.

It is plan-only:
- No file mutation
- No patch application
- No commit or push
- No test execution

`/apply-patch` remains restricted to valid approved patch payloads.

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

## Guardrails

1. `/build-task` requires Operator Mode.
2. `/build-task` returns planning output only and must include:
   - task summary
   - files/directories inspected or recommended for inspection
   - likely files to change
   - tests to add or update
   - validation commands
   - risk notes
3. Every `/build-task` response must state:
   `No files were changed. No tests were run. No commit or push occurred.`
4. Next valid step must be explicit:
   - prepare a patch payload, or
   - use VS Code/Copilot to implement the plan.
5. `/build-task` must not claim implementation completion, test pass, commit, or push.
