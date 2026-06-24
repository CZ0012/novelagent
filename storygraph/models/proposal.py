"""Proposal Artifact contract models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from storygraph.models.common import ContractModel, JsonDict


ProposalArtifactType = Literal[
    "scene_draft",
    "fact_draft",
    "scene_rebuild",
    "canon_patch",
    "outline_draft",
    "project_structure_draft",
]

ProposalStatus = Literal[
    "drafting",
    "agent_revised",
    "author_revised",
    "ready_for_review",
    "accepted",
    "rejected",
]

ProposalBodyFormat = Literal["plain_text", "markdown", "structured_json"]
ProposalCreatedVia = Literal["manual", "llm", "import", "workflow", "api"]
ProposalReviewStatus = Literal["none", "accepted", "rejected"]


class ProposalRef(ContractModel):
    kind: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    note: str | None = None
    quote: str | None = None
    source_span: JsonDict | None = None


class ProposalProvenance(ContractModel):
    created_by: str = Field(..., min_length=1)
    created_via: ProposalCreatedVia = "manual"
    workflow_run_id: str | None = None
    model_ref: str | None = None
    note: str | None = None


class ProposalReviewDecision(ContractModel):
    status: ProposalReviewStatus = "none"
    reviewer: str | None = None
    reviewed_at: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def reviewed_decisions_require_auditor(self) -> "ProposalReviewDecision":
        if self.status != "none" and (not self.reviewer or not self.reviewed_at):
            raise ValueError("accepted/rejected proposal decisions require reviewer and reviewed_at")
        return self


class ProposalArtifact(ContractModel):
    contract_version: Literal["proposal_artifact_v1"] = "proposal_artifact_v1"
    id: str
    project_id: str
    artifact_type: ProposalArtifactType
    status: ProposalStatus = "drafting"
    title: str = Field(..., min_length=1)
    body: str = ""
    body_format: ProposalBodyFormat = "markdown"
    target_refs: list[ProposalRef] = Field(default_factory=list)
    source_refs: list[ProposalRef] = Field(default_factory=list)
    provenance: ProposalProvenance
    version: int = Field(ge=1)
    derived_refs: list[ProposalRef] = Field(default_factory=list)
    review_decision: ProposalReviewDecision = Field(default_factory=ProposalReviewDecision)
    created_at: str
    updated_at: str

    @field_validator("project_id", "id")
    @classmethod
    def required_identifier(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier cannot be empty")
        return value

    @model_validator(mode="after")
    def review_status_matches_artifact_status(self) -> "ProposalArtifact":
        if self.status == "accepted" and self.review_decision.status != "accepted":
            raise ValueError("accepted proposals require an accepted review_decision")
        if self.status == "rejected" and self.review_decision.status != "rejected":
            raise ValueError("rejected proposals require a rejected review_decision")
        if self.status not in {"accepted", "rejected"} and self.review_decision.status != "none":
            raise ValueError("non-terminal proposals cannot carry accepted/rejected decisions")
        return self
