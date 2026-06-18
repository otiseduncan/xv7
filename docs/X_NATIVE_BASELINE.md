# X Native Baseline

This is the clean X Native runtime baseline.

It intentionally avoids the legacy XV7 session bridge, old memory core, Open WebUI integration, and legacy frontend routing.

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

The runtime can stage, preview, and draft. Apply/write execution is intentionally locked in this baseline.

## What this stack does not use

- `core/main.py`
- `core/api/session_message_routes.py`
- old `/sessions/{id}/messages` path
- old visible bridge
- old chat memory path
- old frontend at port `3000`

## Extraction plan

After this baseline is stable, useful pieces from the existing XV7 branch can be extracted into X Native deliberately, one module at a time. The old core should not be allowed to intercept X Native responses.
