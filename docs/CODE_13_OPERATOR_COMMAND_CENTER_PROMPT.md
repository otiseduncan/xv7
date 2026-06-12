# CODE-13 — Operator Command Center Prompt

## Purpose

Define the Operator Command Center UI/UX layer so Xoduz can run the code/operator loop in a calm, controlled, and honest way.

This prompt should produce a compact command center that supports:

- inspect
- plan
- approve
- patch
- test
- report
- commit helper

without default clutter.

## Prompt

```text
CODE-13 — Operator Command Center

You are working in the XV7/Xoduz repo.
Implement a calm Operator Command Center panel that supports the real operator loop:

inspect -> plan -> approve -> patch -> test -> report -> commit

Hard rules:
- Keep default UI calm and compact.
- Read-only actions are allowed without approval.
- Mutating actions require explicit approval.
- Show honest unavailable/degraded states when bridge/tools are offline.
- Do not pretend actions ran if they did not run.
- Keep receipts compact by default; disclose details on demand.

UI requirements:
1. Add a dedicated Operator Command Center panel/section.
2. Default visible fields:
   - current mode: normal / operator / approval pending
   - workspace root
   - last action receipt (compact)
   - pending action queue summary (count + highest risk)
3. Primary controls (compact):
   - Inspect
   - Plan
   - Approve
   - Run Tests
   - View Diff
   - Commit Helper
4. Advanced details must be hidden behind disclosure controls.
5. No giant debug dumps in default view.
6. If tool bridge or runtime is unavailable, show explicit unavailable state and reason.

State model requirements:
- mode: normal | operator | approval_pending | running | unavailable
- actions must be disabled when mode/tool state makes them unsafe
- read-only actions remain available when mutation path is unavailable
- approval_pending mode must visually block mutation controls until approval decision

Backend data contract requirements:
Define and consume a compact payload for command center status:

{
  "mode": "normal|operator|approval_pending|running|unavailable",
  "workspace_root": "...",
  "last_receipt": {
    "action_id": "...",
    "action_name": "...",
    "status": "success|failed|denied|unavailable",
    "summary": "..."
  },
  "pending_queue": {
    "count": 0,
    "highest_risk": "low|medium|high",
    "next_action_id": "..."
  },
  "capabilities": {
    "inspect": true,
    "plan": true,
    "approve": true,
    "patch": false,
    "run_tests": true,
    "view_diff": true,
    "commit_helper": true
  },
  "unavailable_reasons": []
}

Safety behavior requirements:
- Read-only actions can run without approval.
- Mutating actions always require explicit approval.
- If no approval, mutation actions return denied with clear receipt.
- If offline/unavailable, return unavailable/failure with clear limitation note.

Acceptance checks:
- Layout is defined and calm by default.
- Backend data shape is defined and consumed.
- Safe action states are defined and enforced.
- Unavailable states are visible and honest.
- Test checklist exists and can be run locally.

Validation commands:
- python -m pytest tests/ -v --tb=short --asyncio-mode=auto
- npm test -- public/app.test.js
- python -m ruff check core/ tests/
- python -m ruff format --check core/ tests/

Return:
- files changed
- summary of UI states implemented
- list of safety gates enforced
- exact test commands run and outcomes
```

## Test/Validation Checklist

- Command center renders with calm default state.
- Mode indicator updates correctly (normal/operator/approval pending).
- Read-only actions stay enabled when mutation path is blocked.
- Mutation actions are blocked without approval.
- Last receipt updates after each action.
- Queue summary updates when pending actions are created/resolved.
- Unavailable bridge/runtime shows explicit limitation text.
- Advanced details are hidden by default.

## Safety Notes

- Do not run mutation actions from model suggestion alone.
- Do not hide approval state.
- Do not label unavailable as success.
- Keep receipts compact in visible UI; place details in disclosure/drawer.
