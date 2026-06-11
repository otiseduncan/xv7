# CODE Operator Build Plan

Status: active build lane
Target: make Xoduz operate as a safe local coding assistant.

## Goal

Build the reliable operator loop:

```text
inspect -> plan -> approve -> patch -> test -> report
```

This is the missing bridge between chat, memory, and real app building.

## Current foundation

XV7 already has the important base pieces:

- local core API
- frontend UI
- Docker runtime
- model routing
- brain records
- Active Focus
- Memory, Knowledge, and Verified Status separation
- Operator Mode safety model
- read-only scan actions
- basic file operation groundwork
- receipts and per-message details
- regression tests and CI

The next work is to make these pieces act as one workflow.

## Phase 1: Workspace awareness

### CODE-01: workspace_map

Add a read-only operator action that gives Xoduz a compact live map of the current repo.

It should report:

- repo root
- current branch
- dirty files
- untracked files
- top-level folders
- key files
- detected stack
- available test commands
- current operator capability flags

Natural-language triggers:

- check the repo
- where are we
- what's left
- inspect the project
- what can you see in this workspace

Acceptance:

- returns live repo information
- does not mutate files
- includes a receipt
- has tests

## Phase 2: Planning before editing

### CODE-02: patch_plan

Add a read-only action that turns a user request into a proposed implementation plan.

It should return:

- interpreted goal
- files likely involved
- proposed steps
- risks
- approval requirement
- tests to run
- rollback notes

Acceptance:

- no file writes
- honest uncertainty when inspection is incomplete
- clear test plan

## Phase 3: Controlled patching

### CODE-03: apply_patch

Add controlled patch application after approval.

Requirements:

- approval required
- writes stay inside repo root
- record changed files
- produce diff summary
- suggest or run tests
- report failures honestly

Acceptance:

- no approval means no write
- outside-root paths are denied
- successful patch returns changed files and test guidance

## Phase 4: Test runner

### CODE-04: run_tests

Add a safe test runner for allowed project commands.

Initial allowed commands:

- python ruff check
- python ruff format check
- python pytest suite
- npm frontend test

Acceptance:

- allowed commands run
- disallowed commands are denied
- output includes status, exit code, summary, and receipt

## Phase 5: Diff/report summary

### CODE-05: diff_summary

Make every code change explain itself.

It should report:

- changed files
- high-level summary
- risk flags
- test status
- next action

## Phase 6: Commit helper

### CODE-06: commit_helper

Only after CODE-01 through CODE-05 are stable, add a commit helper.

It should:

- show files to commit
- avoid generated junk
- suggest a message
- require approval
- not push by default

## Phase 7: App builder mode

### APP-01: app_request_intake

Turn a loose app idea into structured requirements.

Collect:

- app name
- purpose
- target user
- screens
- data entities
- required actions
- storage needs
- local or deployable target

### APP-02: local_app_scaffold

Start with one reliable stack:

```text
React frontend + FastAPI backend + local SQLite or JSON storage
```

Generate apps under:

```text
generated-apps/<safe-app-name>/
```

### APP-03: preview_and_iterate

Support the loop:

```text
build -> run -> screenshot or feedback -> patch -> test -> report
```

## Phase 8: Communication learning

### COMM-07: correction_learning

When Otis corrects Xoduz, convert the correction into a reviewable rule.

Examples:

- repo check workflow
- CI failure workflow
- answer style preference
- source/proof expectations

### COMM-08: workflow_learning

Store repeatable workflows with:

- trigger phrases
- steps
- required tools
- expected output
- safety boundaries

## Build order

1. CODE-01 workspace_map
2. CODE-02 patch_plan
3. CODE-03 apply_patch
4. CODE-04 run_tests
5. CODE-05 diff_summary
6. CODE-06 commit_helper
7. COMM-07 correction_learning
8. COMM-08 workflow_learning
9. APP-01 app_request_intake
10. APP-02 local_app_scaffold
11. APP-03 preview_and_iterate

## Success target

Xoduz reaches the next level when Otis can say:

```text
Inspect this repo and add a small feature.
```

And Xoduz can:

1. inspect live repo state
2. explain the plan
3. ask for approval when needed
4. patch files safely
5. run tests
6. summarize what changed
7. avoid claiming proof she does not have
