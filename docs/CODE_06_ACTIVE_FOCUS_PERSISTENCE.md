# Code 6 — Active Focus Persistence Hardening

Date: 2026-06-12

## Purpose

Code 6 hardens the Active Focus persistence path so XV7 does not report a focus change as saved unless the runtime record is actually persisted.

## Problem addressed

The runtime can be configured so focus mutations try to save into the canonical seed brain record directory. In a container, that directory may be read-only. Code 6 moves runtime focus mutation toward a dedicated runtime override directory and adds tests around that behavior.

## Target behavior

- Active Focus updates are intercepted before model fallback.
- A new focus instruction creates a runtime focus record.
- Prior active focus records are superseded through runtime overrides.
- The current focus is immediately available in session metadata and future context assembly.
- A failed write must not produce a successful saved receipt.

## Suggested validation

```bash
pytest tests/test_brain_records.py tests/test_operator_chat_integration.py
pytest tests/test_active_focus_persistence.py
pytest
```

## Operator note

Recommended runtime paths:

```bash
XV7_BRAIN_RECORDS_PATH=data/brain/records
XV7_BRAIN_RUNTIME_RECORDS_PATH=data/brain/runtime_records
```
