"""Minimal FastAPI surface for the StoryGraph MVP."""

from __future__ import annotations

import os
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from storygraph.core.agent_config import (
    AgentPermissionLevel,
    AgentRuntimeConfig,
    AgentRuntimeConfigUpdate,
    apply_agent_config,
    config_response,
    has_permission,
    load_agent_config,
    save_agent_config,
    update_agent_config,
)
from storygraph.core.config import StoryGraphSettings
from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.ids import new_id, slug_id
from storygraph.core.time import utc_now
from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph
from storygraph.models.proposal import (
    ProposalArtifact,
    ProposalArtifactType,
    ProposalBodyFormat,
    ProposalCreatedVia,
    ProposalProvenance,
    ProposalRef,
)
from storygraph.models.common import EvidenceItem
from storygraph.models.style import StyleSample
from storygraph.services import (
    AuthorCanonSeedService,
    ContextPackBuilder,
    GraphQueryService,
    ReviewService,
    RuleBasedContinuityChecker,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
    create_scene_writer,
)
from storygraph.stores import (
    CandidateStore,
    SQLiteCandidateStore,
    SQLiteDraftStore,
    SQLiteProposalStore,
    SQLiteStyleSampleStore,
)
from storygraph.stores.graph_factory import open_configured_graph_store, save_configured_graph_store
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.workflows import SceneGenerationWorkflow


class CreateProjectRequest(BaseModel):
    title: str
    genre: str = "fantasy"
    language: str = "zh-CN"
    target_length: str | None = None
    narrative_pov: str | None = None


class AuthorSeedRequest(BaseModel):
    reviewer: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    properties: dict = Field(default_factory=dict)


class CharacterSeedRequest(AuthorSeedRequest):
    id: str | None = None
    name: str = Field(..., min_length=1)


class LocationSeedRequest(AuthorSeedRequest):
    id: str | None = None
    name: str = Field(..., min_length=1)


class RelationSeedRequest(AuthorSeedRequest):
    id: str | None = None
    type: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)


class ChapterSeedRequest(AuthorSeedRequest):
    id: str | None = None
    title: str = Field(..., min_length=1)
    volume_index: int = 1
    chapter_index: int = 1
    summary: str | None = None
    purpose: str | None = None
    status: str = "planned"
    properties: dict = Field(default_factory=dict)


class SceneSeedRequest(AuthorSeedRequest):
    id: str | None = None
    title: str = Field(..., min_length=1)
    scene_index: int = 1
    pov_character_id: str | None = None
    location_id: str | None = None
    timeline_position: str | None = None
    goal: str | None = None
    conflict: str | None = None
    outcome: str | None = None
    emotional_turn: str | None = None
    required_characters: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_not_violate: list[str] = Field(default_factory=list)
    style_constraints: dict = Field(default_factory=dict)
    previous_scene_id: str | None = None
    status: str = "planned"
    properties: dict = Field(default_factory=dict)


class WorldRuleSeedRequest(AuthorSeedRequest):
    id: str | None = None
    domain: str = Field(..., min_length=1)
    rule: str = Field(..., min_length=1)
    severity: str = "medium"
    examples: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    properties: dict = Field(default_factory=dict)


class StyleSampleRequest(BaseModel):
    id: str | None = None
    text: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    pov: str | None = None
    tone: str | None = None
    dialogue_style: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None


class ReviewRequest(BaseModel):
    reviewer: str = Field("author", min_length=1)
    note: str | None = None


class DemoSeedRequest(BaseModel):
    reviewer: str = Field("author", min_length=1)
    rationale: str = Field(
        "作者明确初始化内置奇幻演示项目。",
        min_length=1,
    )
    source_ref: str = Field("demo:fantasy_project_v1", min_length=1)


class DraftRequest(BaseModel):
    text: str | None = None
    summary: str | None = None


class StateExtractionRequest(BaseModel):
    output_target: Literal["candidate_store", "proposal_workspace"] = "candidate_store"


class SceneGenerationRunRequest(BaseModel):
    output_target: Literal["draft_store", "proposal_workspace"] = "draft_store"


class ProposalCreateRequest(BaseModel):
    id: str | None = None
    artifact_type: ProposalArtifactType
    title: str = Field(..., min_length=1)
    body: str = ""
    body_format: ProposalBodyFormat = "markdown"
    target_refs: list[ProposalRef] = Field(default_factory=list)
    source_refs: list[ProposalRef] = Field(default_factory=list)
    created_by: str = Field("author", min_length=1)
    created_via: ProposalCreatedVia = "manual"
    workflow_run_id: str | None = None
    model_ref: str | None = None
    provenance_note: str | None = None


class ProposalUpdateRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    body_format: ProposalBodyFormat | None = None
    target_refs: list[ProposalRef] | None = None
    source_refs: list[ProposalRef] | None = None
    actor: str = Field("author", min_length=1)
    created_via: ProposalCreatedVia = "manual"
    note: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class ProposalReviseRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    body_format: ProposalBodyFormat | None = None
    target_refs: list[ProposalRef] | None = None
    source_refs: list[ProposalRef] | None = None
    actor: str = Field("agent", min_length=1)
    created_via: ProposalCreatedVia = "llm"
    note: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class ProposalSubmitReviewRequest(BaseModel):
    actor: str = Field("author", min_length=1)
    note: str | None = None
    expected_version: int | None = Field(default=None, ge=1)


class ProposalReviewRequest(BaseModel):
    decision: Literal["accepted", "rejected"]
    reviewer: str = Field("author", min_length=1)
    note: str | None = None
    expected_version: int = Field(..., ge=1)


class ProposalDecisionRequest(ReviewRequest):
    expected_version: int = Field(..., ge=1)


class ProposalPromoteDraftRequest(BaseModel):
    scene_id: str = Field(..., min_length=1)
    summary: str | None = None
    actor: str = Field("author", min_length=1)
    expected_version: int | None = Field(default=None, ge=1)


class ProposalExtractCandidatesRequest(BaseModel):
    source_draft_id: str = Field(..., min_length=1)
    actor: str = Field("author", min_length=1)
    expected_version: int | None = Field(default=None, ge=1)


class EditAcceptRequest(ReviewRequest):
    patch_properties: dict = Field(default_factory=dict)


