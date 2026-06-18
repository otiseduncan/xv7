# X Native Planner

X Native Planner v0 turns inspection or repair-style requests into structured sandbox-only repair proposals.

UI URL: `http://localhost:3100`

API URL: `http://localhost:3101`

The old XV7 core is intentionally bypassed. X Native is the new control baseline. Old XV7 is a parts yard and will be mined later for useful pieces only.

## Planner Output

Planner proposals include:

- problem summary
- probable cause
- proposed fix
- affected files
- validation commands
- rollback plan
- risk
- stage id when staged
- receipt path when saved
- `execution_allowed=false`
- `apply_allowed=false`
- `repo_write=false`

## Sandbox Workspace

Workspace drafts are written only under:

```text
data/x_native/workspace
```

Workspace endpoints:

- `POST /x-native/workspace/draft`
- `GET /x-native/workspace`

Workspace drafts are sandbox-only and are not promoted to repo source. Absolute paths, `..`, Windows drive prefixes, and paths outside the workspace are rejected.

## Current Safety State

Allowed:

- inspect
- plan
- stage
- preview
- draft to sandbox

Not yet allowed:

- repo apply
- repo writes
- shell execution

## Validation

```powershell
python -m py_compile apps/x_native_api/main.py apps/x_native_api/planner.py
docker compose -f docker-compose.x-native.yml up -d --build
Invoke-RestMethod http://localhost:3101/health
Invoke-RestMethod http://localhost:3101/x-native/state
```
