"""Strict, reviewable staged long-form planning payloads."""

from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator
from storygraph.models.project import OutputLanguage


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Text = str


class BlueprintRequest(StrictModel):
    instruction: str = Field(min_length=1, max_length=12000)
    target_length: int = Field(default=500000, ge=10000, le=2000000)
    volume_count: int = Field(default=5, ge=1, le=12)
    chapters_per_volume: int = Field(default=20, ge=1, le=60)
    scenes_per_chapter: int = Field(default=2, ge=1, le=6)

    @field_validator("instruction")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Instruction must not be blank.")
        return value


class ExpansionRequest(StrictModel):
    parent_proposal_id: str = Field(min_length=1, max_length=200)
    parent_version: int = Field(ge=1)
    volume_index: int = Field(ge=1, le=12)
    chapter_start: int = Field(default=1, ge=1, le=60)
    chapter_count: int = Field(default=5, ge=1, le=5)
    instruction: str = Field(default="", max_length=12000)


class LongformApplyRequest(StrictModel):
    expected_version: int = Field(ge=1)
    reviewer: str = Field(min_length=1, max_length=100)
    rationale: str = Field(default="Author explicitly reviewed and applied the long-form plan.", min_length=1, max_length=1000)
    review_id: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("reviewer", "rationale")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Review provenance must not be blank.")
        return value


class LongformRevisionRequest(StrictModel):
    expected_version: int = Field(ge=1)
    instruction: str = Field(min_length=1, max_length=12000)
    mode: Literal["full", "targeted"] = "full"

    @field_validator("instruction")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Revision instruction must not be blank.")
        return value


class TargetedRevisionChange(StrictModel):
    path: str = Field(min_length=1, max_length=500)
    before: str = Field(min_length=1, max_length=12000)
    after: str = Field(min_length=1, max_length=12000)


class TargetedRevisionOutput(StrictModel):
    changes: list[TargetedRevisionChange] = Field(min_length=1, max_length=40)


class WorldRulePlan(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    domain: str = Field(min_length=1, max_length=120)
    rule: str = Field(min_length=1, max_length=1500)


class EntityInitialState(StrictModel):
    """Explicit baseline slots; omitted values are unknown, never inferred."""

    life_status: Literal["alive", "dead"] | None = None
    physical_state: Literal["healthy", "injured", "healing"] | None = None
    location_id: str | None = Field(default=None, min_length=1, max_length=64)
    owner_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def only_owner_may_be_explicit_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set - {"owner_id"}):
            raise ValueError("Unknown baseline slots must be omitted; only explicit unowned owner_id may be null.")
        return self

    @model_serializer(mode="wrap")
    def serialize_explicit_slots(self, handler):
        # No null defaults can enter canon or change a stored baseline later.
        return {key: value for key, value in handler(self).items() if key in self.model_fields_set}


class EntityPlan(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    kind: Literal["Character", "Location", "Organization", "Item", "Secret"]
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    initial_state: EntityInitialState | None = None

    @model_validator(mode="after")
    def allowed_initial_slots(self):
        if self.initial_state is None:
            return self
        allowed = {"Character": {"life_status", "physical_state", "location_id"},
                   "Item": {"location_id", "owner_id"}}
        if self.kind not in allowed or self.initial_state.model_fields_set - allowed[self.kind]:
            raise ValueError("Initial baseline slots are not valid for this entity kind.")
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_serialization(self, handler):
        data = handler(self)
        # This omission is receipt compatibility: old model_dump content did not
        # contain this optional extension, and its accepted body hash must stay.
        if self.initial_state is None:
            data.pop("initial_state", None)
        return data


class ArcTurn(StrictModel):
    volume_index: int = Field(ge=1, le=12)
    change: str = Field(min_length=1, max_length=1000)


class CharacterArc(StrictModel):
    character_id: str = Field(min_length=1, max_length=64)
    initial_state: str = Field(min_length=1, max_length=1000)
    desire: str = Field(min_length=1, max_length=1000)
    conflict: str = Field(min_length=1, max_length=1000)
    turning_points: list[ArcTurn] = Field(min_length=1, max_length=12)
    final_state: str = Field(min_length=1, max_length=1000)


class StyleBrief(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    pov: str = Field(min_length=1, max_length=200)
    tense: str = Field(min_length=1, max_length=200)
    tone: str = Field(min_length=1, max_length=500)
    sentence_rhythm: str = Field(min_length=1, max_length=500)
    diction: str = Field(min_length=1, max_length=500)
    dialogue_style: str = Field(min_length=1, max_length=500)
    banned_patterns: list[str] = Field(default_factory=list, max_length=30)
    rubric: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1, max_length=20)


class VolumePlan(StrictModel):
    index: int = Field(ge=1, le=12)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=2000)
    central_conflict: str = Field(min_length=1, max_length=1000)
    climax: str = Field(min_length=1, max_length=1000)
    ending_hook: str = Field(min_length=1, max_length=1000)
    target_length: int = Field(ge=1, le=2000000)


