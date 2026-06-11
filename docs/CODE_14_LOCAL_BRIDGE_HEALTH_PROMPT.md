# CODE-14 — Local Bridge Health Prompt

## Mission

Make local bridge health boring, obvious, and honest.

Xoduz must know when local host tools are available, when they are unavailable, and what the operator should do next. She must not pretend a local scan ran when the bridge is down.

## Why this matters

The local bridge is what separates a normal chatbot from a local operator. If the bridge is unstable or unclear, Xoduz will either hallucinate capability or frustrate Otis with unclear failures.

This lane makes bridge status visible and reliable.

## Files to inspect first

```text
local_bridge/app.py
core/operator/actions/
core/operator/registry.py
core/operator/manager.py
core/main.py
tests/test_operator_chat_integration.py
tests/test_operator_readonly_actions.py
```

## Required behavior

### 1. Bridge status endpoint

Expose or reuse an endpoint/action that reports:

```text
bridge_configured
bridge_url
bridge_reachable
health_status
available_tools
last_success_at
last_failure_at
last_failure_reason
fallback_used
```

### 2. Honest scan routing

When user asks:

```text
scan my system
what processor am I running
check my GPU
what drives do I have
```

Xoduz should:

1. route to local scan intent,
2. check bridge availability,
3. run scan only if bridge is reachable,
4. report unavailable if bridge is unreachable,
5. include receipt metadata.

### 3. User-facing failure wording

If the bridge is unavailable, answer like this:

```text
I cannot scan the host right now because the local bridge is not reachable. I did not run a scan. Start the local bridge, then retry.
```

Do not say:

```text
Your CPU is...
Your drive list is...
The scan completed...
```

unless live scan proof exists.

### 4. Startup guidance

Add a documented command or script for starting the bridge locally.

The docs should include the exact expected health URL and what a good response looks like.

### 5. Receipt metadata

Scan answers should include compact metadata fields:

```text
action_name
bridge_checked
bridge_available
fallback_used
scan_live
source
limitation
```

## Tests required

Add or update tests for:

1. bridge reachable -> scan can run,
2. bridge unreachable -> no fake scan,
3. CPU prompt routes to scan_cpu,
4. disk prompt routes to scan_disk,
5. GPU prompt routes to scan_gpu,
6. unavailable result includes receipt and limitation,
7. normal answer body stays short and honest.

## Acceptance commands

```powershell
python -m pytest tests/test_operator_chat_integration.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/test_operator_readonly_actions.py -v --tb=short --asyncio-mode=auto
python -m pytest tests/ -v --tb=short --asyncio-mode=auto
python -m ruff check core/ tests/
python -m ruff format --check core/ tests/
```

## Definition of done

CODE-14 is done when Xoduz never fakes local scan proof and always gives Otis a clear bridge status plus the next action.

## Commit message

```text
feat: harden local bridge health reporting
```
