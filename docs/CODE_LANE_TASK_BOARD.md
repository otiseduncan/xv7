# CODE Lane Task Board

This file is the practical task board for getting Xoduz to operate like a coding assistant.

## Milestone: CODE-01 Workspace Context Map

Status: not started

### Required implementation

- [ ] Create `core/operator/actions/workspace.py`.
- [ ] Add `workspace_map(...)` read-only action.
- [ ] Register action in operator registry.
- [ ] Add slash route `/workspace-map` if slash routes are centralized.
- [ ] Add natural-language route for:
  - `check the repo`
  - `where are we`
  - `what is left`
  - `inspect the project`
  - `what files matter here`
- [ ] Add tests.
- [ ] Add compact receipt shape.

### Acceptance

- [ ] Running workspace map does not mutate files.
- [ ] Returned payload includes repo root, branch, dirty files, top-level folders, stack, key files, and test commands.
- [ ] Normal chat can call it for repo-status style questions.
- [ ] Missing git or missing repo root is reported honestly.

## Milestone: CODE-02 Patch Planner

Status: not started

### Required implementation

- [ ] Create planner action or service.
- [ ] Input: user goal and optional workspace map.
- [ ] Output: planned files, change list, risk, tests, approval requirement.
- [ ] Must not write files.
- [ ] Must not stage git changes.
- [ ] Must not claim a patch was applied.
- [ ] Add tests.

### Acceptance

- [ ] `Build app mode` request returns a plan, not a mutation.
- [ ] Plan includes likely files and tests.
- [ ] Plan marks mutation as requiring approval.
- [ ] Plan works even if workspace map is partial.

## Milestone: CODE-03 Approved Patch Apply

Status: not started

### Required implementation

- [ ] Add staged patch object.
- [ ] Add approval flow.
- [ ] Add repo-root path guard.
- [ ] Add diff capture.
- [ ] Add rollback hint.
- [ ] Add test command suggestions.
- [ ] Add tests for approved and denied paths.

### Acceptance

- [ ] No approval means no write.
- [ ] Outside-root write is denied.
- [ ] Approved patch writes expected files only.
- [ ] Result includes diff summary and tests to run.

## Milestone: CODE-04 Test Runner

Status: not started

### Required implementation

- [ ] Add read-only/action-safe test runner.
- [ ] Run targeted tests based on changed files.
- [ ] Support full backend gate.
- [ ] Support frontend vitest gate.
- [ ] Support Docker build gate when Docker files change.
- [ ] Persist latest test result in operator history.

### Acceptance

- [ ] Test output is summarized, not dumped by default.
- [ ] Failures show exact failing test/assertion.
- [ ] Xoduz never says green unless command really passed.

## Milestone: CODE-05 Diff Summary

Status: not started

### Required implementation

- [ ] Add diff summary action.
- [ ] Summarize changed files.
- [ ] Identify generated files and test artifacts.
- [ ] Warn before committing unwanted artifacts.
- [ ] Add tests.

### Acceptance

- [ ] `what changed?` gives direct file summary.
- [ ] Generated junk like logs/cache is flagged.
- [ ] Output is compact with expandable details.

## Milestone: CODE-06 Commit Helper

Status: not started

### Required implementation

- [ ] Add commit-plan action.
- [ ] Add staged-file summary.
- [ ] Suggest commit message.
- [ ] Require approval before commit.
- [ ] Never force push.
- [ ] Add tests.

### Acceptance

- [ ] Xoduz can say: `I would commit these 3 files with this message.`
- [ ] User must approve before commit.
- [ ] If tests are failing, warning is explicit.

## Milestone: APP-01 First App Builder Flow

Status: blocked until CODE-01 through CODE-04 exist

### Required implementation

- [ ] Add app request intake.
- [ ] Support one blessed stack first.
- [ ] Recommended first stack: static/React frontend + FastAPI backend.
- [ ] Scaffold under `generated-apps/<app-name>`.
- [ ] Run local build/test command.
- [ ] Return preview instructions.

### Acceptance

- [ ] Prompt: `build me a simple inventory app` creates a plan.
- [ ] Approval applies scaffold.
- [ ] Tests/build run.
- [ ] Xoduz reports files and preview command.

## Daily working rule

Every new lane must follow this order:

```text
spec -> implementation -> tests -> local gate -> CI -> roadmap update
```

No more pushing feature code without a test target and a known fallback plan.