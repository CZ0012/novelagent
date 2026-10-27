"""Context Pack contract models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from storygraph.models.common import ContractModel, Severity
from storygraph.models.project import OutputLanguage
from storygraph.models.temporal_state import TemporalStateProjection
from storygraph.models.writer_visibility import ResolvedWriterVisibility


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
    profile_id: str | None = None
    profile_sha256: str | None = None
    rubric: list[str] = Field(default_factory=list)


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


class ContextGap(ContractModel):
    kind: str
    ref: str
    severity: Severity = "high"
    message: str
    source: str | None = None


class PlannedCausalPrecondition(ContractModel):
    scene_id: str = Field(min_length=1, max_length=200)
    relation_id: str = Field(min_length=1, max_length=200)
    planned_summary: str | None = Field(default=None, max_length=4000)
    planned_outcome: str | None = Field(default=None, max_length=4000)


class PlannedForeshadowingAction(ContractModel):
    id: str = Field(min_length=1, max_length=200)
    relation_id: str = Field(min_length=1, max_length=200)
    action: Literal["seed", "payoff"]
    clue_text: str | None = Field(default=None, max_length=4000)
    planned_payoff: str | None = Field(default=None, max_length=4000)
    seed_scene_ids: list[str] = Field(default_factory=list, max_length=30)
    do_not_reveal_payoff: bool


class ApprovedScenePlan(ContractModel):
    semantics: Literal["approved_plan_not_realized_facts"] = "approved_plan_not_realized_facts"
    planned_summary: str | None = Field(default=None, max_length=4000)
    planned_outcome: str | None = Field(default=None, max_length=4000)
    emotional_turn: str | None = Field(default=None, max_length=4000)
    target_length: int | None = Field(default=None, ge=1, le=2000000)
    causal_preconditions: list[PlannedCausalPrecondition] = Field(default_factory=list, max_length=30)
    foreshadowing_actions: list[PlannedForeshadowingAction] = Field(default_factory=list, max_length=30)


class ContextPack(ContractModel):
    contract_version: Literal["context_pack_v1"] = "context_pack_v1"
    writer_visibility_required: bool = False
    writer_visibility: ResolvedWriterVisibility | None = Field(default=None, exclude=True, repr=False)
    project_id: str
    output_language: OutputLanguage
    scene_id: str
    chapter_id: str
    pov_character_id: str
    location_id: str
    timeline_position: str
    scene_goal: str
    conflict: str
    scene_plan: ApprovedScenePlan | None = None
    required_characters: list[str] = Field(default_factory=list)
    canon_entities: list[dict] = Field(default_factory=list)
    temporal_states: list[TemporalStateProjection] = Field(default_factory=list)
    active_relationships: list[str] = Field(default_factory=list)
    knowledge_boundaries: list[KnowledgeBoundary] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_not_violate: list[str] = Field(default_factory=list)
    unresolved_foreshadowing: list[str] = Field(default_factory=list)
    relevant_world_rules: list[str] = Field(default_factory=list)
    previous_scene_summary: str | None = None
    style_constraints: StyleConstraints
    retrieved_style_samples: list[str] = Field(default_factory=list)
    missing_context: list[ContextGap] = Field(default_factory=list)
    provenance: ContextProvenance
    budget: ContextBudget