def create_app(settings: StoryGraphSettings | None = None) -> FastAPI:
    app = FastAPI(title="StoryGraph Agent", version="0.1.3")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    use_persistent_stores = settings is not None
    settings = settings or StoryGraphSettings()
    if use_persistent_stores:
        settings.ensure_workspace()
    agent_config = load_agent_config(settings)
    apply_agent_config(settings, agent_config)
    configured_graph = open_configured_graph_store(
        settings,
        default_backend="memory",
        seed_demo=True,
    )
    graph = configured_graph.graph

    def persist_graph() -> None:
        save_configured_graph_store(configured_graph, settings)
    draft_store = SQLiteDraftStore(settings.draft_store_path if use_persistent_stores else ":memory:")
    candidate_store = SQLiteCandidateStore(
        settings.candidate_store_path if use_persistent_stores else ":memory:"
    )
    proposal_store = SQLiteProposalStore(
        settings.proposal_store_path if use_persistent_stores else ":memory:"
    )
    workflow_store = SQLiteWorkflowStore(
        settings.workflow_store_path if use_persistent_stores else ":memory:"
    )
    style_sample_store = SQLiteStyleSampleStore(
        settings.style_sample_store_path if use_persistent_stores else ":memory:"
    )
    context_builder = ContextPackBuilder(graph, draft_store, style_sample_store)
    checker = RuleBasedContinuityChecker()
    extractor = RuleBasedStateExtractor()
    review = ReviewService(candidate_store, graph)
    canon_seed = AuthorCanonSeedService(graph)
    graph_query = GraphQueryService(graph)
    scene_workflow = SceneGenerationWorkflow(
        context_builder=context_builder,
        writer=RuleBasedSceneWriter(draft_store),
        checker=checker,
        extractor=extractor,
        workflow_store=workflow_store,
        review_service=review,
        proposal_store=proposal_store,
        runtime_kind=settings.workflow_runtime,
        checkpoint_path=str(settings.workflow_checkpoint_path),
    )

    def require_permission(required: AgentPermissionLevel) -> None:
        if not has_permission(agent_config.permission_level, required):
            raise HTTPException(
                status_code=403,
                detail={
                    "category": "permission_denied",
                    "message": (
                        "当前权限为"
                        f"“{_permission_label(agent_config.permission_level)}"
                        f"（{agent_config.permission_level}）”，"
                        f"不允许执行“{_permission_label(required)}（{required}）”级操作。"
                    ),
                },
            )

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "persistent_stores": use_persistent_stores,
            "workspace": str(settings.workspace_dir),
            "graph_backend": configured_graph.backend,
            "workflow_runtime": settings.workflow_runtime,
            "scene_writer": settings.scene_writer,
            "llm_configured": bool(settings.llm_base_url and settings.llm_api_key),
            "permission_level": agent_config.permission_level,
        }

    @app.get("/settings/agent")
    def get_agent_settings() -> dict:
        return _agent_settings_payload(agent_config)

    @app.put("/settings/agent")
    def put_agent_settings(request: AgentRuntimeConfigUpdate) -> dict:
        nonlocal agent_config
        agent_config = update_agent_config(agent_config, request)
        apply_agent_config(settings, agent_config)
        if use_persistent_stores:
            save_agent_config(settings, agent_config)
        return _agent_settings_payload(agent_config)

    @app.post("/projects")
    def create_project(request: CreateProjectRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        project_id = slug_id("project", request.title)
        try:
            graph.seed_canon_node(
                node_id=project_id,
                node_type="Project",
                properties={
                    "title": request.title,
                    "genre": request.genre,
                    "language": request.language,
                    "target_length": request.target_length,
                    "narrative_pov": request.narrative_pov,
                },
                source_ref="api:projects",
                reviewer="author",
                rationale="作者通过 API 创建项目。",
            )
        except GraphStoreError as exc:
            raise _graph_http_exception(exc) from exc
        persist_graph()
        return {"project_id": project_id}

    @app.get("/projects")
    def list_projects() -> dict:
        return {"projects": graph_query.list_projects()}

    @app.get("/projects/{project_id}")
    def get_project(project_id: str) -> dict:
        try:
            return graph_query.get_node(project_id=project_id, node_id=project_id).model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/outline")
    def get_project_outline(project_id: str) -> dict:
        try:
            return graph_query.project_outline(project_id=project_id)
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/characters")
    def add_character(project_id: str, request: CharacterSeedRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            node = canon_seed.add_character(
                project_id=project_id,
                node_id=request.id,
                name=request.name,
                properties=request.properties,
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return node.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/locations")
    def add_location(project_id: str, request: LocationSeedRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            node = canon_seed.add_location(
                project_id=project_id,
                node_id=request.id,
                name=request.name,
                properties=request.properties,
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return node.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/chapters")
    def add_chapter(project_id: str, request: ChapterSeedRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            node = canon_seed.add_chapter(
                project_id=project_id,
                node_id=request.id,
                title=request.title,
                properties={
                    "volume_index": request.volume_index,
                    "chapter_index": request.chapter_index,
                    "summary": request.summary,
                    "purpose": request.purpose,
                    "status": request.status,
                    **request.properties,
                },
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return node.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/chapters/{chapter_id}/scenes")
    def add_scene(project_id: str, chapter_id: str, request: SceneSeedRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            node = canon_seed.add_scene(
                project_id=project_id,
                chapter_id=chapter_id,
                node_id=request.id,
                title=request.title,
                properties={
                    "scene_index": request.scene_index,
                    "pov_character_id": request.pov_character_id,
                    "location_id": request.location_id,
                    "timeline_position": request.timeline_position,
                    "goal": request.goal,
                    "conflict": request.conflict,
                    "outcome": request.outcome,
                    "emotional_turn": request.emotional_turn,
                    "required_characters": request.required_characters,
                    "must_include": request.must_include,
                    "must_not_violate": request.must_not_violate,
                    "style_constraints": request.style_constraints,
                    "previous_scene_id": request.previous_scene_id,
                    "status": request.status,
                    **request.properties,
                },
                previous_scene_id=request.previous_scene_id,
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return node.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/world-rules")
    def add_world_rule(project_id: str, request: WorldRuleSeedRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            node = canon_seed.add_world_rule(
                project_id=project_id,
                node_id=request.id,
                domain=request.domain,
                rule=request.rule,
                properties={
                    "severity": request.severity,
                    "examples": request.examples,
                    "exceptions": request.exceptions,
                    **request.properties,
                },
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return node.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/relations")
    def add_relation(project_id: str, request: RelationSeedRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            relation = canon_seed.add_relation(
                project_id=project_id,
                relation_id=request.id,
                relation_type=request.type,
                source_id=request.source_id,
                target_id=request.target_id,
                properties=request.properties,
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return relation.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/style-samples")
    def add_style_sample(project_id: str, request: StyleSampleRequest) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            graph.get_node(project_id)
            sample = StyleSample(
                id=request.id or new_id("style_sample"),
                project_id=project_id,
                text=request.text,
                source_ref=request.source_ref,
                pov=request.pov,
                tone=request.tone,
                dialogue_style=request.dialogue_style,
                tags=request.tags,
                summary=request.summary,
                created_at=utc_now(),
            )
            return style_sample_store.add(sample).model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/proposals")
    def create_proposal(project_id: str, request: ProposalCreateRequest) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            _ensure_project_exists(graph, project_id)
            now = utc_now()
            proposal = ProposalArtifact(
                id=request.id or new_id("proposal"),
                project_id=project_id,
                artifact_type=request.artifact_type,
                status="drafting",
                title=request.title,
                body=request.body,
                body_format=request.body_format,
                target_refs=request.target_refs,
                source_refs=request.source_refs,
                provenance=ProposalProvenance(
                    created_by=request.created_by,
                    created_via=request.created_via,
                    workflow_run_id=request.workflow_run_id,
                    model_ref=request.model_ref,
                    note=request.provenance_note,
                ),
                version=1,
                created_at=now,
                updated_at=now,
            )
            return proposal_store.create(proposal).model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/proposals")
    def list_proposals(
        project_id: str,
        status: str | None = None,
        artifact_type: str | None = None,
    ) -> dict:
        proposals = proposal_store.list(
            project_id=project_id,
            status=status,
            artifact_type=artifact_type,
        )
        return {"proposals": [proposal.model_dump() for proposal in proposals]}

    @app.get("/projects/{project_id}/proposals/{proposal_id}")
    def get_proposal(project_id: str, proposal_id: str, version: int | None = None) -> dict:
        try:
            proposal = proposal_store.get(proposal_id, version=version)
            _ensure_proposal_project(proposal, project_id)
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/projects/{project_id}/proposals/{proposal_id}/versions")
    def proposal_versions(project_id: str, proposal_id: str) -> dict:
        try:
            versions = proposal_store.history(proposal_id)
            if versions:
                _ensure_proposal_project(versions[-1], project_id)
            return {"versions": [proposal.model_dump() for proposal in versions]}
        except ContractError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/projects/{project_id}/proposals/{proposal_id}")
    def update_proposal(
        project_id: str,
        proposal_id: str,
        request: ProposalUpdateRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            _ensure_proposal_project(proposal_store.get(proposal_id), project_id)
            proposal = proposal_store.revise(
                proposal_id,
                actor=request.actor,
                created_via=request.created_via,
                title=request.title,
                body=request.body,
                body_format=request.body_format,
                target_refs=request.target_refs,
                source_refs=request.source_refs,
                note=request.note,
                expected_version=request.expected_version,
                status="author_revised",
            )
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/revise")
    def revise_proposal(
        project_id: str,
        proposal_id: str,
        request: ProposalReviseRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            existing = proposal_store.get(proposal_id)
            _ensure_proposal_project(existing, project_id)
            body = request.body
            if body is None:
                _ensure_proposal_artifact_type(existing, "scene_draft")
                target_scene_id = _proposal_target_scene_id(existing)
                context_pack = context_builder.build(project_id=project_id, scene_id=target_scene_id)
                body = create_scene_writer(settings, draft_store).draft(context_pack).text
            proposal = proposal_store.revise(
                proposal_id,
                actor=request.actor,
                created_via=request.created_via,
                title=request.title,
                body=body,
                body_format=request.body_format,
                target_refs=request.target_refs,
                source_refs=request.source_refs,
                note=request.note,
                expected_version=request.expected_version,
                status="agent_revised",
            )
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/submit-review")
    def submit_proposal_review(
        project_id: str,
        proposal_id: str,
        request: ProposalSubmitReviewRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            _ensure_proposal_project(proposal_store.get(proposal_id), project_id)
            proposal = proposal_store.mark_ready(
                proposal_id,
                actor=request.actor,
                note=request.note,
                expected_version=request.expected_version,
            )
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/review")
    def review_proposal(
        project_id: str,
        proposal_id: str,
        request: ProposalReviewRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            _ensure_proposal_project(proposal_store.get(proposal_id), project_id)
            proposal = proposal_store.review(
                proposal_id,
                decision=request.decision,
                reviewer=request.reviewer,
                note=request.note,
                expected_version=request.expected_version,
            )
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/accept")
    def accept_proposal(project_id: str, proposal_id: str, request: ProposalDecisionRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            _ensure_proposal_project(proposal_store.get(proposal_id), project_id)
            proposal = proposal_store.review(
                proposal_id,
                decision="accepted",
                reviewer=request.reviewer,
                note=request.note,
                expected_version=request.expected_version,
            )
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/reject")
    def reject_proposal(project_id: str, proposal_id: str, request: ProposalDecisionRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            _ensure_proposal_project(proposal_store.get(proposal_id), project_id)
            proposal = proposal_store.review(
                proposal_id,
                decision="rejected",
                reviewer=request.reviewer,
                note=request.note,
                expected_version=request.expected_version,
            )
            return proposal.model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/derive-draft")
    @app.post("/projects/{project_id}/proposals/{proposal_id}/promote/draft")
    def promote_proposal_to_draft(
        project_id: str,
        proposal_id: str,
        request: ProposalPromoteDraftRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            proposal = proposal_store.get(proposal_id)
            _ensure_proposal_project(proposal, project_id)
            _ensure_proposal_promotable(proposal, request.expected_version)
            _ensure_proposal_artifact_type(proposal, "scene_draft")
            graph_query.scene_node(project_id=project_id, scene_id=request.scene_id)
            draft = draft_store.create_draft(
                project_id=project_id,
                scene_id=request.scene_id,
                text=proposal.body,
                summary=request.summary or f"由协作草稿 {proposal.id} v{proposal.version} 转为场景草稿。",
            )
            updated_proposal = proposal_store.record_derived_ref(
                proposal_id,
                derived_ref=ProposalRef(
                    kind="draft",
                    ref=draft.id,
                    note=f"Current scene draft derived from proposal v{proposal.version}.",
                ),
                actor=request.actor,
                note="Promoted proposal content to Draft Store.",
                expected_version=proposal.version,
            )
            return {"proposal": updated_proposal.model_dump(), "draft": draft.model_dump()}
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/submit-canon-review")
    @app.post("/projects/{project_id}/proposals/{proposal_id}/promote/candidate-facts")
    def promote_proposal_to_candidate_facts(
        project_id: str,
        proposal_id: str,
        request: ProposalExtractCandidatesRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            proposal = proposal_store.get(proposal_id)
            _ensure_proposal_project(proposal, project_id)
            _ensure_proposal_promotable(proposal, request.expected_version)
            _ensure_proposal_artifact_type(proposal, "fact_draft")
            source_draft = draft_store.get_draft(request.source_draft_id)
            if source_draft.project_id != project_id:
                raise HTTPException(status_code=404, detail="这个项目中没有找到来源草稿。")
            candidates = [
                _candidate_with_proposal_evidence(candidate, proposal)
                for candidate in extractor.extract(project_id=project_id, draft=source_draft)
            ]
            if not candidates:
                return {
                    "proposal": proposal.model_dump(),
                    "source_draft": source_draft.model_dump(),
                    "candidates": [],
                }
            submitted = review.submit(candidates)
            updated_proposal = proposal
            for candidate in submitted:
                updated_proposal = proposal_store.record_derived_ref(
                    proposal_id,
                    derived_ref=ProposalRef(
                        kind="candidate_fact",
                        ref=candidate.id,
                        note=f"CandidateFact extracted from proposal v{proposal.version}.",
                    ),
                    actor=request.actor,
                    note="Recorded CandidateFact derived from proposal content.",
                    expected_version=updated_proposal.version,
                )
            return {
                "proposal": updated_proposal.model_dump(),
                "source_draft": source_draft.model_dump(),
                "candidates": [candidate.model_dump() for candidate in submitted],
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="没有找到来源草稿。") from exc
        except (ContractError, GraphStoreError, ValueError) as exc:
            if isinstance(exc, ValueError):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise _contract_http_exception(exc) from exc

    @app.get("/demo")
    def demo() -> dict:
        return {"project_id": PROJECT_ID, "scene_id": SCENE_ID}

    @app.post("/demo/seed")
    def seed_demo(request: DemoSeedRequest | None = None) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        request = request or DemoSeedRequest()
        demo_graph = build_fantasy_demo_graph()
        nodes_created = 0
        relationships_created = 0
        nodes_skipped: list[str] = []
        relationships_skipped: list[str] = []

        for node in sorted(demo_graph.nodes.values(), key=lambda item: item.id):
            try:
                graph.seed_canon_node(
                    node_id=node.id,
                    node_type=node.type,
                    properties=node.properties,
                    source_ref=request.source_ref,
                    reviewer=request.reviewer,
                    rationale=request.rationale,
                )
                nodes_created += 1
            except GraphStoreError as exc:
                if exc.category != "duplicate_id":
                    raise _graph_http_exception(exc) from exc
                nodes_skipped.append(node.id)

        for relation in sorted(demo_graph.relationships.values(), key=lambda item: item.id):
            try:
                graph.seed_canon_relation(
                    relation_id=relation.id,
                    relation_type=relation.type,
                    source_id=relation.source_id,
                    target_id=relation.target_id,
                    properties=relation.properties,
                    source_ref=request.source_ref,
                    reviewer=request.reviewer,
                    rationale=request.rationale,
                )
                relationships_created += 1
            except GraphStoreError as exc:
                if exc.category != "duplicate_id":
                    raise _graph_http_exception(exc) from exc
                relationships_skipped.append(relation.id)

        persist_graph()
        return {
            "project_id": PROJECT_ID,
            "scene_id": SCENE_ID,
            "nodes_created": nodes_created,
            "relationships_created": relationships_created,
            "nodes_skipped": nodes_skipped,
            "relationships_skipped": relationships_skipped,
        }

    @app.get("/projects/{project_id}/graph/query")
    def query_graph(
        project_id: str,
        source_id: str,
        hop_limit: int = 1,
        edge_labels: str | None = None,
        node_labels: str | None = None,
        statuses: str | None = None,
    ) -> dict:
        try:
            return graph_query.query_neighbors(
                project_id=project_id,
                source_id=source_id,
                hop_limit=hop_limit,
                edge_labels=_csv(edge_labels),
                node_labels=_csv(node_labels),
                statuses=_csv(statuses),  # type: ignore[arg-type]
            )
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/graph/preview")
    def project_graph_preview(project_id: str) -> dict:
        try:
            return graph_query.project_graph_preview(project_id=project_id)
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/scenes/{scene_id}")
    def get_scene(project_id: str, scene_id: str) -> dict:
        try:
            return graph_query.scene_node(project_id=project_id, scene_id=scene_id)
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/scenes/{scene_id}/context-pack")
    def build_context(project_id: str, scene_id: str) -> dict:
        return context_builder.build(project_id=project_id, scene_id=scene_id).model_dump()

    @app.get("/projects/{project_id}/scenes/{scene_id}/draft")
    def latest_draft(project_id: str, scene_id: str) -> dict:
        draft = draft_store.latest_for_scene(project_id, scene_id)
        return {"draft": draft.model_dump() if draft else None}

    @app.post("/projects/{project_id}/scenes/{scene_id}/draft")
    def write_draft(project_id: str, scene_id: str, request: DraftRequest | None = None) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        if request and request.text is not None:
            return draft_store.create_draft(
                project_id=project_id,
                scene_id=scene_id,
                text=request.text,
                summary=request.summary,
            ).model_dump()
        context_pack = context_builder.build(project_id=project_id, scene_id=scene_id)
        return create_scene_writer(settings, draft_store).write_and_save(context_pack).model_dump()

    @app.post("/projects/{project_id}/scenes/{scene_id}/check-continuity")
    def check_continuity(project_id: str, scene_id: str) -> dict:
        context_pack = context_builder.build(project_id=project_id, scene_id=scene_id)
        draft = draft_store.latest_for_scene(project_id, scene_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="这个场景还没有草稿。")
        return checker.check(context_pack=context_pack, draft=draft).model_dump()

    @app.post("/projects/{project_id}/scenes/{scene_id}/extract-state")
    def extract_state(
        project_id: str,
        scene_id: str,
        request: StateExtractionRequest | None = None,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        request = request or StateExtractionRequest()
        draft = draft_store.latest_for_scene(project_id, scene_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="这个场景还没有草稿。")
        candidates = extractor.extract(project_id=project_id, draft=draft)
        if request.output_target == "proposal_workspace":
            now = utc_now()
            proposal = ProposalArtifact(
                id=new_id("proposal"),
                project_id=project_id,
                artifact_type="fact_draft",
                status="agent_revised",
                title=f"候选事实提案：{scene_id}",
                body=json.dumps(
                    {
                        "source_draft_id": draft.id,
                        "candidate_previews": [
                            candidate.model_dump() for candidate in candidates
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                body_format="structured_json",
                target_refs=[
                    ProposalRef(kind="scene", ref=scene_id),
                    ProposalRef(kind="draft", ref=draft.id),
                ],
                source_refs=[ProposalRef(kind="draft", ref=draft.id)],
                provenance=ProposalProvenance(
                    created_by="agent",
                    created_via="api",
                    note="State extraction wrote CandidateFact previews to Proposal Store.",
                ),
                version=1,
                created_at=now,
                updated_at=now,
            )
            return {
                "proposal": proposal_store.create(proposal).model_dump(),
                "candidate_previews": [candidate.model_dump() for candidate in candidates],
                "candidates": [],
            }
        try:
            review.submit(candidates)
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"candidates": [candidate.model_dump() for candidate in candidates]}

    @app.post("/projects/{project_id}/scenes/{scene_id}/runs/scene-generation")
    def run_scene_generation(
        project_id: str,
        scene_id: str,
        request: SceneGenerationRunRequest | None = None,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        request = request or SceneGenerationRunRequest()
        workflow = SceneGenerationWorkflow(
            context_builder=context_builder,
            writer=create_scene_writer(settings, draft_store),
            checker=checker,
            extractor=extractor,
            workflow_store=workflow_store,
            review_service=review,
            proposal_store=proposal_store,
            runtime_kind=settings.workflow_runtime,
            checkpoint_path=str(settings.workflow_checkpoint_path),
        )
        try:
            result = workflow.run(
                project_id=project_id,
                scene_id=scene_id,
                output_target=request.output_target,
            )
        finally:
            workflow.close()
        return {
            "context_pack": result.context_pack.model_dump(),
            "draft": result.draft.model_dump() if result.draft else None,
            "proposal": result.proposal.model_dump() if result.proposal else None,
            "continuity_report": (
                result.continuity_report.model_dump() if result.continuity_report else None
            ),
            "candidates": [candidate.model_dump() for candidate in result.candidates],
            "workflow_run": result.workflow_run.model_dump() if result.workflow_run else None,
        }

    @app.get("/projects/{project_id}/runs")
    def list_runs(project_id: str, status: str | None = None) -> dict:
        return {
            "runs": [
                run.model_dump()
                for run in workflow_store.list(project_id=project_id, status=status)
            ]
        }

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        try:
            return workflow_store.get(run_id).model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=404, detail="没有找到这次工作流运行。") from exc

    @app.get("/runs/{run_id}/events")
    def get_run_events(run_id: str) -> dict:
        try:
            run = workflow_store.get(run_id)
        except ContractError as exc:
            raise HTTPException(status_code=404, detail="没有找到这次工作流运行。") from exc
        return {"events": _workflow_events(run)}

    @app.post("/runs/{run_id}/resume-review")
    def resume_review(run_id: str) -> dict:
        try:
            return scene_workflow.resume_review(run_id).model_dump()
        except ContractError as exc:
            raise HTTPException(status_code=404, detail="没有找到这次工作流运行。") from exc

    @app.get("/projects/{project_id}/facts/pending")
    def pending_facts(project_id: str) -> dict:
        return {"facts": [fact.model_dump() for fact in review.pending(project_id=project_id)]}

    @app.post("/projects/{project_id}/facts/{fact_id}/accept")
    def accept_fact(project_id: str, fact_id: str, request: ReviewRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        _ensure_candidate_project(candidate_store, fact_id, project_id)
        try:
            fact = review.accept(fact_id, reviewer=request.reviewer, note=request.note)
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        persist_graph()
        return fact.model_dump()

    @app.post("/projects/{project_id}/facts/{fact_id}/edit-accept")
    def edit_accept_fact(project_id: str, fact_id: str, request: EditAcceptRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        _ensure_candidate_project(candidate_store, fact_id, project_id)
        try:
            fact = review.edit_and_accept(
                fact_id,
                reviewer=request.reviewer,
                patch_properties=request.patch_properties,
                note=request.note,
            )
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        persist_graph()
        return fact.model_dump()

    @app.post("/projects/{project_id}/facts/{fact_id}/reject")
    def reject_fact(project_id: str, fact_id: str, request: ReviewRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        _ensure_candidate_project(candidate_store, fact_id, project_id)
        try:
            fact = review.reject(fact_id, reviewer=request.reviewer, note=request.note)
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return fact.model_dump()

    @app.post("/projects/{project_id}/facts/{fact_id}/defer")
    def defer_fact(project_id: str, fact_id: str, request: ReviewRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        _ensure_candidate_project(candidate_store, fact_id, project_id)
        try:
            fact = review.defer(fact_id, reviewer=request.reviewer, note=request.note)
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return fact.model_dump()

    return app


def _ensure_candidate_project(
    candidate_store: CandidateStore, fact_id: str, project_id: str
) -> None:
    try:
        fact = candidate_store.get(fact_id)
    except ContractError as exc:
        raise HTTPException(status_code=404, detail="没有找到这个候选事实。") from exc
    if fact.project_id != project_id:
        raise HTTPException(status_code=404, detail="这个项目中没有找到该候选事实。")


def _ensure_project_exists(graph, project_id: str) -> None:
    graph.get_node(project_id)


def _ensure_proposal_project(proposal: ProposalArtifact, project_id: str) -> None:
    if proposal.project_id != project_id:
        raise HTTPException(status_code=404, detail="这个项目中没有找到该协作草稿。")


def _ensure_proposal_promotable(
    proposal: ProposalArtifact,
    expected_version: int | None,
) -> None:
    if expected_version is not None and proposal.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=(
                "协作草稿版本已变化："
                f"期望 v{expected_version}，当前 v{proposal.version}。"
            ),
        )
    if proposal.status != "accepted":
        raise HTTPException(status_code=409, detail="只有已接受的协作草稿可以执行提升。")


def _ensure_proposal_artifact_type(
    proposal: ProposalArtifact,
    artifact_type: str,
) -> None:
    if proposal.artifact_type != artifact_type:
        raise HTTPException(
            status_code=409,
            detail=f"该操作要求协作草稿类型为 {artifact_type}。",
        )


def _proposal_target_scene_id(proposal: ProposalArtifact) -> str:
    scene_ref = next((ref.ref for ref in proposal.target_refs if ref.kind == "scene"), None)
    if not scene_ref:
        raise HTTPException(status_code=409, detail="该协作草稿缺少目标场景。")
    return scene_ref


def _candidate_with_proposal_evidence(candidate, proposal: ProposalArtifact):
    return candidate.model_copy(
        update={
            "evidence": [
                *candidate.evidence,
                EvidenceItem(
                    kind="proposal_artifact",
                    ref=f"{proposal.id}@v{proposal.version}",
                    note="Explicitly promoted from an accepted proposal artifact.",
                ),
            ]
        }
    )


def _contract_http_exception(exc: ContractError | GraphStoreError) -> HTTPException:
    if isinstance(exc, GraphStoreError):
        return _graph_http_exception(exc)
    return HTTPException(status_code=409, detail={"category": "contract_error", "message": str(exc)})


def _graph_http_exception(exc: GraphStoreError) -> HTTPException:
    status_code = 404 if exc.category == "not_found" else 409
    return HTTPException(
        status_code=status_code,
        detail={"category": exc.category, "message": str(exc)},
    )


def _csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _agent_settings_payload(config: AgentRuntimeConfig) -> dict:
    response = config_response(config).model_dump()
    response["permission_descriptions"] = {
        "read_only": "只能读取 canon（正典）、草稿、协作草稿、上下文包、运行记录和待审事实。",
        "read_generate": "可读取并生成草稿、协作草稿、检查结果、候选事实和风格样本。",
        "full": "允许完整本地作者操作，包括人工初始化（seed）、协作草稿决策和 CandidateFact（候选事实）审阅决策。",
    }
    return response


def _permission_label(level: AgentPermissionLevel) -> str:
    labels = {
        AgentPermissionLevel.READ_ONLY: "仅读取",
        AgentPermissionLevel.READ_GENERATE: "可读取生成",
        AgentPermissionLevel.FULL: "完全权限",
    }
    return labels[level]


def _cors_origins() -> list[str]:
    configured = os.environ.get("STORYGRAPH_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ]


def _workflow_events(run) -> list[dict]:
    return [
        {
            "run_id": run.id,
            "workflow_name": run.workflow_name,
            "step": step.name,
            "status": step.status,
            "started_at": step.started_at,
            "completed_at": step.completed_at,
            "artifact_refs": step.artifact_refs,
            "message": step.message,
        }
        for step in run.steps
    ]


app = create_app()
