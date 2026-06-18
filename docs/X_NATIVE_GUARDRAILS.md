# X Native Guardrails

X Native is the clean control baseline. Old XV7 is a parts yard only.

## Allowed source paths

- `apps/x_native_api/`
- `apps/x_native_ui/`
- `docs/X_NATIVE_BASELINE.md`
- `docs/X_NATIVE_PLANNER.md`
- `docs/X_NATIVE_GUARDRAILS.md`
- `docker-compose.x-native.yml`
- `scripts/x_native_*.ps1`
- `scripts/x_native_*.py`
- `.gitignore`

## Runtime output paths

- `data/x_native/receipts`
- `data/x_native/stages`
- `data/x_native/drafts`
- `data/x_native/workspace`

## Denied integration paths

X Native must not call, import, or depend on:

- `/sessions`
- `/sessions/{id}/messages`
- `core/main.py`
- `core/api/session_message_routes.py`
- old visible-response bridge
- old memory bridge
- old Open WebUI path

## Runtime safety

X Native runtime must not:

- write repo source files
- apply repo patches
- execute shell commands from user prompts
- promote workspace drafts to repo
- expose an apply endpoint

All staged, planned, and draft outputs must include:

- `execution_allowed=false`
- `apply_allowed=false`
- `repo_write=false`
- `promoted_to_repo=false`
- `sandbox_only=true`

Review bundles are also sandbox-only and must stay under `data/x_native/stages/review_bundles`.

## Size limits

- Source files stay under 500 lines.
- UI files stay under 600 lines.
- Functions stay under 60 lines.
- Split API logic into focused modules instead of growing `main.py`.
