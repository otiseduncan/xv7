# VS Code Next Prompts

Use these prompts one lane at a time.

## CODE-01 workspace_map

```text
Implement CODE-01 workspace_map.

Goal:
Give Xoduz a read-only live workspace map before she plans code work.

Tasks:
1. Add a read-only operator action named workspace_map.
2. Return repo root, branch, dirty files, untracked files, top-level folders, key files, detected stack, and available test commands.
3. Register the action in the operator registry.
4. Add slash command /workspace-map.
5. Add natural-language routing for check the repo, where are we, what's left, and inspect the project.
6. Add tests proving the action is read-only and returns the expected shape.

Acceptance:
- The new tests pass.
- Existing operator tests still pass.
- No file mutation occurs.
- Result includes a compact receipt.
```

## CODE-02 patch_plan

```text
Implement CODE-02 patch_plan.

Goal:
Let Xoduz convert a user request into a safe implementation plan without writing files.

Tasks:
1. Add a read-only operator action named patch_plan.
2. Input is a user goal string.
3. Output interpreted goal, likely files, proposed steps, risk level, approval requirement, tests to run, and rollback notes.
4. Add tests proving patch_plan does not mutate files.

Acceptance:
- patch_plan gives a useful implementation plan.
- It does not write files.
- It reports uncertainty honestly.
```

## CODE-03 controlled code change

```text
Implement CODE-03 controlled code change support.

Goal:
Allow Xoduz to prepare and apply small repo-scoped changes only after approval.

Tasks:
1. Require Operator Mode and approval.
2. Keep all writes inside the repo root.
3. Record changed files and a summary.
4. Return test suggestions and rollback notes.
5. Add safety tests.

Acceptance:
- No approval means no write.
- Outside-root paths are denied.
- Successful changes return changed files.
- Failures are honest and specific.
```

## CODE-04 run_tests

```text
Implement CODE-04 run_tests.

Goal:
Give Xoduz a safe way to run allowed project checks.

Tasks:
1. Add run_tests operator action.
2. Start with an allowlist of existing project checks.
3. Deny unknown commands.
4. Return exit code, stdout summary, stderr summary, duration, and receipt.
5. Add tests for allowed and denied commands.

Acceptance:
- Allowed checks run.
- Unknown commands are denied.
- Results are compact and honest.
```

## CODE-05 diff_summary

```text
Implement CODE-05 diff_summary.

Goal:
Let Xoduz answer what changed from live repo state.

Tasks:
1. Add diff_summary read-only action.
2. Return changed files, high-level summary, risk flags, and next action.
3. Add natural-language routing for what changed and summarize this patch.
4. Add tests.

Acceptance:
- Uses live repo status.
- Does not rely on memory.
- Does not mutate files.
```

## COMM-07 correction_learning

```text
Implement COMM-07 correction_learning.

Goal:
When Otis corrects Xoduz, capture the correction as a reviewable rule.

Tasks:
1. Detect explicit corrections.
2. Create a pending learned rule record.
3. Surface it in Review.
4. Add tests.

Acceptance:
- Corrections become pending records.
- User can approve or reject them.
- Approved rules affect future answers.
```

## APP-01 app_request_intake

```text
Implement APP-01 app_request_intake.

Goal:
Turn a loose app-building request into structured requirements.

Tasks:
1. Add app request intake parser.
2. Extract app name, purpose, user type, screens, entities, actions, storage needs, and target.
3. Ask only minimum clarifying questions when required fields are missing.
4. Add tests.

Acceptance:
- A loose app request returns a structured app spec or one compact clarification.
```

## Pull checklist

After remote writes, run:

```powershell
git pull
git status --short --branch
```

Then run the targeted checks for the lane being worked.
