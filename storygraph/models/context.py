"""Context Pack contract models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from storygraph.models.common import ContractModel


DEFAULT_PRIORITY_ORDER = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]


class KnowledgeBoundary(ContractModel):
    character_id: str
    knows: list[str] = Field(default_factory=list)
    does_not_know: list[str] = Field(default_factory=list)
    falsely_believes: list[str] = Field(default_factory=list)
    suspects: list[str] = Field(default_factory=list)
    hides: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class StyleConstraints(ContractModel):
    pov: str
    tense: str | None = None
    tone: str | None = None
    sentence_rhythm: str | None = None
    diction: str | None = None
    dialogue_style: str | None = None
    banned_patterns: list[str] = Field(default_factory=list)


class ContextProvenance(ContractModel):
    graph_query_ids: list[str] = Field(default_factory=list)
    draft_refs: list[str] = Field(default_factory=list)
    style_sample_refs: list[str] = Field(default_factory=list)
    author_instruction_refs: list[str] = Field(default_factory=list)
    built_at: str


class ContextBudget(ContractModel):
    target_tokens: int = 4000
    estimated_tokens: int = 0
    priority_order: list[Literal["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]] = Field(
        default_factory=lambda: list(DEFAULT_PRIORITY_ORDER)
    )
    dropped_items: list[str] = Field(default_factory=list)


class ContextPack(ContractModel):
    contract_version: Literal["context_pack_v1"] = "context_pack_v1"
    project_id: str
    scene_id: str
    chapter_id: str
    pov_character_id: str
    location_id: str
    timeline_position: str
    scene_goal: str
    conflict: str
    required_characters: list[str] = Field(default_factory=list)
    active_relationships: list[str] = Field(default_factory=list)
    knowledge_boundaries: list[KnowledgeBoundary] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_not_violate: list[str] = Field(default_factory=list)
    unresolved_foreshadowing: list[str] = Field(default_factory=list)
    relevant_world_rules: list[str] = Field(default_factory=list)
    previous_scene_summary: str | None = None
    style_constraints: StyleConstraints
    retrieved_style_samples: list[str] = Field(default_factory=list)
    provenance: ContextProvenance
    budget: ContextBudget

