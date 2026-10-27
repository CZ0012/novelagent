"""Explicit noncanon permissions for a prose-model input, not graph knowledge."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisibilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WriterSurfacePlan(VisibilityModel):
    kind: Literal["literal", "current_scene_summary"]
    text: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def check_source(self):
        if self.kind == "literal" and (self.text is None or not self.text.strip()):
            raise ValueError("Literal surface plan requires text.")
        if self.kind == "current_scene_summary" and self.text is not None:
            raise ValueError("Current summary selection cannot replace its source.")
        return self


class WriterStyleCapsule(VisibilityModel):
    pov: str | None = Field(default=None, max_length=2000)
    tense: str | None = Field(default=None, max_length=2000)
    tone: str | None = Field(default=None, max_length=2000)
    sentence_rhythm: str | None = Field(default=None, max_length=2000)
    diction: str | None = Field(default=None, max_length=2000)
    dialogue_style: str | None = Field(default=None, max_length=2000)
    banned_patterns: tuple[str, ...] = Field(default=(), max_length=30)
    rubric: tuple[str, ...] = Field(default=(), max_length=30)

    @model_validator(mode="after")
    def bounded_lists(self):
        if any(not s.strip() or len(s) > 2000 for s in (*self.banned_patterns, *self.rubric)):
            raise ValueError("Writer style list item is invalid.")
        return self


class WriterVisibleCharacter(VisibilityModel):
    character_id: str = Field(min_length=1, max_length=200)
    public_name: str = Field(min_length=1, max_length=120)
    allow_offstage_name: bool = False


class WriterVisibleClaim(VisibilityModel):
    text: str = Field(min_length=1, max_length=2000)
    presentation: Literal["observation", "belief", "character_statement", "narrator_fact"]
    phase: Literal["entry", "during_scene"] = "during_scene"
    character_id: str | None = Field(default=None, min_length=1, max_length=200)


class ReaderPresented(VisibilityModel):
    draft_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1, strict=True)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)
    offset_unit: Literal["utf16"] = "utf16"
    expected_text: str = Field(min_length=1, max_length=4000)
    presentation: Literal["narration", "character_statement", "clue"]


class WriterVisibilityPolicy(VisibilityModel):
    contract_version: Literal["writer_visibility_policy_v1"] = "writer_visibility_policy_v1"
    access_mode: Literal["surface", "pov", "omniscient"]
    surface_plan: WriterSurfacePlan
    writer_style: WriterStyleCapsule
    writer_style_origin: Literal["profile_projection", "author_literal"] = "author_literal"
    writer_style_source_profile_id: str | None = Field(default=None, max_length=200)
    writer_style_source_profile_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    characters: tuple[WriterVisibleCharacter, ...] = Field(default=(), max_length=40)
    visible_claims: tuple[WriterVisibleClaim, ...] = Field(default=(), max_length=40)
    reader_presented: tuple[ReaderPresented, ...] = Field(default=(), max_length=20)
    expected_reader_inference: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def style_binding(self):
        if len({c.character_id for c in self.characters}) != len(self.characters):
            raise ValueError("Duplicate writer character mapping.")
        if any(not c.public_name.strip() for c in self.characters) or any(
            not c.text.strip() for c in self.visible_claims
        ):
            raise ValueError("Writer names and claims must be nonblank.")
        bound = (
            self.writer_style_source_profile_id is not None
            and self.writer_style_source_profile_sha256 is not None
        )
        if self.writer_style_origin == "profile_projection" and not bound:
            raise ValueError("Profile projection requires exact profile binding.")
        if self.writer_style_origin == "author_literal" and (
            self.writer_style_source_profile_id is not None
            or self.writer_style_source_profile_sha256 is not None
        ):
            raise ValueError("Literal style cannot claim profile binding.")
        return self


class WriterVisibilityRecord(VisibilityModel):
    contract_version: Literal["writer_visibility_v1"] = "writer_visibility_v1"
    project_id: str = Field(min_length=1, max_length=200)
    scene_id: str | None = Field(default=None, min_length=1, max_length=200)
    version: int = Field(ge=1, strict=True)
    spec: WriterVisibilityPolicy | None
    source_context_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    configured_by: str = Field(min_length=1, max_length=200)
    configured_at: str = Field(min_length=1, max_length=64)


class ResolvedWriterVisibility(VisibilityModel):
    record: WriterVisibilityRecord
    project_id: str
    scene_id: str
    source_context_sha256: str
    policy_fingerprint: str
    reader_sources_verified: bool = False
    reader_source_resolver: Any = Field(default=None, exclude=True, repr=False)
    character_scope_resolver: Any = Field(default=None, exclude=True, repr=False)


class ProseInputGrants(VisibilityModel):
    """Only this instruction/edit target, not reader permission or canon state."""

    instruction: bool = Field(default=False, strict=True)
    instruction_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    target: Literal["none", "draft", "selection"] = "none"
    draft_id: str | None = Field(default=None, min_length=1, max_length=200)
    version: int | None = Field(default=None, ge=1, strict=True)
    text_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    start: int | None = Field(default=None, ge=0, strict=True)
    end: int | None = Field(default=None, ge=1, strict=True)
    expected_text: str | None = Field(default=None, min_length=1, max_length=100000)
    offset_unit: Literal["utf16"] = "utf16"

    @model_validator(mode="after")
    def bound_input(self):
        if self.instruction and self.instruction_sha256 is None:
            raise ValueError("Instruction grant requires its exact text hash.")
        if not self.instruction and self.instruction_sha256 is not None:
            raise ValueError("Instruction hash without permission.")
        if self.target != "none" and any(
            v is None for v in (self.draft_id, self.version, self.text_sha256)
        ):
            raise ValueError("Target grant requires a saved Draft binding.")
        if self.target == "selection" and any(
            v is None for v in (self.start, self.end, self.expected_text)
        ):
            raise ValueError("Selection grant requires its exact UTF-16 span.")
        if self.target != "selection" and any(
            v is not None for v in (self.start, self.end, self.expected_text)
        ):
            raise ValueError("Unexpected selection fields.")
        if self.target == "none" and any(
            v is not None for v in (self.draft_id, self.version, self.text_sha256)
        ):
            raise ValueError("Unexpected Draft binding.")
        return self
