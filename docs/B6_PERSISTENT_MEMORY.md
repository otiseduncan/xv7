# B6 Persistent Memory

B6 adds a durable, reviewable persistent-memory layer for XV7.

## Core separation rules

- Memory is not Knowledge.
- Memory is not Verified Status.
- Memory entries are source-labeled and confidence-scored.
- Pending memories are not active recall.

## Storage layout

- Schema: `core/memory/schema.py`
- Store: `core/memory/store.py`
- Manager/policy: `core/memory/manager.py`
- Records: `data/memory/records/XV7-MEMORY-*.json`

## Lifecycle supported

- create pending memory
- approve memory
- activate memory
- supersede memory
- soft-delete memory
- list active memories
- search memories by keyword/tag
- compact memory receipts

Soft-delete is non-destructive. Records are retained with `status=deleted`.

## Chat behaviors (B6)

- `What do you remember?`
- `What do you remember about me?`
- `What do you remember about XV7?`
- `Remember this: ...`
- `Forget that ...`
- `Update that memory: ...`
- `Is that memory verified or just remembered?`

Memory answers use Memory records only. Verified answers still route to Verified Status records.
