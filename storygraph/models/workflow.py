"""Workflow run state models.

These models are intentionally backend-neutral so the local MVP can persist
LangGraph-shaped state before the real LangGraph runtime is wired in.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from storygraph.models.common import ContractModel, JsonDict
from storygraph.models.project import OutputLanguage


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
    contract_version: Literal["review_payload_v1"] = "review_payload_v1"
    status: Literal["none", "pending"] = "none"
    candidate_ids: list[str] = Field(default_factory=list)
    source_draft_id: str | None = None
    note: str | None = None


class WorkflowRun(ContractModel):
    contract_version: Literal["workflow_run_v1"] = "workflow_run_v1"
    id: str
    workflow_name: str
    project_id: str
    output_language: OutputLanguage | None = None
    language_inferred: bool = False
    scene_id: str | None = None
    status: WorkflowRunStatus
    current_step: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    review_payload: ReviewPayload = Field(default_factory=ReviewPayload)
    created_at: str
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def mark_legacy_language(cls, value):
        if isinstance(value, dict):
            value = {
                **value,
                "language_inferred": value.get("output_language") is None,
            }
        return value