class CausalLink(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    from_volume: int = Field(ge=1, le=12)
    to_volume: int = Field(ge=1, le=12)
    cause: str = Field(min_length=1, max_length=1000)
    effect: str = Field(min_length=1, max_length=1000)


class ForeshadowingPlan(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    clue: str = Field(min_length=1, max_length=1000)
    payoff: str = Field(min_length=1, max_length=1000)
    seed_volume: int = Field(ge=1, le=12)
    payoff_volume: int = Field(ge=1, le=12)
    character_ids: list[str] = Field(default_factory=list, max_length=20)


class Blueprint(StrictModel):
    synopsis: str = Field(min_length=1, max_length=6000)
    world_rules: list[WorldRulePlan] = Field(min_length=1, max_length=30)
    entities: list[EntityPlan] = Field(min_length=2, max_length=60)
    character_arcs: list[CharacterArc] = Field(min_length=1, max_length=30)
    style_brief: StyleBrief
    volumes: list[VolumePlan] = Field(min_length=1, max_length=12)
    causal_links: list[CausalLink] = Field(default_factory=list, max_length=60)
    foreshadowing: list[ForeshadowingPlan] = Field(min_length=1, max_length=60)


class ScenePlan(StrictModel):
    id: str = Field(pattern=r"^v\d{2}_c\d{3}_s\d{2}$")
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1000)
    goal: str = Field(min_length=1, max_length=500)
    conflict: str = Field(min_length=1, max_length=500)
    outcome: str = Field(min_length=1, max_length=500)
    emotional_turn: str = Field(min_length=1, max_length=500)
    pov_character_id: str = Field(min_length=1, max_length=64)
    location_id: str = Field(min_length=1, max_length=64)
    required_characters: list[str] = Field(min_length=1, max_length=20)
    timeline_position: str = Field(min_length=1, max_length=500)
    target_length: int = Field(ge=1, le=2000000)
    causal_dependencies: list[str] = Field(default_factory=list, max_length=30)
    foreshadowing_seed_ids: list[str] = Field(default_factory=list, max_length=30)
    foreshadowing_payoff_ids: list[str] = Field(default_factory=list, max_length=30)


class ChapterPlan(StrictModel):
    index: int = Field(ge=1, le=60)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1500)
    purpose: str = Field(min_length=1, max_length=1000)
    target_length: int = Field(ge=1, le=2000000)
    scenes: list[ScenePlan] = Field(min_length=1, max_length=6)


class Expansion(StrictModel):
    volume_index: int = Field(ge=1, le=12)
    chapter_start: int = Field(ge=1, le=60)
    chapters: list[ChapterPlan] = Field(min_length=1, max_length=5)


class LongformPlan(StrictModel):
    schema_version: Literal["longform_plan_v1"] = Field(alias="schema")
    phase: Literal["blueprint", "expansion"]
    project_id: str
    output_language: OutputLanguage
    graph_snapshot: str = Field(pattern=r"^[a-f0-9]{64}$")
    request: BlueprintRequest | ExpansionRequest
    parent_proposal_id: str | None = None
    parent_version: int | None = None
    blueprint: Blueprint | None = None
    expansion: Expansion | None = None
