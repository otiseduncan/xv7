# B6.1 Memory Maintenance and Test Isolation

B6.1 adds safe cleanup operations for persistent memory and isolates tests from production-like memory files.

## Why soft-delete

Soft-delete keeps history reviewable and reversible.

- No hard-delete operations are used.
- Deleted memories can be restored.
- Audit trails remain intact for operator review.

## Maintenance script

Path: `scripts/memory_maintenance.py`

Supported commands:

- `list`
- `list-active`
- `list-deleted`
- `find-duplicates`
- `soft-delete --id XV7-MEMORY-0000 --confirm "SOFT DELETE"`
- `restore --id XV7-MEMORY-0000`
- `audit`
- `export-audit --out runtime/memory_audit.json`
- `soft-delete-range --from XV7-MEMORY-0005 --to XV7-MEMORY-0016 --confirm "SOFT DELETE TEST MEMORIES"`
- `soft-delete-duplicates --confirm "SOFT DELETE DUPLICATE CANDIDATES"`

All destructive operations print target IDs before mutation.

## Duplicate detection

Duplicate candidates are detected deterministically from active records using:

- normalized content similarity
- matching `memory_type`
- overlapping tags
- same `source`
- active status only

## Test isolation

Memory tests use temporary record directories instead of `data/memory/records`.

- Unit tests create stores under `tmp_path`.
- Chat-path tests inject temporary persistent-memory managers.
- Isolation tests verify no new files are created in `data/memory/records`.
