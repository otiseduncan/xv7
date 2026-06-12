# CODE Lane Index

This is the main map for CODE lane work.

Use this page first when asking: "what is next?"

## Status Legend

- planned
- prompt written
- implemented
- tested
- verified

## CODE Lane Map (01-21)

| ID | Title | Status | Short Description |
| --- | --- | --- | --- |
| CODE-01 | Workspace Context Map | implemented | Read-only workspace inspection and stack map. |
| CODE-02 | Patch Planner | implemented | Read-only planner action fully wired into operator registry; ready for action queue integration. |
| CODE-03 | Approved Patch Apply | implemented | Approval-gated patch application inside repo root; no commit or push. |
| CODE-04 | Test Runner | implemented | Allowlisted local validation runner with compact receipts. |
| CODE-05 | Diff Summary | implemented | Read-only git diff summary with changed files, risk flags, and next action. |
| CODE-06 | Commit Helper | prompt written | Approval-gated commit helper with safety warnings. |
| CODE-07 | App Builder Mode | prompt written | Controlled app-builder interaction lane. |
| CODE-08 | Workflow Learning | prompt written | Capture and apply operator workflow preferences safely. |
| CODE-09 | CI Parity Gate | prompt written | Ensure local and CI gate parity. |
| CODE-10 | App Builder Gauntlet | prompt written | Validation gauntlet for app-builder loop reliability. |
| CODE-11 | Agent Eval Harness | prompt written | Eval harness for code/operator reliability checks. |
| CODE-12 | Memory-to-Workflow Promotion | prompt written | Promote approved corrections into workflow rules. |
| CODE-13 | Operator Command Center | prompt written | Calm command center UI for inspect-plan-approve loop. |
| CODE-14 | Local Bridge Health | prompt written | Local bridge health checks and honest fallback states. |
| CODE-15 | App Template Registry | prompt written | Registry for approved app templates and usage constraints. |
| CODE-16 | Implementation Session Protocol | prompt written | Session protocol for implementation work. |
| CODE-17 | Safe Repo Writer | prompt written | Bound file-writing behavior with strict safety checks. |
| CODE-18 | Context Source Router | prompt written | Route answers to correct source with confidence. |
| CODE-19 | Operator UI Action Queue | prompt written | Pending mutation queue with explicit approval lifecycle. |
| CODE-20 | Beta Readiness Gate | prompt written | Testable checklist for beta-ready declaration. |
| CODE-21 | Session Notes | prompt written | Session scratchpad and continuity notes for CODE lane. |

## Recommended Build Order

1. CODE-01 Workspace Context Map
2. CODE-02 Patch Planner
3. CODE-03 Approved Patch Apply
4. CODE-04 Test Runner
5. CODE-05 Diff Summary
6. CODE-06 Commit Helper
7. CODE-13 Operator Command Center
8. CODE-18 Context Source Router
9. CODE-19 Operator UI Action Queue
10. CODE-14 Local Bridge Health
11. CODE-09 CI Parity Gate
12. CODE-16 Implementation Session Protocol
13. CODE-17 Safe Repo Writer
14. CODE-12 Memory-to-Workflow Promotion
15. CODE-08 Workflow Learning
16. CODE-07 App Builder Mode
17. CODE-15 App Template Registry
18. CODE-10 App Builder Gauntlet
19. CODE-11 Agent Eval Harness
20. CODE-20 Beta Readiness Gate
21. CODE-21 Session Notes

## What To Do Next

Current next recommended implementation target: CODE-06 Commit Helper.

CODE-01 is implemented as a read-only workspace map action with registry exposure and tests.

CODE-02 is implemented as a read-only `patch_plan` action with registry exposure and tests.

CODE-03 is implemented as an approval-gated `apply_approved_patch` action. It denies unapproved changes, rejects outside-root paths, writes only inside the repo root, returns changed files and compact diff data, and never commits or pushes.

CODE-04 is implemented as a read-only `test_runner` action. It runs only allowlisted validation presets, blocks raw shell execution, validates single pytest targets, returns compact command receipts, and is wired through the operator registry.

CODE-05 is implemented as a read-only `diff_report` action. It runs only known git status/diff commands, returns changed files, compact diff stats, risk flags, and a next recommended action without mutating files or git state.

After CODE-01 through CODE-05 are implemented and stable, run the gauntlet in:

- docs/CODE_OPERATOR_GAUNTLET.md

Then advance to command center/context router/queue hardening (CODE-13, CODE-18, CODE-19).
