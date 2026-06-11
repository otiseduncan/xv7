from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.memory.maintenance import MemoryMaintenanceService
from core.operator.schema import OperatorActionResult, OperatorSafety


def memory_audit(*, action_id: str, repo_root: Path) -> OperatorActionResult:
    started = datetime.now(UTC)
    service = MemoryMaintenanceService()
    payload = service.audit_summary()
    completed = datetime.now(UTC)

    return OperatorActionResult(
        action_id=action_id,
        action_name="memory_audit",
        status="success",
        started_at=started,
        completed_at=completed,
        command_or_operation="memory maintenance audit summary",
        target=str(Path(payload.get("records_dir", "data/memory/records"))),
        stdout_summary=(
            f"total={payload.get('total_records', 0)} "
            f"active={payload.get('status_counts', {}).get('active', 0)} "
            f"deleted={payload.get('status_counts', {}).get('deleted', 0)}"
        ),
        stderr_summary="",
        exit_code=None,
        data=payload,
        safety=OperatorSafety(allowed=True),
        receipt_label=f"memory_audit {action_id}",
    )
