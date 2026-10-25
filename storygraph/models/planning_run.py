"""Bounded non-canon whole-book planning state and exact artifact manifests."""

from typing import Literal
from pydantic import Field, model_validator
from storygraph.models.longform import Blueprint, BlueprintRequest, Expansion, StrictModel
from storygraph.models.project import OutputLanguage


class PlanningRunRequest(BlueprintRequest):
    batch_size: int = Field(default=5, ge=1, le=5)
    max_calls: int = Field(default=80, ge=1, le=128)
    max_repairs_per_step: int = Field(default=2, ge=0, le=2)
    seed_blueprint_id: str | None = Field(default=None, min_length=1, max_length=200)
    seed_blueprint_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def feasible_with_hard_call_limit(self):
        if (self.seed_blueprint_id is None) != (self.seed_blueprint_version is None):
            raise ValueError("Seed blueprint ID and version must be supplied together.")
        batches = self.volume_count*((self.chapters_per_volume+self.batch_size-1)//self.batch_size)
        if 2*(1+batches)+1-(self.seed_blueprint_id is not None) > 128:
            raise ValueError("The requested grid exceeds the 128-call minimum; use larger batches or fewer chapters/volumes.")
        return self


class PlanningRunControl(StrictModel):
    expected_version: int = Field(ge=1)


class PlanningRunResume(PlanningRunControl):
    retry_uncertain_call: bool = False
    max_calls: int | None = Field(default=None, ge=1, le=128)
    restart_from_step: int | None = Field(default=None, ge=0)
    revision_instruction: str | None = Field(default=None, min_length=1, max_length=12000)
    recheck_current_step: bool = False
    preserve_later_outputs: bool = False
    revision_mode: Literal["targeted", "full"] = "targeted"

    @model_validator(mode="after")
    def explicit_restart_instruction(self):
        if self.recheck_current_step and (self.restart_from_step is not None or self.revision_instruction is not None
                                         or self.preserve_later_outputs or self.revision_mode != "targeted"):
            raise ValueError("Recheck cannot be combined with a restart or revision instruction.")
        if self.revision_instruction is not None and (self.restart_from_step is None or not self.revision_instruction.strip()):
            raise ValueError("A nonblank revision instruction requires an explicit restart step.")
        if self.preserve_later_outputs and self.restart_from_step is None:
            raise ValueError("Retaining later outputs requires an explicit restart step.")
        if self.revision_mode == "full" and (self.restart_from_step is None or not self.revision_instruction):
            raise ValueError("Full revision requires an explicit restart step and instruction.")
        return self


class PlanningRef(StrictModel):
    id: str
    version: int = Field(ge=1)
    body_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PlanningStep(StrictModel):
    index: int = Field(ge=0)
    phase: Literal["blueprint", "expansion"]
    volume_index: int | None = None
    chapter_start: int | None = None
    chapter_count: int | None = None
    status: Literal["pending", "generated", "needs_revision", "passed"] = "pending"
    proposal_ref: PlanningRef | None = None
    review_id: str | None = None
    repairs: int = 0
    revision_instruction: str | None = None
    retained_output_ref: PlanningRef | None = None
    revision_mode: Literal["targeted", "full"] = "targeted"


class PlanningCall(StrictModel):
    id: str
    task: Literal["planning", "continuity"]
    operation: Literal["generate", "review", "repair", "book_review"]
    step_index: int


class PlanningRun(StrictModel):
    contract_version: Literal["planning_run_v1"] = "planning_run_v1"
    id: str
    project_id: str
    version: int = Field(ge=1)
    status: Literal["queued", "running", "paused", "awaiting_review", "completed"] = "queued"
    stage: Literal["blueprint", "expansion", "book_review", "bundle", "done"] = "blueprint"
    request: PlanningRunRequest
    output_language: OutputLanguage
    canon_fingerprint: str
    calls_reserved: int = 0
    max_calls: int
    stop_requested: bool = False
    pause_reason: str | None = None
    pending_call: PlanningCall | None = None
    steps: list[PlanningStep]
    bundle_proposal_id: str | None = None
    final_review_id: str | None = None
    execution_fingerprints: dict[str, str] = Field(default_factory=dict)
    owner_pid: int | None = None
    worker_token: str | None = None
    seed_blueprint_ref: PlanningRef | None = None
    restart_history: list[dict] = Field(default_factory=list)
    created_at: str
    updated_at: str


class BranchPlan(StrictModel):
    schema_version: Literal["longform_branch_plan_v1"] = Field(alias="schema")
    run_id: str
    project_id: str
    output_language: OutputLanguage
    canon_fingerprint: str
    step_index: int
    phase: Literal["blueprint", "expansion"]
    blueprint_ref: PlanningRef | None = None
    previous_refs: list[PlanningRef] = Field(default_factory=list)
    blueprint: Blueprint | None = None
    expansion: Expansion | None = None


class BookBundle(StrictModel):
    schema_version: Literal["longform_book_bundle_v1"] = Field(alias="schema")
    run_id: str
    project_id: str
    output_language: OutputLanguage
    canon_fingerprint: str
    blueprint_ref: PlanningRef
    expansion_refs: list[PlanningRef]
    final_review_id: str
