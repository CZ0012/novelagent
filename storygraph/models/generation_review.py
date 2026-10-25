"""Evidence-grounded, noncanon review of one exact generation version."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from storygraph.core.agent_config import ModelExecution
from storygraph.models.common import ReportStatus, Severity
from storygraph.models.project import OutputLanguage


ReviewDimension = Literal[
    "knowledge_boundary", "timeline", "location_state", "relationship_state",
    "world_rule", "foreshadowing", "causality", "pov", "style_constraint",
]
REVIEW_DIMENSIONS: tuple[ReviewDimension, ...] = (
    "knowledge_boundary", "timeline", "location_state", "relationship_state",
    "world_rule", "foreshadowing", "causality", "pov", "style_constraint",
)


class FrozenReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationReviewTarget(FrozenReviewModel):
    project_id: str = Field(min_length=1, max_length=200)
    target_type: Literal["draft", "proposal"]
    target_id: str = Field(min_length=1, max_length=200)
    target_version: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2_000_000)
    output_language: OutputLanguage
    scene_id: str | None = Field(default=None, max_length=200)
    purpose: Literal["scene", "plan"] = "scene"


class CanonFact(FrozenReviewModel):
    id: str
    kind: Literal["node", "relation"]
    text: str


class CanonSnapshot(FrozenReviewModel):
    project_id: str
    scene_id: str | None = None
    scope: Literal["scene", "project", "plan"] = "project"
    facts: tuple[CanonFact, ...] = ()
    fingerprint: str
    complete: bool
    missing_context: tuple[str, ...] = ()
    total_facts: int = Field(ge=0)
    omitted_unrelated_facts: int = Field(default=0, ge=0)


class GenerationReviewEvidence(FrozenReviewModel):
    kind: Literal["target", "canon", "style"]
    ref: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=500)


class GenerationReviewIssue(FrozenReviewModel):
    id: str = Field(min_length=1, max_length=100)
    dimension: ReviewDimension
    severity: Severity
    finding: Literal["contradiction", "required_gap", "advice"] = "contradiction"
    description: str = Field(min_length=1, max_length=1500)
    suggestion: str = Field(min_length=1, max_length=1500)
    evidence: tuple[GenerationReviewEvidence, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def advice_is_not_a_severe_conflict(self):
        if self.finding == "advice" and self.severity in {"high", "critical"}:
            raise ValueError("Advice must have low or medium severity.")
        return self


class SemanticReviewOutput(FrozenReviewModel):
    """Only this bounded shape is accepted from a provider."""

    status: ReportStatus
    summary: str = Field(min_length=1, max_length=2000)
    dimensions_checked: tuple[ReviewDimension, ...] = Field(max_length=9)
    issues: tuple[GenerationReviewIssue, ...] = Field(max_length=40)


class GenerationReviewCoverage(FrozenReviewModel):
    method: Literal["semantic_model", "deterministic_only"]
    canon_complete: bool
    target_complete: bool
    scope: Literal["scene", "project", "plan"] = "project"
    omitted_unrelated_facts: int = Field(default=0, ge=0)
    missing_context: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class GenerationReviewReport(FrozenReviewModel):
    contract_version: Literal["generation_review_v1"] = "generation_review_v1"
    id: str
    project_id: str
    target_type: Literal["draft", "proposal"]
    target_id: str
    target_version: int
    scene_id: str | None = None
    purpose: Literal["scene", "plan"] = "scene"
    output_language: OutputLanguage
    target_text_sha256: str
    canon_fingerprint: str
    canon_evidence_fingerprint: str
    style_fingerprint: str
    status: ReportStatus
    summary: str
    issues: tuple[GenerationReviewIssue, ...] = ()
    dimensions_checked: tuple[ReviewDimension, ...] = ()
    coverage: GenerationReviewCoverage
    model_execution: ModelExecution | None = None
    created_at: str
