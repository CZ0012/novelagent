"""Candidate Fact contract models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from storygraph.models.common import CandidateStatus, ContractModel, EvidenceItem, JsonDict, ReviewStatus


class SourceSpan(ContractModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    quote: str


class ProposedGraphPatch(ContractModel):
    operation: Literal["create_node", "update_node", "create_relation", "update_relation", "none"]
    target: str
    properties: JsonDict = Field(default_factory=dict)
    source_ref: str


class ReviewDecision(ContractModel):
    status: ReviewStatus = "pending"
    reviewer: str | None = None
    reviewed_at: str | None = None
    note: str | None = None


class CandidateFact(ContractModel):
    contract_version: Literal["candidate_fact_v1"] = "candidate_fact_v1"
    id: str
    project_id: str
    fact_type: str
    subject_id: str
    relation: str
    object_id: str | None = None
    value: str | None = None
    source_scene_id: str
    source_draft_id: str
    source_span: SourceSpan
    confidence: float = Field(ge=0.0, le=1.0)
    status: CandidateStatus = "DRAFT_FACT"
    rationale: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    proposed_graph_patch: ProposedGraphPatch
    review: ReviewDecision = Field(default_factory=ReviewDecision)
    created_at: str

    @field_validator("status")
    @classmethod
    def no_canon_candidate_status(cls, value: CandidateStatus) -> CandidateStatus:
        if value == "CANON":  # Defensive guard for architecture examples.
            raise ValueError("CandidateFact cannot use CANON status")
        return value

