"""Draft Store models."""

from __future__ import annotations

from pydantic import Field

from storygraph.models.common import ContractModel


class Draft(ContractModel):
    id: str
    project_id: str
    scene_id: str
    version: int = Field(ge=1)
    text: str
    summary: str | None = None
    discarded: bool = False
    created_at: str
    updated_at: str

