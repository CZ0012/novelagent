"""Workflow run state models.

These models are intentionally backend-neutral so the local MVP can persist
LangGraph-shaped state before the real LangGraph runtime is wired in.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from storygraph.models.common import ContractModel, JsonDict


WorkflowRunStatus = Literal[
    "running",
    "awaiting_review",
    "needs_revision",
    "completed",
    "blocked",
    "failed",
]
WorkflowStepStatus = Literal["pending", "running", "completed", "skipped", "failed"]


class WorkflowStep(ContractModel):
    name: str
    status: WorkflowStepStatus
    started_at: str | None = None
    completed_at: str | None = None
    artifact_refs: JsonDict = Field(default_factory=dict)
    message: str | None = None


class ReviewPayload(ContractModel):
    status: Literal["none", "pending"] = "none"
    candidate_ids: list[str] = Field(default_factory=list)
    source_draft_id: str | None = None
    note: str | None = None


class WorkflowRun(ContractModel):
    id: str
    workflow_name: str
    project_id: str
    scene_id: str | None = None
    status: WorkflowRunStatus
    current_step: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    review_payload: ReviewPayload = Field(default_factory=ReviewPayload)
    created_at: str
    updated_at: str
