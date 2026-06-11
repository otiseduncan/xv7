# CODE-12 — Memory-to-Workflow Promotion Prompt

## Mission

Turn Otis's corrections and repeated instructions into reviewable workflow rules that Xoduz can use during future operator/coding work.

This is the bridge between memory and actual behavior.

Xoduz should not merely remember facts. She should learn operator workflows.

## Core problem

Today, Otis can correct Xoduz in chat:

```text
No, when I say repo check, inspect git status, failing CI, current branch, latest commits, and roadmap.
```

That correction should become a pending workflow rule, not vanish into chat history.

Future Xoduz behavior should then change after Otis approves it.

## Required behavior

When a user correction clearly describes a workflow preference, Xoduz should create a pending workflow rule.

Examples:

```text
When I say check the repo, inspect git status and CI first.
When I ask for a roadmap, use current repo state plus docs, not generic advice.
Do not call receipt chips proof by themselves.
When a tool is unavailable, say unavailable instead of guessing.
When I say build an app, use inspect-plan-approve-patch-test-report.
```

These should become structured records.

## Files to inspect first

Inspect and adapt to existing brain/runtime records structure:

```text
core/brain/records.py
core/brain/schema.py
core/brain/manager.py
core/main.py
tests/test_runtime_brain_records_api.py
tests/test_operator_chat_integration.py
docs/CODE_LANE_TASK_BOARD.md
```

## Proposed record shape

Use existing schema if possible. If new fields are needed, keep them small.

Suggested workflow record fields:

```json
{
  "record_id": "XV7-WORKFLOW-0001",
  "layer": "workflow",
  "status": "pending_review",
  "relevance_state": "current",
  "trigger_phrases": ["check the repo", "repo status", "where are we"],
  "workflow_steps": [
    "inspect git status",
    "inspect latest commits",
    "inspect CI status if available",
    "inspect roadmap docs",
    "answer with current state and next step"
  ],
  "applies_when": "operator asks for project/repo status",
  "source": "operator correction",
  "created_from_message_id": "...",
  "requires_approval": true
}
```

If the existing brain records cannot support this exact shape, store it in metadata without breaking current records.

## Required implementation

### 1. Correction detector

Add logic that detects correction/workflow phrases like:

```text
when I say...
from now on...
do not...
always...
stop doing...
that means...
next time...
```

The detector must be conservative. It should not convert every complaint into a rule.

### 2. Pending workflow creation

When detected, create a pending workflow record with:

- trigger phrase,
- behavior rule,
- source message,
- pending_review status,
- safe metadata,
- no immediate silent activation unless current design already supports approved auto-learning.

### 3. Approval path

Use existing Brain Records approval/reject UI/API where possible.

Otis should be able to approve, reject, edit/tune, or archive the workflow rule.

### 4. Runtime use

Once approved/current, workflow rules should influence operator routing and answer planning.

Example:

```text
User: check the repo
Xoduz: follows approved repo-check workflow instead of generic status text.
```

### 5. Receipts / metadata

When a workflow record affects an answer, metadata should include:

```text
workflow_record_ids
workflow_applied: true
workflow_name or trigger
```

Do not dump the full workflow into the normal visible answer unless the user asks.

## Safety requirements

- Do not store secrets.
- Do not store raw sensitive messages in visible records.
- Do not auto-promote protected or dangerous behaviors.
- Do not allow memory rules to bypass operator approval for mutations.
- Approved workflow can guide behavior, but cannot override safety policy.

## Required tests

Add or extend tests for:

1. A clear workflow correction creates a pending workflow record.
2. Random frustration does not create a workflow record.
3. Approved workflow is used on matching future prompt.
4. Rejected workflow is not used.
5. Workflow use appears in metadata/source pins.
6. Workflow rule cannot authorize mutation without operator approval.

## Acceptance commands

```powershell
python -m pytest tests/test_operator_chat_integration.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/test_runtime_brain_records_api.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/ -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```

## Definition of done

CODE-12 is done when Otis can correct Xoduz once, approve the generated workflow rule, and Xoduz uses that rule in a later matching request.

The first target workflow should be:

```text
repo check = inspect git state, recent commits, CI status, roadmap docs, and report current next step.
```

## Commit message

```text
feat: promote operator corrections into workflow rules
```
