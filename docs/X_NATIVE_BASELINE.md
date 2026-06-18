# X Native Baseline

This is the clean X Native runtime baseline and the new control baseline for X.

It intentionally avoids the legacy XV7 session bridge, old memory core, Open WebUI integration, and legacy frontend routing.
The old XV7 core is intentionally bypassed and will be mined later for useful pieces only.

## Services

- `x-native-api` on `http://localhost:3101`
- `x-native-ui` on `http://localhost:3100`

## Start only X Native

```powershell
docker compose -f docker-compose.x-native.yml up -d --build
```

Open:

```text
http://localhost:3100
```

## Stop X Native

```powershell
docker compose -f docker-compose.x-native.yml down
```

## Proof commands

```powershell
Invoke-RestMethod http://localhost:3101/health
Invoke-RestMethod http://localhost:3101/x-native/state
.\scripts\x_native_smoke.ps1
```

## Message examples

Safe inspection:

```text
diagnose yourself
```

Safe staging:

```text
create file native_test.txt
```

Planner:

```text
Inspect your runtime and propose the next repair needed to make this baseline production-ready. Stage only. Do not apply or write files.
```

The runtime can inspect, plan, stage, preview, create review bundles, and draft to sandbox workspace. Apply/write execution is intentionally locked in this baseline.

## Current safety state

See `docs/X_NATIVE_GUARDRAILS.md` for the active hard guardrails.

Allowed:

- inspect
- plan
- stage
- preview
- create review bundles
- draft to sandbox workspace under `data/x_native/workspace`

Not allowed:

- repo apply
- repo writes
- shell execution from prompts

Every planned/drafted action must keep:

- `execution_allowed=false`
- `apply_allowed=false`
- `repo_write=false`
- `sandbox_only=true`

## One-command smoke

From repo root after starting the stack:

```powershell
.\scripts\x_native_smoke.ps1
.\scripts\x_native_full_check.ps1
```

The checks cover health, state, diagnosis, planner proposals, review bundles, sandbox workspace draft/list behavior, UI availability, and line-count guardrails.

## What this stack does not use

- `core/main.py`
- `core/api/session_message_routes.py`
- old `/sessions/{id}/messages` path
- old visible bridge
- old chat memory path
- old frontend at port `3000`

## Extraction plan

After this baseline is stable, useful pieces from the existing XV7 branch can be extracted into X Native deliberately, one module at a time. The old core should not be allowed to intercept X Native responses.
