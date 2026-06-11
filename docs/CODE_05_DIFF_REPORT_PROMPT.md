# CODE-05 — Diff and Work Report Prompt

## Purpose

Give Xoduz the ability to explain exactly what changed after a patch, without dumping noisy raw diffs into chat.

This is the fifth step in the code-operator loop:

```text
inspect -> plan -> approve -> patch -> test -> report
```

CODE-05 turns repository state into a clean, useful operator report.

---

## Build instruction for VS Code / local AI

Implement CODE-05 as a read-only action and response formatter.

### Goal

Create a `diff_report` operator action that summarizes changed files, diff scope, validation status, and next actions.

### Files to inspect first

- `core/operator/actions/`
- `core/operator/registry.py`
- `core/operator/schema.py`
- `core/operator/manager.py`
- `tests/test_operator_readonly_actions.py`
- `tests/test_operator_runtime_hardening.py`
- `tests/test_operator_receipt_metadata.py`

### Required behavior

Add a read-only action named:

```text
diff_report
```

The action must collect:

```text
- current branch
- short HEAD sha
- changed files from git status --short
- staged files
- unstaged files
- untracked files
- compact diff stat
- optional per-file summary
- latest validation result if available
```

### Safety rules

- Read-only action.
- Must never run `git add`, `git commit`, `git reset`, `git checkout`, `git clean`, or mutation commands.
- Must deny any request to include full raw file contents unless the user explicitly asks to inspect a specific file.
- Must keep normal chat output compact.

### Output shape

Return data like:

```json
{
  "branch": "main",
  "head": "abc1234",
  "clean": false,
  "changed_files": ["core/main.py", "tests/test_x.py"],
  "staged_files": [],
  "unstaged_files": ["core/main.py"],
  "untracked_files": [],
  "diff_stat": "2 files changed, 42 insertions(+), 8 deletions(-)",
  "risk": "medium",
  "validation": {
    "last_test_preset": "ci_core",
    "passed": true
  },
  "next_actions": ["run frontend_app", "commit if approved"]
}
```

### Report format

The visible answer should look like:

```text
Changed files:
- core/main.py — added workspace_map route wiring
- tests/test_operator_readonly_actions.py — added read-only coverage

Validation:
- backend tests passed
- frontend tests not run

Risk:
- medium: operator routing changed

Next:
- run npm test -- public/app.test.js
- commit after review
```

Do not put raw JSON in the visible chat unless the user asks for details.

### Routing phrases

Route these to `diff_report`:

```text
what changed
show me the diff summary
what did you change
summarize the patch
what is dirty
what files changed
are we clean
```

### Tests to add

Add tests proving:

- action is registered as read-only.
- clean repo returns `clean: true`.
- dirty repo returns changed file groups.
- untracked files are reported separately.
- diff stat is compact.
- mutation commands are not used.
- natural-language routing works for “what changed?”
- visible response does not include raw diff unless requested.

### Acceptance

- `diff_report` works from normal chat.
- `diff_report` is safe in normal mode.
- Xoduz can tell Otis what changed after a patch without hallucinating.

---

## Done means

After Xoduz edits code, she can honestly answer:

```text
what changed, what passed, what failed, what is next
```

without making Otis dig through raw Git output.
