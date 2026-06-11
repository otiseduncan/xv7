# CODE-06 — Commit Helper Prompt

## Purpose

Teach Xoduz to prepare a safe commit after an approved patch and successful validation, without hiding state or pretending a commit happened when it did not.

This is not a free-form auto-commit feature. It is a controlled operator workflow that summarizes staged changes, recommends a commit message, and only commits when Operator Mode approval is present.

## Why this exists

The code/operator loop needs a clean ending:

1. Inspect the workspace.
2. Plan the change.
3. Apply an approved patch.
4. Run validation.
5. Summarize the diff.
6. Prepare a clean commit.
7. Report exactly what happened.

Without CODE-06, Xoduz can help build but leaves Otis manually guessing what to commit, what changed, and whether generated artifacts slipped in.

## Required behavior

Implement a read-first commit helper action.

The action must be able to:

- inspect `git status --short --branch`
- list staged files
- list unstaged files
- detect untracked generated artifacts
- detect likely unsafe paths such as caches, temp files, logs, build outputs, and local runtime JSON dumps
- propose a commit message
- optionally stage only approved files
- optionally create the commit only after explicit approval

## Safety rules

The helper must not commit by default.

Commit creation requires:

- Operator Mode ON
- explicit user approval
- a visible pending action card
- clean explanation of what will be staged
- clean explanation of what will be excluded

Never commit:

- `node_modules/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.coverage`
- generated runtime JSON such as `brain-history.json`, `brain-library.json`, `brain-review.json`
- local logs such as `gha-unit.log`, `gha-failed.log`
- local database files
- secrets or `.env` files

## Proposed action shape

Action name:

```text
commit_helper
```

Inputs:

```json
{
  "goal": "short user-facing goal",
  "approved_paths": ["optional explicit file list"],
  "mode": "inspect|stage|commit"
}
```

Outputs:

```json
{
  "branch": "main",
  "ahead_behind": "ahead 1 / behind 0 if available",
  "staged_files": [],
  "unstaged_files": [],
  "untracked_files": [],
  "excluded_files": [],
  "recommended_paths": [],
  "recommended_message": "CODE-01 add workspace map action",
  "requires_approval": true,
  "commit_created": false,
  "commit_sha": null,
  "receipt": {
    "type": "operator",
    "label": "Commit Helper",
    "status": "planned|staged|committed|denied|failed"
  }
}
```

## Chat behavior

When the user asks:

- "commit this"
- "prepare the commit"
- "what should I commit"
- "stage the real files"
- "commit the CODE-01 work"

Xoduz should first inspect the repo and show:

```text
Recommended commit:
CODE-01 add workspace map action

Include:
- core/operator/actions/workspace.py
- core/operator/registry.py
- tests/test_workspace_map.py

Exclude:
- gha-unit.log
- brain-library.json
- node_modules/.vite/vitest/results.json

Approval required before staging/committing.
```

## Acceptance tests

Add tests proving:

1. Inspect mode is read-only.
2. Generated artifacts are excluded.
3. `.env` files are excluded.
4. Commit mode is denied without Operator Mode.
5. Commit mode is denied without approval.
6. Approved file lists are respected.
7. The action returns a compact receipt.
8. The visible answer does not claim a commit was created unless `commit_created=true` and a SHA exists.

## Done means

CODE-06 is done when Otis can ask:

```text
Xoduz, prepare a commit for this CODE-01 patch.
```

and Xoduz can safely identify real source/test/docs changes, exclude junk, recommend a message, and wait for approval before actually committing.
