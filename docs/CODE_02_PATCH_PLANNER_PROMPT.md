# CODE-02 Prompt: Patch Planner

Use this prompt after CODE-01 workspace_map exists and passes tests.

## Prompt

```text
CODE-02 — Patch Planner

You are working in the XV7/Xoduz repo. Implement a read-only patch planning workflow that turns a user goal into a concrete implementation plan without modifying files.

Goal:
Let Xoduz answer coding/build requests the way a senior assistant should: inspect the repo, identify likely files, propose a plan, name tests, and ask for approval before any mutation.

Hard rules:
- No file writes.
- No git staging.
- No command that mutates repo/runtime.
- No claim that a patch was applied.
- No broad hallucinated architecture claims; use workspace_map when available.

Implementation requirements:
1. Add a patch planning service or operator action. Suggested file:
   - `core/operator/actions/patch_plan.py`
   or, if project conventions prefer services:
   - `core/operator/planning.py`
2. Input:
   - user goal
   - optional workspace map result
   - optional known changed files
3. Output:
   - normalized user goal
   - files likely involved
   - proposed changes
   - tests to run
   - risk level: low/medium/high
   - approval required: true/false
   - why approval is required
   - unknowns/questions if needed
4. Add route/classifier handling for prompts like:
   - build the next piece
   - add app builder mode
   - make Xoduz inspect and patch code
   - write code for VS Code
   - implement CODE-01/CODE-02/CODE-03
5. Add tests proving:
   - planner is read-only
   - planner includes files/tests/risk
   - planner requires approval for mutation
   - planner does not invent success
   - planner uses workspace_map if provided

Suggested return shape:

{
  "goal": "Implement workspace_map operator action",
  "mode": "plan_only",
  "mutation_required": true,
  "approval_required": true,
  "risk": "medium",
  "likely_files": [
    "core/operator/actions/workspace.py",
    "core/operator/registry.py",
    "tests/test_operator_readonly_actions.py"
  ],
  "proposed_changes": [
    "Add read-only workspace map action",
    "Register action",
    "Add tests and chat routing"
  ],
  "tests_to_run": [
    "python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto"
  ],
  "questions": []
}

Acceptance:
- A coding request produces a plan, not a mutation.
- The visible answer is compact and practical.
- Detailed plan data is available in receipt/diagnostics.
- All tests pass.
```

## Manual validation commands

```powershell
python -m pytest tests/test_operator_chat_integration.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```

## Notes for Otis

This is the bridge from chat to coding work. Once CODE-02 exists, Xoduz should stop giving vague advice and start giving specific implementation plans with files and tests.