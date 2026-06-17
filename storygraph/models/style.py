"""Style sample models for local retrieval."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from storygraph.models.common import ContractModel


class StyleSample(ContractModel):
    contract_version: Literal["style_sample_v1"] = "style_sample_v1"
    id: str
    project_id: str
    text: str
    source_ref: str
    pov: str | None = None
    tone: str | None = None
    dialogue_style: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    created_at: str


class StyleSampleMatch(ContractModel):
    sample: StyleSample
    score: float
    matched_terms: list[str] = Field(default_factory=list)

