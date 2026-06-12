# CODE-02 Registry Mop-Up Prompt

Use this only after pulling the partial CODE-02 remote commits.

## Prompt

```text
CODE-02 REGISTRY MOP-UP

Context:
The core read-only `patch_plan` action and direct unit tests have already landed:

- core/operator/actions/patch_plan.py
- tests/test_operator_patch_plan.py

The remote writer could not safely update the central registry/export files because those files contain existing operator scan action names. Finish the tiny local wiring in VS Code.

Hard rules:
- Keep this patch small.
- Do not change patch_plan behavior unless tests prove a defect.
- Do not change existing scan/runtime/file actions.
- Do not add mutation behavior.
- patch_plan must remain read-only and plan-only.

Tasks:

1. Update `core/operator/registry.py`:
   - Import `patch_plan` from `core.operator.actions.patch_plan`.
   - Add `"patch_plan": OperatorActionSpec("patch_plan", "read_only", patch_plan)` to `build_operator_registry()` near `workspace_map`.
   - Update `run_action()` so `patch_plan` uses the existing `target` argument as the user goal:

     ```python
     if action_name == "patch_plan":
         if not target:
             raise ValueError("patch_plan requires a target goal")
         return spec.handler(action_id=action_id, repo_root=repo_root, goal=target)
     ```

2. Update `core/operator/actions/__init__.py`:
   - Import `patch_plan`.
   - Add `"patch_plan"` to `__all__`.

3. Update `tests/test_operator_registry.py`:
   - Add `"patch_plan"` to `EXPECTED_ACTIONS`.
   - Add a test that `run_action("patch_plan", target="Implement CODE-02 Patch Planner")` returns a successful `patch_plan` result.
   - Add a test that missing target raises `ValueError` with `requires a target goal`.

4. Run targeted validation:

   ```powershell
   python -m pytest tests/test_operator_patch_plan.py tests/test_operator_registry.py -v --tb=short --asyncio-mode=auto
   python -m ruff check core/operator/actions/patch_plan.py core/operator/registry.py core/operator/actions/__init__.py tests/test_operator_patch_plan.py tests/test_operator_registry.py
   python -m ruff format --check core/operator/actions/patch_plan.py core/operator/registry.py core/operator/actions/__init__.py tests/test_operator_patch_plan.py tests/test_operator_registry.py
   ```

5. If green, update `docs/CODE_LANE_INDEX.md`:
   - Change CODE-02 status from `partial` to `implemented`.
   - Replace the note saying registry/export still needs wiring with a short verified note.

6. Commit:

   ```text
   feat(operator): wire patch plan action
   ```

Expected result:
- `patch_plan` is available directly and through the operator registry.
- No mutation behavior is introduced.
- CODE-02 can be treated as implemented after targeted tests pass.
```
