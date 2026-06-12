# CODE-17 — Safe Repo Writer Prompt

## Purpose

Give Xoduz a controlled writer that can create, update, and delete files inside the repository without becoming dangerous, sloppy, or confusing.

This is the file-mutation layer under the larger coding loop.

## Rule

Xoduz may only write when all of these are true:

1. The user has requested or approved a mutation.
2. Operator Mode or an equivalent approval gate allows the mutation.
3. The target path is inside the repo root.
4. The target path is not denied by policy.
5. A before/after diff can be produced.
6. The mutation can be described in a compact receipt.

No approval, no write.

## Writer operations

Implement a small set first:

- `write_file`
- `append_file`
- `replace_in_file`
- `delete_file`
- `create_directory`
- `apply_unified_patch`

Do not start with a giant general-purpose shell executor.

## Required protections

### Path safety

Reject:

- paths outside repo root
- absolute paths outside the workspace
- `..` traversal escaping the root
- `.git/` writes
- runtime secrets
- `.env` overwrite unless explicitly approved and redacted
- generated cache directories unless specifically requested

### Diff safety

Every write result must include:

- changed files
- operation type
- line count before/after when possible
- short diff summary
- rollback hint
- whether tests were run

### Approval safety

For any mutation, create a pending action first:

```json
{
  "action": "write_file",
  "path": "...",
  "risk": "low|medium|high",
  "requires_approval": true,
  "summary": "..."
}
```

Only execute after the user approves.

## Natural language routing

Route these to safe repo writer planning, not immediate mutation:

- "write this to the repo"
- "add this file"
- "patch this"
- "fix this test"
- "delete that"
- "replace this block"
- "create the next prompt"

If the user has explicitly said "go ahead" for a series of doc writes, doc-only writes can proceed as low risk, but code mutations still need stronger checks.

## First implementation target

Build doc/file writing first, then code patching.

### Version 1

- create markdown docs under `docs/`
- update markdown docs under `docs/`
- produce receipts
- deny code mutation unless explicit approval is present

### Version 2

- apply code patches
- run tests automatically
- report failures honestly

## Acceptance tests

Add tests for:

- write inside repo succeeds after approval
- outside-root write is denied
- `.git` write is denied
- unapproved write is denied
- markdown doc write can be approved as low risk
- diff summary is returned
- rollback hint is returned
- receipt includes changed files

## Suggested files

- `core/operator/actions/files.py`
- `core/operator/registry.py`
- `core/operator/manager.py`
- `tests/test_operator_write_actions.py`
- `tests/test_operator_chat_integration.py`

## Done when

Xoduz can safely create or update repo files with approval, produce a diff summary, and refuse unsafe paths without drama.
