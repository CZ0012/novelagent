"""Continuity Report contract models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from storygraph.models.common import ContractModel, EvidenceItem, ReportStatus, Severity


CheckedDimension = Literal[
    "knowledge_boundary",
    "timeline",
    "location_state",
    "relationship_state",
    "world_rule",
    "foreshadowing",
    "causality",
    "pov",
    "style_constraint",
]


IssueType = Literal[
    "knowledge_boundary_violation",
    "timeline_conflict",
    "location_conflict",
    "relationship_conflict",
    "world_rule_conflict",
    "foreshadowing_mismatch",
    "causal_gap",
    "pov_leak",
    "style_drift",
    "missing_required_element",
    "unsupported_new_fact",
]


class ContinuityIssue(ContractModel):
    id: str
    issue_type: IssueType
    severity: Severity
    description: str
    violated_nodes: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    suggestion: str
    blocking: bool = False


class ContinuityProvenance(ContractModel):
    graph_query_ids: list[str] = Field(default_factory=list)
    context_pack_ref: str


class ContinuityReport(ContractModel):
    contract_version: Literal["continuity_report_v1"] = "continuity_report_v1"
    project_id: str
    scene_id: str
    draft_id: str
    context_pack_id: str
    status: ReportStatus
    summary: str
    issues: list[ContinuityIssue] = Field(default_factory=list)
    checked_dimensions: list[CheckedDimension] = Field(default_factory=list)
    provenance: ContinuityProvenance
    created_at: str

