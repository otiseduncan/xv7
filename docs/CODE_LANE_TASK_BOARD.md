# CODE Lane Task Board

This file is the practical task board for getting Xoduz to operate like a coding assistant.

Primary map: `docs/CODE_LANE_INDEX.md`

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

## Milestone: CODE-13 Operator Command Center

Status: not started

### Required implementation

- [ ] Add calm command center panel for operator loop controls.
- [ ] Show mode: normal/operator/approval pending.
- [ ] Show workspace root and last action receipt.
- [ ] Show pending action queue summary.
- [ ] Keep advanced details behind disclosure.
- [ ] Keep read-only actions usable without approval.
- [ ] Block mutation actions without explicit approval.
- [ ] Add tests for unavailable/offline honest states.

### Acceptance

- [ ] Layout and backend data contract are defined.
- [ ] Safe action states are enforced.
- [ ] Unavailable states are explicit and honest.
- [ ] UI remains calm by default.

## Milestone: CODE-18 Context Source Router

Status: not started

### Required implementation

- [ ] Define source routing table for answer selection.
- [ ] Add confidence levels (high/medium/low).
- [ ] Enforce inspect-first rules for repo/CI/test-state prompts.
- [ ] Add clarification and unavailable branches.
- [ ] Add compact source pins/receipts (no proof spam).
- [ ] Add tests for routing decisions.

### Acceptance

- [ ] Routing table is implemented/documented.
- [ ] Confidence policy is visible and testable.
- [ ] No-inspection-required cases are blocked from guessing.
- [ ] Example prompts route to expected sources.

## Milestone: CODE-19 Operator UI Action Queue

Status: not started

### Required implementation

- [ ] Add pending mutation queue in UI/runtime state.
- [ ] Include fields: action id/name, targets, risk, reason, diff preview, tests, approval status, timestamps.
- [ ] Support actions: approve/reject/edit request/read-only preview/apply.
- [ ] Ensure queue survives refresh when possible.
- [ ] Deny expired or unapproved applies.
- [ ] Add queue state transition tests.

### Acceptance

- [ ] Schema is implemented/documented.
- [ ] UI states are compact and clear.
- [ ] Expired/missing approval denial is explicit.
- [ ] Mutation never runs from suggestion alone.

## Milestone: CODE-20 Beta Readiness Gate

Status: not started

### Required implementation

- [ ] Define beta-readiness checklist by gate domain.
- [ ] Add statuses: required/partial/optional/blocked/verified.
- [ ] Add minimum beta bar and hard blockers.
- [ ] Attach concrete verification commands/checks.
- [ ] Add reporting format for readiness status.

### Acceptance

- [ ] Beta readiness is testable, not vibe-based.
- [ ] Minimum beta bar is explicit.
- [ ] Blockers are explicit.
- [ ] Commands/checks are runnable.

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

## Coherent Build Order (Current)

1. CODE-01 Workspace Context Map
2. CODE-02 Patch Planner
3. CODE-03 Approved Patch Apply
4. CODE-04 Test Runner
5. CODE-05 Diff Summary
6. CODE-06 Commit Helper
7. CODE-13 Operator Command Center
8. CODE-18 Context Source Router
9. CODE-19 Operator UI Action Queue
10. CODE-20 Beta Readiness Gate
11. APP-01 First App Builder Flow