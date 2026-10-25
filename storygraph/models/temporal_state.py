"""Typed reviewed state assertions, stored as immutable Event canon nodes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


StateField = Literal["life_status", "physical_state", "location_id", "owner_id"]
STATE_FIELDS = ("life_status", "physical_state", "location_id", "owner_id")
STATE_SUBJECT_TYPES = {
    "life_status": {"Character"}, "physical_state": {"Character"},
    "location_id": {"Character", "Item"}, "owner_id": {"Item"},
}


class TemporalStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    contract_version: Literal["temporal_state_v1"] = "temporal_state_v1"
    field: StateField
    value: str | None = Field(max_length=200)
    valid_from_scene: str = Field(min_length=1, max_length=200)
    expected_slot_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: Literal["assert", "correct"] = "assert"
    supersedes_assertion_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def typed_value(self):
        if (self.action == "correct") != bool(self.supersedes_assertion_id):
            raise ValueError("Corrections require one superseded assertion; assertions cannot supersede")
        if self.field == "life_status" and self.value not in {"alive", "dead"}:
            raise ValueError("Invalid life status")
        if self.field == "physical_state" and self.value not in {"healthy", "injured", "healing"}:
            raise ValueError("Invalid physical state")
        if self.field == "location_id" and not self.value:
            raise ValueError("Location state requires an existing Location")
        if self.field == "owner_id" and self.value == "":
            raise ValueError("Empty owner is not a known unowned state; use null")
        return self


class TemporalCorrectionSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=500)


class TemporalStateCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    assertion_id: str = Field(min_length=1, max_length=200)
    source_draft_id: str = Field(min_length=1, max_length=200)
    expected_draft_version: int = Field(ge=1)
    expected_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_span: TemporalCorrectionSpan
    value: str | None = Field(max_length=200)
    expected_slot_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    rationale: str = Field(min_length=1, max_length=1000)


class TemporalStateValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: StateField
    status: Literal["resolved", "unknown", "ambiguous"]
    value: str | None = None
    assertion_refs: tuple[str, ...] = ()
    reason: str | None = None


class TemporalStateProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["temporal_state_v1"] = "temporal_state_v1"
    project_id: str
    subject_id: str
    scene_id: str
    at_scene_start: bool = False
    states: tuple[TemporalStateValue, ...]
    complete: bool
