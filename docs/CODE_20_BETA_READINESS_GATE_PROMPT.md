# CODE-20 — Beta Readiness Gate Prompt

## Purpose

Define a testable gate for declaring Xoduz beta-ready.

Beta-ready must be based on observable checks, not vibes.

## Prompt

```text
CODE-20 — Beta Readiness Gate

You are working in XV7/Xoduz.
Define and implement/document a Beta Readiness Gate that determines whether Xoduz is beta-ready.

Do not use subjective language only.
Every gate item must have:
- status: required | partial | optional | blocked | verified
- clear evidence/check command
- pass/fail criteria

Required gate domains:
1. Communication gate
2. Brain/context gate
3. Operator safety gate
4. Repo coding loop gate
5. App builder gate
6. CI parity gate
7. Local bridge gate
8. UI calmness gate
9. Memory/workflow learning gate
10. Honest failure/unavailable gate

Checklist structure:
{
  "gate": "communication",
  "status": "required|partial|optional|blocked|verified",
  "evidence": "...",
  "check_command": "...",
  "pass_criteria": "...",
  "last_checked_at": "ISO-8601"
}

Minimum beta bar (must all pass):
- operator mutation approval gating works
- inspect -> plan -> approve -> patch -> test -> report loop works locally
- failure/unavailable states are honest
- receipts/source pins are compact and accurate
- core regression suites pass

Not beta-ready if (blockers):
- mutation can run without approval
- test/CI claims can be made without proof
- context routing chooses stale/hallucinated source over live required source
- unreadable/cluttered operator UI blocks normal operation
- bridge offline states are shown as success

Suggested checks/commands:
- python -m pytest tests/ -v --tb=short --asyncio-mode=auto
- npm test -- public/app.test.js
- python -m ruff check core/ tests/
- python -m ruff format --check core/ tests/
- docker compose config
- operator gauntlet walkthrough checks

Acceptance:
- beta readiness is testable and documented
- minimum beta bar is explicit
- hard blockers are explicit
- check commands are listed and runnable

Return:
- readiness checklist table
- current status summary by gate
- blockers list
- exact commands used for verification
```

## Suggested Readiness Checklist Template

| Gate | Status | Evidence | Check Command | Pass Criteria |
| --- | --- | --- | --- | --- |
| Communication | required | receipts and answer clarity checks | npm test -- public/app.test.js | compact, honest answer + source behavior |
| Brain/Context | required | review/history/now correctness | python -m pytest tests/test_runtime_brain_records_api.py -v --tb=short --asyncio-mode=auto | context states correct and deterministic |
| Operator Safety | required | approval gate behavior | python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto | no unapproved mutation |
| Repo Coding Loop | required | inspect-plan-approve-patch-test-report flow | python -m pytest tests/ -v --tb=short --asyncio-mode=auto | loop executes with honest receipts |
| App Builder | partial | app mode plan + scaffold checks | npm test -- public/app.test.js | app-builder path is controlled and tested |
| CI Parity | required | local vs CI equivalence | python -m pytest tests/ -v --tb=short --asyncio-mode=auto | local gate matches CI gate |
| Local Bridge | required | bridge health and fallback honesty | python -m pytest tests/ -v --tb=short --asyncio-mode=auto | offline/failed states are explicit |
| UI Calmness | required | operator and brain panel control budget | npm test -- public/app.test.js | no cluttered default action overload |
| Memory/Workflow Learning | partial | promotion/review flow checks | python -m pytest tests/ -v --tb=short --asyncio-mode=auto | learning is reviewable and safe |
| Honest Unavailable | required | negative-path truthfulness | python -m pytest tests/ -v --tb=short --asyncio-mode=auto | no fake success/proof |
