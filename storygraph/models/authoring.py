"""Versioned, noncanon author collaboration workspace contracts."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator, field_validator
from storygraph.core.agent_config import ModelExecution

from storygraph.models.common import ContractModel, JsonDict
from storygraph.models.project import OutputLanguage
from storygraph.models.writer_visibility import ReaderPresented, WriterVisibilityPolicy


class AuthoringSourcePin(ContractModel):
    kind: Literal["source_document", "outline"]
    id: str = Field(min_length=1, max_length=200)
    version: int | None = Field(default=None, ge=1, strict=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def outline_version(self):
        if self.kind == "outline" and self.version is None:
            raise ValueError("Outline pins require an exact Proposal version.")
        return self


class AuthoringDraftPin(ContractModel):
    scene_id: str = Field(min_length=1, max_length=200)
    draft_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1, strict=True)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AuthoringEvidence(ContractModel):
    draft: AuthoringDraftPin
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)
    expected_text: str = Field(min_length=1, max_length=4000)
    offset_unit: Literal["utf16"] = "utf16"

    @model_validator(mode="after")
    def ordered_span(self):
        if self.end <= self.start:
            raise ValueError("Evidence must have a nonempty ordered span.")
        return self


class AuthoringDesignItem(ContractModel):
    model_config = ConfigDict(json_schema_extra={"allOf": [
        {"if": {"properties": {"kind": {"enum": ["character_belief", "character_claim"]}}, "required": ["kind"]},
         "then": {"required": ["character_id"], "properties": {"character_id": {"type": "string", "minLength": 1, "maxLength": 200}}}},
        {"if": {"properties": {"kind": {"const": "open_question"}}, "required": ["kind"]},
         "then": {"properties": {"status": {"enum": ["open", "alternative"]}}}},
    ]})
    id: str = Field(min_length=1, max_length=200)
    kind: Literal["world_fact", "true_cause", "character_belief", "character_claim", "open_question"]
    status: Literal["open", "alternative", "author_decided"] = "open"
    text: str = Field(min_length=1, max_length=6000)
    character_id: str | None = Field(default=None, min_length=1, max_length=200)
    about_character_id: str | None = Field(default=None, min_length=1, max_length=200)
    alternative_group: str | None = Field(default=None, max_length=200)
    rationale: str = Field(default="", max_length=4000)
    depends_on: list[str] = Field(default_factory=list, max_length=100)
    evidence: list[AuthoringEvidence] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def subjective_owner(self):
        if self.kind in {"character_belief", "character_claim"} and not self.character_id:
            raise ValueError("Subjective design items require their owning character.")
        if self.kind == "open_question" and self.status == "author_decided":
            raise ValueError("An open question cannot be an author-decided truth.")
        return self


class AuthoringCharacterKnowledge(ContractModel):
    character_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    item_id: str | None = Field(default=None, min_length=1, max_length=200)
    evidence: list[AuthoringEvidence] = Field(default_factory=list, max_length=20)


class AuthoringCharacterAction(ContractModel):
    character_id: str = Field(min_length=1, max_length=200)
    intention: str = Field(min_length=1, max_length=4000)
    depends_on: list[str] = Field(default_factory=list, max_length=100)


class AuthoringCharacterPlan(ContractModel):
    character_id: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=4000)
    belief_item_ids: list[str] = Field(default_factory=list, max_length=100)
    knowledge_assumptions: list[str] = Field(default_factory=list, max_length=40)
    intended_actions: list[AuthoringCharacterAction] = Field(default_factory=list, max_length=40)


class AuthoringSceneCard(ContractModel):
    id: str = Field(min_length=1, max_length=200)
    version: int = Field(default=1, ge=1, strict=True)
    title: str = Field(min_length=1, max_length=500)
    chapter_title: str = Field(default="", max_length=500)
    author_summary: str = Field(default="", max_length=4000)
    location: str = Field(default="", max_length=500)
    timeline_position: str = Field(default="", max_length=1000)
    goal: str = Field(default="", max_length=4000)
    conflict: str = Field(default="", max_length=4000)
    emotional_turn: str = Field(default="", max_length=4000)
    target_length: int = Field(default=1500, ge=100, le=20000, strict=True)
    scene_id: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["proposed", "approved"] = "proposed"
    pov_character_id: str | None = Field(default=None, min_length=1, max_length=200)
    entry_knowledge: list[AuthoringCharacterKnowledge] = Field(default_factory=list, max_length=100)
    intended_actions: list[AuthoringCharacterAction] = Field(default_factory=list, max_length=100)
    acquisitions: list[AuthoringCharacterKnowledge] = Field(default_factory=list, max_length=100)
    writer_policy: WriterVisibilityPolicy
    withheld: list[str] = Field(default_factory=list, max_length=100)
    intended_outcome: str = Field(default="", max_length=6000)
    depends_on: list[str] = Field(default_factory=list, max_length=100)


class AuthoringWorkspace(ContractModel):
    items: list[AuthoringDesignItem] = Field(default_factory=list, max_length=200)
    character_plans: list[AuthoringCharacterPlan] = Field(default_factory=list, max_length=80)
    scene_cards: list[AuthoringSceneCard] = Field(default_factory=list, max_length=200)
    reader_records: list[ReaderPresented] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def unique_ids(self):
        for values, name in ((self.items, "item"), (self.scene_cards, "card")):
            if len({value.id for value in values}) != len(values):
                raise ValueError(f"Duplicate {name} ID.")
        if len({p.character_id for p in self.character_plans}) != len(self.character_plans):
            raise ValueError("Duplicate character plan.")
        return self


class AuthoringMessage(ContractModel):
    id: str = Field(min_length=1, max_length=200)
    role: Literal["author", "assistant", "tool"]
    content: str = Field(max_length=30000)
    created_at: str = Field(min_length=1, max_length=64)
    tool_name: str | None = Field(default=None, max_length=100)
    tool_call_id: str | None = Field(default=None, max_length=200)
    model_execution: ModelExecution | None = None


class AuthoringProposal(ContractModel):
    id: str = Field(min_length=1, max_length=200)
    base_workspace_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canon_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    inputs_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    supersedes_proposal_id: str | None = Field(default=None, min_length=1, max_length=200)
    model_execution: ModelExecution | None = None
    patch: AuthoringPatch
    summary: str = Field(min_length=1, max_length=6000)
    affected_card_ids: list[str] = Field(default_factory=list, max_length=200)
    affected_scene_ids: list[str] = Field(default_factory=list, max_length=200)
    status: Literal["pending", "adopted", "rejected"] = "pending"
    evidence: list[AuthoringEvidence] = Field(default_factory=list, max_length=100)
    created_at: str = Field(min_length=1, max_length=64)
    reviewed_by: str | None = Field(default=None, max_length=200)
    reviewed_at: str | None = Field(default=None, max_length=64)


class AuthoringHistoryCounts(ContractModel):
    messages: int = Field(default=0, ge=0)
    proposals: int = Field(default=0, ge=0)


class AuthoringHistoryHasMore(ContractModel):
    messages: bool = False
    proposals: bool = False


class AuthoringWriterChoice(ContractModel):
    profile_id: str = Field(min_length=1, max_length=80)
    profile_name: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    auth_mode: Literal["api_key", "chatgpt_plan"] = "api_key"
    reason: str = Field(min_length=1, max_length=2000)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class AuthoringPickWriterArgs(ContractModel):
    profile_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2000)


class AuthoringSession(ContractModel):
    contract_version: Literal["authoring_session_v1"] = "authoring_session_v1"
    id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=200)
    version: int = Field(default=1, ge=1, strict=True)
    content_language: OutputLanguage
    turn_status: Literal["idle", "running", "failed", "unknown"] = "idle"
    turn_id: str | None = Field(default=None, max_length=200)
    turn_calls_started: int = Field(default=0, ge=0, le=8, strict=True)
    turn_max_steps: int = Field(default=6, ge=1, le=8, strict=True)
    turn_error_category: str | None = Field(default=None, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    writer_choice: AuthoringWriterChoice | None = None
    source_pins: list[AuthoringSourcePin] = Field(default_factory=list, max_length=40)
    draft_pins: list[AuthoringDraftPin] = Field(default_factory=list, max_length=2000)
    messages: list[AuthoringMessage] = Field(default_factory=list, max_length=20000)
    workspace: AuthoringWorkspace = Field(default_factory=AuthoringWorkspace)
    proposals: list[AuthoringProposal] = Field(default_factory=list, max_length=5000)
    history_counts: AuthoringHistoryCounts = Field(default_factory=AuthoringHistoryCounts)
    history_has_more: AuthoringHistoryHasMore = Field(default_factory=AuthoringHistoryHasMore)
    created_at: str = Field(min_length=1, max_length=64)
    updated_at: str = Field(min_length=1, max_length=64)


class AuthoringPatch(ContractModel):
    upsert_items: list[AuthoringDesignItem] = Field(default_factory=list, max_length=40)
    upsert_character_plans: list[AuthoringCharacterPlan] = Field(default_factory=list, max_length=20)
    upsert_scene_cards: list[AuthoringSceneCard] = Field(default_factory=list, max_length=20)
    remove_item_ids: list[str] = Field(default_factory=list, max_length=40)
    remove_character_ids: list[str] = Field(default_factory=list, max_length=20)
    remove_card_ids: list[str] = Field(default_factory=list, max_length=20)
    add_reader_records: list[ReaderPresented] = Field(default_factory=list, max_length=40)
    remove_reader_records: list[ReaderPresented] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def disjoint_changes(self):
        groups = (
            ([i.id for i in self.upsert_items], self.remove_item_ids),
            ([p.character_id for p in self.upsert_character_plans], self.remove_character_ids),
            ([c.id for c in self.upsert_scene_cards], self.remove_card_ids),
        )
        for upserts, removes in groups:
            if len(set(upserts)) != len(upserts) or len(set(removes)) != len(removes):
                raise ValueError("Duplicate patch identity.")
            if set(upserts) & set(removes):
                raise ValueError("Patch cannot both remove and upsert an identity.")
        for records in (self.add_reader_records, self.remove_reader_records):
            if any(record in records[:index] for index, record in enumerate(records)):
                raise ValueError("Duplicate reader record patch identity.")
        if any(record in self.remove_reader_records for record in self.add_reader_records):
            raise ValueError("Patch cannot both add and remove the same reader record.")
        return self


class AuthoringEmptyArgs(ContractModel):
    pass


class AuthoringReadSourceArgs(ContractModel):
    kind: Literal["source_document", "outline", "draft"]
    id: str = Field(min_length=1, max_length=200)
    start: int | None = Field(default=None, ge=0, strict=True)
    end: int | None = Field(default=None, ge=1, strict=True)
    offset_unit: Literal["utf16"] = "utf16"

    @model_validator(mode="after")
    def bounded_range(self):
        if (self.start is None) != (self.end is None):
            raise ValueError("Source range requires both UTF-16 offsets.")
        if self.start is not None and not 0 < self.end - self.start <= 20000:
            raise ValueError("Source range must be nonempty and at most 20000 UTF-16 units.")
        return self


class AuthoringQueryArgs(ContractModel):
    query: str = Field(default="", max_length=2000)
    limit: int = Field(default=20, ge=1, le=40, strict=True)


class AuthoringPageArgs(AuthoringQueryArgs):
    offset: int = Field(default=0, ge=0, strict=True)


class AuthoringInspectProposalArgs(ContractModel):
    proposal_id: str = Field(min_length=1, max_length=200)
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=10, ge=1, le=20, strict=True)


class AuthoringSearchSourceArgs(ContractModel):
    kind: Literal["source_document", "outline", "draft"]
    id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=2000)
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=10, ge=1, le=20, strict=True)


class AuthoringCharacterViewArgs(ContractModel):
    character_id: str = Field(min_length=1, max_length=200)
    card_id: str | None = Field(default=None, min_length=1, max_length=200)


class AuthoringSimulateCharacterArgs(AuthoringCharacterViewArgs):
    question_kind: Literal["next_action", "conflict_response", "disclosure_choice"]


class AuthoringCharacterOption(ContractModel):
    action: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=4000)


class AuthoringCharacterSimulation(ContractModel):
    options: list[AuthoringCharacterOption] = Field(min_length=1, max_length=6)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)


class AuthoringImpactArgs(ContractModel):
    item_ids: list[str] = Field(default_factory=list, max_length=40)
    card_ids: list[str] = Field(default_factory=list, max_length=20)


class AuthoringProposeArgs(ContractModel):
    patch: AuthoringPatch
    summary: str = Field(min_length=1, max_length=6000)


class AuthoringReviseProposalArgs(AuthoringProposeArgs):
    proposal_id: str = Field(min_length=1, max_length=200)


class AuthoringDraftAcquisitionArgs(ContractModel):
    character_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    quote_refs: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=1, max_length=20)
    item_id: str | None = Field(default=None, min_length=1, max_length=200)


class AuthoringDraftReaderArgs(ContractModel):
    quote_ref: str = Field(min_length=1, max_length=200)
    presentation: Literal["narration", "character_statement", "clue"]


class AuthoringDraftEvidenceArgs(ContractModel):
    summary: str = Field(min_length=1, max_length=6000)
    acquisitions: list[AuthoringDraftAcquisitionArgs] = Field(default_factory=list, max_length=40)
    reader_records: list[AuthoringDraftReaderArgs] = Field(default_factory=list, max_length=40)


class AuthoringSearchDraftQuotesArgs(ContractModel):
    quotes: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1, max_length=12,
        description="Exact literal quotations; each 1..1000 characters, combined at most 4000 characters.")

    @model_validator(mode="after")
    def bounded_quotes(self):
        if any(not 1 <= len(quote) <= 1000 for quote in self.quotes) or sum(map(len, self.quotes)) > 4000:
            raise ValueError("Draft quote batch exceeds its explicit literal quotation bounds.")
        return self


class AuthoringDesignChange(ContractModel):
    target_type: Literal["item", "character_plan", "scene_card"]
    target_id: str = Field(min_length=1, max_length=200)
    fields: JsonDict = Field(min_length=1)


class AuthoringDesignChangesArgs(ContractModel):
    summary: str = Field(min_length=1, max_length=6000)
    changes: list[AuthoringDesignChange] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_targets(self):
        keys = [(change.target_type, change.target_id) for change in self.changes]
        if len(set(keys)) != len(keys):
            raise ValueError("Design changes require distinct typed target identities.")
        return self


class AuthoringCardReviewArgs(ContractModel):
    summary: str = Field(min_length=1, max_length=6000)
    card_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=1, max_length=20,
        json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def unique_cards(self):
        if len(set(self.card_ids)) != len(self.card_ids):
            raise ValueError("Card review requires distinct card identities.")
        return self


class AuthoringMemoryRecord(ContractModel):
    operation: Literal["record", "withdraw", "replace"] = "record"
    memory_id: str | None = Field(default=None, min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)
    kind: Literal["preference", "decision", "tentative"]
    status: Literal["active", "tentative"]
    source_message_id: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=1, max_length=4000)


class AuthoringFinishArgs(ContractModel):
    message: str = Field(min_length=1, max_length=30000)
    author_memories: list[JsonDict] = Field(default_factory=list, max_length=6,
        json_schema_extra={"items": AuthoringMemoryRecord.model_json_schema()})

    @field_validator("author_memories", mode="before")
    @classmethod
    def bounded_optional_memories(cls, value):
        # Optional notebook output must never discard an otherwise valid Main reply.
        if not isinstance(value, list):
            return [{"invalid": True}]
        return [item if isinstance(item, dict) else {"invalid": True} for item in value[:6]]


class AuthoringNavigationContext(ContractModel):
    chapter_id: str | None = Field(default=None, min_length=1, max_length=200)
    scene_id: str | None = Field(default=None, min_length=1, max_length=200)


class AuthoringSkillArgs(ContractModel):
    skill_id: Literal["author-collaboration", "project-navigation", "review-and-revision", "exact-draft-evidence", "writer-and-canon", "character-perspective"]


class AuthoringWorkflowArgs(AuthoringNavigationContext):
    target: Literal["conversation", "design", "checks", "manuscript", "sources", "graph", "settings", "planning", "proposals", "writer", "continuity"]


class AuthoringToolAction(ContractModel):
    tool: Literal["list_writers", "pick_writer", "inspect_sources", "read_source", "search_source", "search_draft_quotes", "inspect_canon", "inspect_workspace", "search_history", "inspect_proposal", "character_view", "simulate_character", "impact_analysis", "propose_workspace", "revise_proposal", "propose_draft_evidence", "propose_design_changes", "propose_card_review", "discover_capabilities", "read_skill", "inspect_project", "inspect_reviews", "open_workflow", "finish"]
    args: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def strict_tool_arguments(self):
        schemas = {
            "list_writers": AuthoringEmptyArgs,
            "pick_writer": AuthoringPickWriterArgs,
            "inspect_sources": AuthoringPageArgs,
            "read_source": AuthoringReadSourceArgs,
            "search_source": AuthoringSearchSourceArgs,
            "inspect_canon": AuthoringQueryArgs,
            "inspect_workspace": AuthoringPageArgs,
            "search_history": AuthoringPageArgs,
            "inspect_proposal": AuthoringInspectProposalArgs,
            "character_view": AuthoringCharacterViewArgs,
            "simulate_character": AuthoringSimulateCharacterArgs,
            "impact_analysis": AuthoringImpactArgs,
            "propose_workspace": AuthoringProposeArgs,
            "revise_proposal": AuthoringReviseProposalArgs,
            "propose_draft_evidence": AuthoringDraftEvidenceArgs,
            "search_draft_quotes": AuthoringSearchDraftQuotesArgs,
            "propose_design_changes": AuthoringDesignChangesArgs,
            "propose_card_review": AuthoringCardReviewArgs,
            "discover_capabilities": AuthoringEmptyArgs,
            "read_skill": AuthoringSkillArgs,
            "inspect_project": AuthoringPageArgs,
            "inspect_reviews": AuthoringPageArgs,
            "open_workflow": AuthoringWorkflowArgs,
            "finish": AuthoringFinishArgs,
        }
        parsed = schemas[self.tool].model_validate(self.args)
        object.__setattr__(self, "args", parsed.model_dump(mode="json", exclude_unset=self.tool in {"propose_workspace", "revise_proposal"}))
        return self


AuthoringProposal.model_rebuild()
AuthoringSession.model_rebuild()

def authoring_tool_schema() -> dict:
    """Advertise the same strict tool-specific arguments enforced at runtime."""
    schemas = {
        "list_writers": AuthoringEmptyArgs,
        "pick_writer": AuthoringPickWriterArgs,
        "inspect_sources": AuthoringPageArgs,
        "read_source": AuthoringReadSourceArgs,
        "search_source": AuthoringSearchSourceArgs,
        "inspect_canon": AuthoringQueryArgs,
        "inspect_workspace": AuthoringPageArgs,
        "search_history": AuthoringPageArgs,
        "inspect_proposal": AuthoringInspectProposalArgs,
        "character_view": AuthoringCharacterViewArgs,
        "simulate_character": AuthoringSimulateCharacterArgs,
        "impact_analysis": AuthoringImpactArgs,
        "propose_workspace": AuthoringProposeArgs,
        "revise_proposal": AuthoringReviseProposalArgs,
        "propose_draft_evidence": AuthoringDraftEvidenceArgs,
        "search_draft_quotes": AuthoringSearchDraftQuotesArgs,
        "propose_design_changes": AuthoringDesignChangesArgs,
        "propose_card_review": AuthoringCardReviewArgs,
        "discover_capabilities": AuthoringEmptyArgs,
        "read_skill": AuthoringSkillArgs,
        "inspect_project": AuthoringPageArgs,
        "inspect_reviews": AuthoringPageArgs,
        "open_workflow": AuthoringWorkflowArgs,
        "finish": AuthoringFinishArgs,
    }
    definitions = {}
    variants = []
    for name, model in schemas.items():
        arguments = model.model_json_schema()
        definitions.update(arguments.pop("$defs", {}))
        variants.append({
            "type": "object",
            "additionalProperties": False,
            "required": ["tool", "args"],
            "properties": {"tool": {"const": name}, "args": arguments},
        })
    # Author commands cannot approve; domain/read records still retain approved.
    card = definitions.get("AuthoringSceneCard")
    if card is not None:
        status = card["properties"]["status"]
        status.pop("enum", None)
        status["const"] = "proposed"
        status["default"] = "proposed"
    return {"oneOf": variants, "$defs": definitions}
