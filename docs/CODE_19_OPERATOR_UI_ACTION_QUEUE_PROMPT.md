# CODE-19 — Operator UI Action Queue Prompt

## Purpose

Define the pending action queue and approval flow so proposed mutations are explicit, reviewable, and never auto-executed.

## Prompt

```text
CODE-19 — Operator UI Action Queue

You are working in XV7/Xoduz.
Implement a compact pending action queue and approval flow for mutation actions.

Critical rule:
Mutations must never run just because the model suggested them.
Only approved queued actions may apply.

Queue requirements:
- Compact queue view in UI.
- Queue survives refresh if possible (runtime/session persistence).
- Queue entries include approval state and expiry.

Queue schema:
{
  "action_id": "OP-...",
  "action_name": "...",
  "target_files": ["..."],
  "risk_level": "low|medium|high",
  "reason": "...",
  "diff_preview": "...",
  "tests_to_run": ["..."],
  "approval_status": "pending|approved|rejected|expired|applied",
  "created_at": "ISO-8601",
  "expires_at": "ISO-8601"
}

UI action requirements:
- approve
- reject
- edit request
- run read-only preview
- apply

Behavior rules:
- apply is disabled unless approval_status == approved and not expired
- expired actions are denied and must not mutate
- missing action_id returns honest not found/denied
- read-only preview can run before approval
- queue list should show newest first by default

Denial behavior:
- expired approval -> denied with explicit reason
- missing approval -> denied with explicit reason
- missing queue item -> failed/denied with explicit reason
- disallowed risk mode -> denied with explicit reason

Receipt requirements:
- each queue transition emits compact receipt
- include action_id, transition, status, timestamp
- visible chat remains compact; details in disclosure

Acceptance:
- schema is defined and implemented/documented
- UI states are defined (pending/approved/rejected/expired/applied)
- queue action tests are defined
- denial behavior for expired/missing approval is defined and verified

Validation commands:
- python -m pytest tests/ -v --tb=short --asyncio-mode=auto
- npm test -- public/app.test.js
- python -m ruff check core/ tests/
- python -m ruff format --check core/ tests/

Return:
- queue schema
- state transition table
- denial behavior table
- files changed
- tests run and outcomes
```

## Suggested State Transition Table

- pending -> approved (approve)
- pending -> rejected (reject)
- pending -> pending (edit request)
- pending -> pending (read-only preview)
- approved -> applied (apply)
- approved -> expired (time elapsed)
- pending -> expired (time elapsed)

## Test Checklist

- Queue item is created with required fields.
- Approve sets approval_status to approved.
- Reject sets approval_status to rejected.
- Expired item cannot be applied.
- Unapproved item cannot be applied.
- Missing queue item returns honest failure/denial.
- Queue survives page refresh/session reload (if persistence implemented).
