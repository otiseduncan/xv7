# CODE-03 Prompt: Approved Patch Apply

Use this prompt only after CODE-01 and CODE-02 exist and pass tests.

## Prompt

```text
CODE-03 — Approved Patch Apply

You are working in the XV7/Xoduz repo. Implement a safe approved patch application workflow.

Goal:
Let Xoduz apply bounded code changes only after an explicit user approval flow. This is the first mutation step in the coding assistant loop.

Hard rules:
- No write outside repo root.
- No mutation unless Operator Mode is enabled or the existing mutation approval rules are satisfied.
- No applying a plan that has not been staged.
- No destructive commands.
- No commit or push in this milestone.
- Always return changed files and diff summary.
- Failed tests must be reported honestly.

Implementation requirements:
1. Add a staged patch representation.
2. Add an action or service to apply approved patches. Suggested names:
   - `stage_patch_plan`
   - `apply_approved_patch`
   - `patch_apply`
3. The patch input should include:
   - target files
   - before/after content or unified diff
   - source plan id
   - risk level
   - test commands
4. The apply path must:
   - validate repo root
   - validate all paths stay inside repo
   - reject absolute/outside paths
   - create parent directories only inside allowed workspace
   - capture before/after hash or diff
   - return changed files
   - return tests to run or run them if the project already supports test execution
5. Add approval UX/card if needed in frontend.
6. Add tests proving:
   - unapproved patch is denied
   - outside-root path is denied
   - approved patch modifies expected file
   - diff summary exists
   - failed patch is honest
   - no commit happens

Suggested result shape:

{
  "action": "apply_approved_patch",
  "status": "success",
  "changed_files": ["core/operator/actions/workspace.py"],
  "diff_summary": [
    "Added workspace_map read-only action"
  ],
  "tests_recommended": [
    "python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto"
  ],
  "committed": false,
  "requires_commit_approval": true
}

Acceptance:
- A patch cannot be applied without approval.
- A patch cannot write outside the repo.
- A successful patch returns changed files and a compact summary.
- Tests are recommended or run with honest status.
- No commit/push happens in CODE-03.
```

## Manual validation commands

```powershell
python -m pytest tests/test_operator_mode_b97.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/test_operator_chat_integration.py -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```

## Notes for Otis

This is the point where Xoduz starts becoming a real builder. Keep the first version boring and safe. It should write only after approval, report exactly what changed, and never pretend tests passed.