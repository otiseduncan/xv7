# Next Steps: Code Operator Loop

This is the next build lane after the COMM-06 Brain Records stabilization work.

The goal is to turn Xoduz from a chat UI with memory/context into a controlled local builder that can inspect the repo, plan a change, apply approved patches, run tests, and report exactly what happened.

## North-star target

A normal user request like this:

```text
Xoduz, build me a simple inventory app.
```

should eventually become this safe execution loop:

```text
1. Understand the request.
2. Inspect the current workspace.
3. Identify files and stack.
4. Produce an implementation plan.
5. Ask for approval before mutation.
6. Apply a bounded patch inside the repo.
7. Run targeted tests.
8. Report changed files, test results, and next steps.
9. Offer commit/push only after verification.
```

## Current foundation already present

The project already has the pieces that make this realistic:

- FastAPI core runtime.
- Browser UI.
- Brain Records, Active Focus, Memory, Knowledge, and Verified Status separation.
- Compact receipts and a per-message explanation drawer.
- Operator Mode safety concepts.
- Read-only operator actions.
- Existing tests around operator behavior and chat quality.
- GitHub Actions CI.

What is missing is the complete code-work loop.

## Build order

Do not jump straight to autonomous editing. Build in this order.

### CODE-01 — Workspace Context Map

Purpose: let Xoduz understand the repo before changing anything.

Required output:

- repo root
- branch
- clean/dirty status
- changed files
- top-level folders
- detected stack
- key files
- test commands
- docker/runtime hints
- safety summary

This must be read-only.

### CODE-02 — Patch Planner

Purpose: turn a user request into a concrete implementation plan.

Required output:

- user goal
- likely files involved
- proposed changes
- risk level
- tests to run
- approval requirement
- rollback notes

This must also be read-only.

### CODE-03 — Approved Patch Apply

Purpose: apply code changes only after explicit approval.

Required behavior:

- Operator Mode must be ON.
- The patch must be staged/approved first.
- All writes must stay inside repo root.
- Before/after diff must be captured.
- Test commands must be returned or run.
- Failed tests must be reported honestly.

### CODE-04 — Test Runner

Purpose: standardize local validation.

Required commands:

- ruff check
- ruff format check
- mypy
- pytest
- frontend vitest when public files changed
- docker build when Docker/runtime files changed

### CODE-05 — Diff and Result Summary

Purpose: make Xoduz explain what changed without dumping noise.

Required output:

- changed files
- human summary
- tests run
- tests skipped and why
- risks
- next action

### CODE-06 — Commit Helper

Purpose: help Otis commit after tests pass.

Required behavior:

- never commit without approval
- never force push
- summarize staged files
- suggest commit message
- block commit if tests are failing unless user explicitly overrides

## Strict safety rules

1. No write outside repo root.
2. No mutation without approval.
3. No hidden destructive commands.
4. No fake test claims.
5. No claiming a repo check happened unless the action actually ran.
6. No broad context guesses when a workspace inspection is available.
7. Receipts stay compact; details go into diagnostics/drawer.

## UX rule

The default chat answer should be simple:

```text
I inspected the workspace. The repo is React/static frontend + FastAPI core + Docker. I found 3 files likely involved. I have a patch plan ready. Want me to stage it?
```

The drawer/receipt should hold the details:

```text
workspace_map: success
patch_plan: success
files_considered: [...]
tests_recommended: [...]
mutation_required: true
approval_required: true
```

## When this lane is complete

Xoduz should be able to safely handle this pattern:

```text
Otis: Check the repo and tell me what is left.
Xoduz: Runs workspace_map and summarizes.

Otis: Build the next piece.
Xoduz: Produces patch_plan.

Otis: Approved.
Xoduz: Applies patch, runs tests, reports result.
```

That is the line between a chat assistant and a builder.