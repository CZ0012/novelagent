"""Style sample models for local retrieval."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from storygraph.models.common import ContractModel
from storygraph.models.source import canonicalize_source_language


class StyleSample(ContractModel):
    contract_version: Literal["style_sample_v1"] = "style_sample_v1"
    id: str
    project_id: str
    language: str | None = None
    language_inferred: bool = False
    text: str
    source_ref: str
    pov: str | None = None
    tone: str | None = None
    dialogue_style: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    created_at: str

    @field_validator("language")
    @classmethod
    def canonical_language(cls, value: str | None) -> str | None:
        return canonicalize_source_language(value) if value is not None else None

    @model_validator(mode="before")
    @classmethod
    def mark_legacy_language(cls, value):
        if isinstance(value, dict):
            value = {**value, "language_inferred": value.get("language") is None}
        return value


class StyleSampleMatch(ContractModel):
    sample: StyleSample
    score: float
    matched_terms: list[str] = Field(default_factory=list)
