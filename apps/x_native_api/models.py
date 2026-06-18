from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NativeMessageRequest(BaseModel):
    raw_text: str = Field(default="")
    operator_mode: bool = False


class AttachContentRequest(BaseModel):
    content: str = Field(default="")


class WorkspaceDraftRequest(BaseModel):
    path: str = Field(default="x_native_workspace_draft.txt")
    content: str = Field(default="")
    stage_id: str | None = None
    plan: dict[str, Any] | None = None


class ReviewBundleRequest(BaseModel):
    raw_text: str = Field(default="Create a review bundle for the latest X Native planner proposal.")
    stage_id: str | None = None
    planner_proposal: dict[str, Any] | None = None
