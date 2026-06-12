# CODE-16 — Implementation Session Protocol Prompt

## Purpose

Turn Xoduz from a chat responder into a disciplined coding session partner.

This lane defines how a build session starts, runs, pauses, and closes. The goal is to prevent drift, prevent hidden work, and make every coding session follow the same inspect → plan → approve → patch → test → report loop.

## Operator outcome

When Otis says something like:

- "check the repo"
- "what are we doing next"
- "start the next build lane"
- "keep rocking"
- "write the next step"
- "build this feature"

Xoduz should enter a structured implementation session instead of answering loosely.

## Required behavior

### 1. Session start

On any implementation-style request, Xoduz must gather or refresh:

- current repo root
- current branch
- working tree status
- latest commit
- active roadmap lane
- active task prompt, if present
- known validation commands
- whether local bridge/operator tools are available

If live repo inspection is not available, Xoduz must say that plainly and switch to prompt-only mode.

### 2. Session state

Create a compact session object with:

```json
{
  "session_id": "IMPL-YYYYMMDD-HHMMSS",
  "mode": "inspect_plan_patch_test_report",
  "repo_root": "...",
  "branch": "...",
  "task_id": "CODE-XX",
  "goal": "...",
  "current_step": "inspect",
  "mutations_allowed": false,
  "approval_required": true,
  "validation_commands": [],
  "changed_files": [],
  "receipts": []
}
```

The session object can be stored in runtime/session state. It should not become permanent memory until the user approves promotion.

### 3. Session phases

Every session must follow these phases:

1. Inspect
2. Plan
3. Approval gate
4. Patch
5. Validate
6. Report
7. Optional commit/push
8. Close or continue

Skipping phases is allowed only for read-only questions.

### 4. User-facing response style

Keep the answer tight. Do not dump internal JSON in normal chat.

Preferred format:

```text
I inspected the repo.
Current lane: CODE-01 Workspace Map.
Next step: implement read-only workspace_map.
Approval needed before file writes.
```

### 5. Receipts

Each implementation session should attach compact receipts:

- source: repo/live/local/static
- files inspected
- tools used
- mutations performed
- tests run
- pass/fail result
- fallback used, if any

Receipts belong in the metadata drawer or a compact receipt chip, not in a giant answer body.

## Acceptance tests

Add tests proving:

- implementation session starts from natural language build prompts
- session starts read-only
- mutation is blocked before approval
- phase transitions are deterministic
- failure states are honest
- unavailable repo tools do not produce fake proof

## Suggested files

Likely files to inspect or modify:

- `core/operator/manager.py`
- `core/operator/registry.py`
- `core/operator/actions/`
- `core/conversation/` or equivalent chat routing layer
- `tests/test_operator_chat_integration.py`
- `tests/test_operator_readonly_actions.py`
- `tests/test_conversation_quality.py`

## Done when

Xoduz can start a coding session, state the current phase, refuse unapproved writes, and produce a clean session summary after validation.
