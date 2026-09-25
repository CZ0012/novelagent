"""Draft Store models."""

from __future__ import annotations

from pydantic import Field, model_validator

from storygraph.models.common import ContractModel
from storygraph.models.project import OutputLanguage
from storygraph.models.common import JsonDict


class Draft(ContractModel):
    id: str
    project_id: str
    scene_id: str
    content_language: OutputLanguage | None = None
    language_inferred: bool = False
    version: int = Field(ge=1)
    text: str
    summary: str | None = None
    provenance: JsonDict | None = None
    discarded: bool = False
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
