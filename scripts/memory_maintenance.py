from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.memory.maintenance import MemoryMaintenanceService  # noqa: E402
from core.memory.store import MemoryStore  # noqa: E402


DELETE_CONFIRM = "SOFT DELETE"
DELETE_RANGE_CONFIRM = "SOFT DELETE TEST MEMORIES"
DELETE_DUPLICATES_CONFIRM = "SOFT DELETE DUPLICATE CANDIDATES"


def _build_service(records_dir: str | None) -> MemoryMaintenanceService:
    store = MemoryStore(records_dir=Path(records_dir)) if records_dir else MemoryStore()
    return MemoryMaintenanceService(store=store)


def _print_records(records) -> None:
    if not records:
        print("No records found.")
        return
    for record in records:
        print(
            f"{record.id} | status={record.status} | pending={record.pending_approval} | "
            f"type={record.memory_type} | source={record.source} | {record.content}"
        )


def _print_duplicates(duplicates) -> None:
    if not duplicates:
        print("No duplicate candidates found.")
        return
    for item in duplicates:
        print(
            f"primary={item.primary_id} duplicate={item.duplicate_id} "
            f"similarity={item.similarity:.4f} shared_tags={','.join(item.shared_tags)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="XV7 memory maintenance operations")
    parser.add_argument(
        "command",
        choices=[
            "list",
            "list-active",
            "list-deleted",
            "find-duplicates",
            "soft-delete",
            "restore",
            "audit",
            "export-audit",
            "soft-delete-range",
            "soft-delete-duplicates",
        ],
    )
    parser.add_argument("--id", dest="memory_id")
    parser.add_argument("--from", dest="range_start")
    parser.add_argument("--to", dest="range_end")
    parser.add_argument("--confirm")
    parser.add_argument("--out", default="runtime/memory_audit.json")
    parser.add_argument("--records-dir")
    parser.add_argument("--include-seeds", action="store_true")
    args = parser.parse_args()

    service = _build_service(args.records_dir)

    try:
        if args.command == "list":
            _print_records(service.list_all())
            return 0

        if args.command == "list-active":
            _print_records(service.list_active())
            return 0

        if args.command == "list-deleted":
            _print_records(service.list_deleted())
            return 0

        if args.command == "find-duplicates":
            _print_duplicates(service.find_duplicate_candidates())
            return 0

        if args.command == "audit":
            print(json.dumps(service.audit_summary(), indent=2))
            return 0

        if args.command == "export-audit":
            out_path = service.export_audit(Path(args.out))
            print(f"Audit written: {out_path}")
            return 0

        if args.command == "soft-delete":
            if not args.memory_id:
                raise ValueError("--id is required for soft-delete")
            target = service.store.get_record(args.memory_id)
            if target is None:
                raise ValueError(f"Memory not found: {args.memory_id}")
            print(f"Target id: {target.id}")
            print(f"Current status: {target.status}")
            if args.confirm != DELETE_CONFIRM:
                raise ValueError(f'soft-delete requires --confirm "{DELETE_CONFIRM}"')
            updated = service.soft_delete_by_id(args.memory_id)
            print(f"Soft-deleted: {updated.id} (status={updated.status})")
            return 0

        if args.command == "restore":
            if not args.memory_id:
                raise ValueError("--id is required for restore")
            target = service.store.get_record(args.memory_id)
            if target is None:
                raise ValueError(f"Memory not found: {args.memory_id}")
            print(f"Target id: {target.id}")
            print(f"Current status: {target.status}")
            updated = service.restore_by_id(args.memory_id)
            print(f"Restored: {updated.id} (status={updated.status})")
            return 0

        if args.command == "soft-delete-range":
            if not args.range_start or not args.range_end:
                raise ValueError("--from and --to are required for soft-delete-range")
            targets = [
                record.id
                for record in service.list_all()
                if args.range_start <= record.id <= args.range_end
            ]
            print("Range targets:")
            print("\n".join(targets) if targets else "<none>")
            if args.confirm != DELETE_RANGE_CONFIRM:
                raise ValueError(
                    f'soft-delete-range requires --confirm "{DELETE_RANGE_CONFIRM}"'
                )
            updated = service.soft_delete_range(args.range_start, args.range_end)
            print("Soft-deleted ids:")
            print("\n".join(record.id for record in updated) if updated else "<none>")
            return 0

        if args.command == "soft-delete-duplicates":
            duplicates = service.find_duplicate_candidates()
            target_ids = sorted({item.duplicate_id for item in duplicates})
            if not args.include_seeds:
                target_ids = [
                    memory_id
                    for memory_id in target_ids
                    if memory_id
                    not in {
                        "XV7-MEMORY-0001",
                        "XV7-MEMORY-0002",
                        "XV7-MEMORY-0003",
                        "XV7-MEMORY-0004",
                    }
                ]
            print("Duplicate soft-delete targets:")
            print("\n".join(target_ids) if target_ids else "<none>")
            if args.confirm != DELETE_DUPLICATES_CONFIRM:
                raise ValueError(
                    "soft-delete-duplicates requires --confirm "
                    f'"{DELETE_DUPLICATES_CONFIRM}"'
                )
            updated = service.soft_delete_duplicates(include_seeds=args.include_seeds)
            print("Soft-deleted ids:")
            print("\n".join(record.id for record in updated) if updated else "<none>")
            return 0

        raise ValueError(f"Unsupported command: {args.command}")
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
