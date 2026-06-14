"""Assistant-visible response planning helpers.

This module organizes already-known facts into deterministic JSON-safe payloads.
It does not generate final prose, call models, write files, or claim work that
was not supplied by callers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, TypedDict


GateState = Literal["passed", "failed", "pending", "not_required"]


class GateStatus(TypedDict):
    local: GateState
    ci: GateState


class VisibleResponsePlanPayload(TypedDict):
    summary_lines: list[str]
    created_files: list[str]
    changed_files: list[str]
    warnings: list[str]
    next_actions: list[str]
    gate_status: GateStatus
    ready_for_user: bool


class VisibleResponsePlanManager:
    """Build deterministic response plan payloads from supplied facts."""

    READY_STATES: set[GateState] = {"passed", "not_required"}

    @staticmethod
    def _clean_string(value: str | None) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_path(value: str) -> str:
        return value.strip().replace("\\", "/")

    @classmethod
    def _dedupe_lines(cls, values: Sequence[str] | None) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values or ():
            normalized = cls._clean_string(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @classmethod
    def _dedupe_paths(cls, values: Sequence[str] | None) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values or ():
            normalized = cls._normalize_path(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @classmethod
    def _summary_lines(
        cls,
        *,
        action_name: str | None,
        artifact_type: str | None,
        project_name: str | None,
    ) -> list[str]:
        lines: list[str] = []
        action = cls._clean_string(action_name)
        artifact = cls._clean_string(artifact_type)
        project = cls._clean_string(project_name)
        if action:
            lines.append(f"Action: {action}")
        if artifact:
            lines.append(f"Artifact: {artifact}")
        if project:
            lines.append(f"Project: {project}")
        return lines

    @classmethod
    def build_plan(
        cls,
        *,
        action_name: str | None = None,
        artifact_type: str | None = None,
        project_name: str | None = None,
        created_files: Sequence[str] | None = None,
        changed_files: Sequence[str] | None = None,
        warnings: Sequence[str] | None = None,
        next_actions: Sequence[str] | None = None,
        local_gate_status: GateState = "not_required",
        ci_gate_status: GateState = "not_required",
    ) -> VisibleResponsePlanPayload:
        gate_status: GateStatus = {
            "local": local_gate_status,
            "ci": ci_gate_status,
        }
        return {
            "summary_lines": cls._summary_lines(
                action_name=action_name,
                artifact_type=artifact_type,
                project_name=project_name,
            ),
            "created_files": cls._dedupe_paths(created_files),
            "changed_files": cls._dedupe_paths(changed_files),
            "warnings": cls._dedupe_lines(warnings),
            "next_actions": cls._dedupe_lines(next_actions),
            "gate_status": gate_status,
            "ready_for_user": (
                local_gate_status in cls.READY_STATES
                and ci_gate_status in cls.READY_STATES
            ),
        }
