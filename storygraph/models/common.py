"""Shared contract primitives."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GraphStatus = Literal[
    "CANON",
    "DRAFT_FACT",
    "HYPOTHESIS",
    "CONFLICT",
    "DEPRECATED",
    "STYLE_SAMPLE",
]

CandidateStatus = Literal[
    "DRAFT_FACT",
    "HYPOTHESIS",
    "CONFLICT",
    "ACCEPTED_FOR_CANON",
    "REJECTED",
    "DEFERRED",
    "DEPRECATED",
]

ReviewStatus = Literal["pending", "accepted", "edited", "rejected", "deferred"]
ReportStatus = Literal["pass", "needs_revision", "blocked", "inconclusive"]
Severity = Literal["low", "medium", "high", "critical"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvidenceItem(ContractModel):
    kind: str
    ref: str
    note: str | None = None
    quote: str | None = None


JsonDict = dict[str, Any]


class ContractRef(ContractModel):
    ref: str = Field(..., min_length=1)
    kind: str = Field(default="unknown")

