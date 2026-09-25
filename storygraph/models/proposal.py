"""Proposal Artifact contract models."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from storygraph.models.common import ContractModel, JsonDict
from storygraph.core.agent_config import ModelExecution
from storygraph.models.project import OutputLanguage
from storygraph.models.source import validate_safe_source_metadata


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
    kind: str = Field(..., min_length=1, max_length=100)
    ref: str = Field(..., min_length=1, max_length=2048)
    note: str | None = Field(default=None, max_length=500)
    quote: str | None = Field(default=None, max_length=500)
    source_span: JsonDict | None = None

    @field_validator("ref", mode="before")
    @classmethod
    def ref_has_no_absolute_local_path(cls, value: str) -> str:
        return validate_safe_source_metadata(value, field_name="proposal ref") or ""

    @field_validator("note", "quote")
    @classmethod
    def text_has_no_absolute_local_path(cls, value: str | None) -> str | None:
        return validate_safe_source_metadata(value, field_name="proposal ref text")

    @field_validator("source_span")
    @classmethod
    def source_span_is_bounded_and_private(cls, value: JsonDict | None) -> JsonDict | None:
        if value is None:
            return None
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(serialized) > 2000:
            raise ValueError("proposal source_span exceeds the metadata budget")
        _validate_source_span_value(value)
        return value


class ProposalProvenance(ContractModel):
    created_by: str = Field(..., min_length=1)
    created_via: ProposalCreatedVia = "manual"
    workflow_run_id: str | None = None
    model_ref: str | None = None
    model_execution: ModelExecution | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def note_has_no_absolute_local_path(cls, value: str | None) -> str | None:
        return validate_safe_source_metadata(value, field_name="proposal provenance note")


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
    content_language: OutputLanguage | None = None
    language_inferred: bool = False
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

    @model_validator(mode="before")
    @classmethod
    def mark_legacy_language(cls, value):
        if isinstance(value, dict):
            value = {
                **value,
                "language_inferred": value.get("content_language") is None,
            }
        return value

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


def _validate_source_span_value(value, *, depth: int = 0) -> None:
    if depth > 4:
        raise ValueError("proposal source_span nesting is too deep")
    if isinstance(value, str):
        if len(value) > 500:
            raise ValueError("proposal source_span text exceeds the metadata budget")
        validate_safe_source_metadata(value, field_name="proposal source_span")
        return
    if isinstance(value, dict):
        if len(value) > 32:
            raise ValueError("proposal source_span contains too many fields")
        for key, nested in value.items():
            if not isinstance(key, str) or not key or len(key) > 100:
                raise ValueError("proposal source_span keys must be short strings")
            validate_safe_source_metadata(key, field_name="proposal source_span key")
            _validate_source_span_value(nested, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > 32:
            raise ValueError("proposal source_span contains too many items")
        for nested in value:
            _validate_source_span_value(nested, depth=depth + 1)
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError("proposal source_span contains an unsupported value")
