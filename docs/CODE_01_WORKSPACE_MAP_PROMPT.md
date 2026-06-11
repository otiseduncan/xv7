# CODE-01 Prompt: Workspace Context Map

Use this prompt in VS Code/Copilot to implement CODE-01.

## Prompt

```text
CODE-01 — Workspace Context Map

You are working in the XV7/Xoduz repo. Implement a read-only workspace map action so Xoduz can inspect the current project before planning or editing code.

Goal:
Create a compact, reliable repo/workspace summary that can be used by chat answers, patch planning, and future app-building workflows.

Rules:
- This action must be read-only.
- It must not write files.
- It must not run mutation commands.
- It must not claim proof unless the command/data was actually collected.
- Missing git/docker/files should be reported as limitations, not hallucinated.

Implementation requirements:
1. Add `core/operator/actions/workspace.py`.
2. Implement `workspace_map(action_id: str, repo_root: Path | str | None = None) -> OperatorActionResult`.
3. The action should collect:
   - resolved repo root
   - git branch if available
   - git status short output if available
   - dirty file list
   - top-level folders
   - key files present/missing
   - detected stack summary
   - likely test commands
   - docker/runtime hints
   - limitation messages when something cannot be proven
4. Keep command execution bounded and read-only.
5. Register the action in the operator registry.
6. Add natural-language routing for:
   - check the repo
   - where are we
   - what is left
   - inspect the project
   - what files matter here
7. Add or update slash command routing for `/workspace-map` if slash commands are centralized.
8. Add tests proving:
   - action is read-only
   - action returns expected keys
   - missing git is reported honestly
   - missing repo root is reported honestly
   - dirty files are represented compactly
   - chat route can select workspace_map for repo-check style prompts

Suggested payload shape:

{
  "repo_root": "...",
  "branch": "main",
  "git_available": true,
  "dirty": true,
  "dirty_files": ["core/main.py"],
  "top_level_folders": ["core", "docs", "public", "tests"],
  "key_files": {
    "README.md": true,
    "docker-compose.yml": true,
    "core/main.py": true,
    "public/index.html": true,
    "package.json": true
  },
  "stack": ["Python", "FastAPI", "static frontend", "Docker", "pytest", "vitest"],
  "test_commands": [
    "python -m pytest tests/ -v --tb=short --asyncio-mode=auto",
    "npm test -- public/app.test.js"
  ],
  "limitations": []
}

Acceptance:
- `python -m pytest tests/ -v --tb=short --asyncio-mode=auto` passes.
- If frontend routing is touched, `npm test -- public/app.test.js` passes.
- The action appears in operator tools/registry.
- A repo-check chat prompt routes to workspace_map and returns a compact receipt.
```

## Manual validation commands

```powershell
python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/test_operator_chat_integration.py -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```

## Notes for Otis

This is the first real step toward making Xoduz work like a coding assistant. Do not build patch-writing until workspace_map is stable. She needs to inspect before she acts.