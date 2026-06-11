# B4 Brain/Context Integration

B4 introduces a fresh XV7-native brain/context system with five layers:

1. System Prompt
2. Active Focus
3. Knowledge
4. Memory
5. Verified Status

## Design rules

- No hidden reasoning replay.
- No fake memory claims.
- No answer without compact context receipt.
- Verified status is limited to command/test/user-confirmed facts.
- Memory provenance distinguishes user-stated vs inferred facts.

## Canonical schema

Brain records are JSON files under `data/brain/records/` and validated by `core/brain/schema.py`.

Required fields:

- `record_id` (pattern: `XV7-<LAYER>-NNNN`)
- `layer` (`system_prompt`, `active_focus`, `knowledge`, `memory`, `verified_status`)
- `title`, `summary`, `body`
- `status` (`active` or `archived`)
- `facts[]` with `statement`, `source_type`, `source_detail`

## Runtime flow

- Loader: `core/brain/records.py`
- Assembler: `core/brain/context.py`
- Manager: `core/brain/manager.py`
- Endpoint: `GET /runtime/context/active`
- Session integration: `POST /sessions/{session_id}/messages`

For each assistant answer, runtime appends a compact receipt line:

`Context receipt: System Prompt ...; Active Focus ...; Knowledge ...; Memory ...; Verified Status ...`

## Seed records

- `XV7-SYSTEM-0001`
- `XV7-FOCUS-0001`
- `XV7-KNOWLEDGE-0001`
- `XV7-MEMORY-0001`
- `XV7-VERIFIED-0001`

These records are fresh XV7 records and are not imported from XV6.1.

## B4 pass questions

The runtime includes record-driven answers for:

- `Who are you?`
- `What are we working on?`
- `What do you know is verified?`
- `What repo/status are we on?`

If required records are missing, the response explicitly reports what is missing.
