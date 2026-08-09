"""Minimal FastAPI surface for the StoryGraph MVP."""

from __future__ import annotations

import os
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
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
from storygraph.models.candidate import CandidateFact
from storygraph.models.common import EvidenceItem
from storygraph.models.draft import Draft
from storygraph.models.source import (
    SourceDocument,
    SourceImportProvenance,
    canonicalize_source_language,
    validate_safe_source_metadata,
)
from storygraph.models.style import StyleSample
from storygraph.models.project import (
    DEFAULT_OUTPUT_LANGUAGE,
    CrossLanguagePolicy,
    OutputLanguage,
    localized,
    validate_output_language,
)
from storygraph.services import (
    AgentDiscussionService,
    AuthorCanonSeedService,
    ContextPackBuilder,
    DiscussionSource,
    GraphQueryService,
    LLMDocumentFactExtractor,
    LLMProjectStructureAnalyzer,
    ReviewService,
    RuleBasedContinuityChecker,
    RuleBasedProjectStructureAnalyzer,
    RuleBasedSceneWriter,
    RuleBasedStateExtractor,
    create_llm_provider,
    create_scene_writer,
)
from storygraph.stores import (
    CandidateStore,
    SQLiteCandidateStore,
    SQLiteDraftStore,
    SQLiteProposalStore,
    SQLiteSourceDocumentStore,
    SQLiteStyleSampleStore,
)
from storygraph.stores.graph_factory import open_configured_graph_store, save_configured_graph_store
from storygraph.stores.memory_graph import InMemoryGraphStore
from storygraph.stores.workflow_store import SQLiteWorkflowStore
from storygraph.services.project_language import resolve_project_output_language
from storygraph.services.project_language import enforce_source_language_policy
from storygraph.services.project_language import project_language_projection
from storygraph.workflows import SceneGenerationWorkflow


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    genre: str = "fantasy"
    language: OutputLanguage = "zh-CN"
    target_length: str | None = None
    narrative_pov: str | None = None

    @field_validator("language", mode="before")
    @classmethod
    def legacy_project_language(cls, value):
        return {"zh_CN": "zh-CN", "en_US": "en-US"}.get(value, value)

class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    genre: str | None = None
    language: OutputLanguage | None = None
    expected_language: str | None = Field(default=None, min_length=1, max_length=35)
    language_change_policy: Literal["future_outputs_only"] | None = None
    target_length: str | None = None
    narrative_pov: str | None = None
    reviewer: str = Field("author", min_length=1)
    rationale: str = Field("作者从工作台编辑项目信息。", min_length=1)
    source_ref: str = Field("author_seed:workbench_project", min_length=1)

    @field_validator("language", mode="before")
    @classmethod
    def legacy_project_language(cls, value):
        return {"zh_CN": "zh-CN", "en_US": "en-US"}.get(value, value)

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


class ChapterUpdateRequest(AuthorSeedRequest):
    title: str | None = None
    volume_index: int | None = Field(default=None, ge=1)
    chapter_index: int | None = Field(default=None, ge=1)
    summary: str | None = None
    purpose: str | None = None
    status: str | None = None


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


class SceneUpdateRequest(AuthorSeedRequest):
    title: str | None = None
    scene_index: int | None = Field(default=None, ge=1)
    pov_character_id: str | None = None
    location_id: str | None = None
    timeline_position: str | None = None
    goal: str | None = None
    conflict: str | None = None
    outcome: str | None = None
    emotional_turn: str | None = None
    required_characters: list[str] | None = None
    must_include: list[str] | None = None
    must_not_violate: list[str] | None = None
    style_constraints: dict | None = None
    previous_scene_id: str | None = None
    status: str | None = None


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
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field("author", min_length=1)
    rationale: str = Field(
        "作者明确初始化内置奇幻演示项目。",
        min_length=1,
    )
    source_ref: str = Field("demo:fantasy_project_v1", min_length=1)
    locale: OutputLanguage = "zh-CN"
    overwrite_existing: bool = True

    @field_validator("locale", mode="before")
    @classmethod
    def legacy_demo_locale(cls, value):
        return {"zh_CN": "zh-CN", "en_US": "en-US"}.get(value, value)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = None
    summary: str | None = None


class StateExtractionRequest(BaseModel):
    output_target: Literal["candidate_store", "proposal_workspace"] = "candidate_store"


class DocumentFactExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    source_language: str = Field(..., min_length=1, max_length=35)
    cross_language_policy: CrossLanguagePolicy = "project_only"
    max_facts: int = Field(16, ge=1, le=32)

    @field_validator("source_language")
    @classmethod
    def canonical_source_language(cls, value: str) -> str:
        return canonicalize_source_language(value)

    @field_validator("source_ref")
    @classmethod
    def safe_source_ref(cls, value: str) -> str:
        return validate_safe_source_metadata(value, field_name="source_ref") or ""


class ProjectStructureDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    source_language: str = Field(..., min_length=1, max_length=35)
    cross_language_policy: CrossLanguagePolicy = "project_only"
    max_chapters: int = Field(12, ge=1, le=40)
    max_scenes_per_chapter: int = Field(8, ge=1, le=24)

    @field_validator("source_language")
    @classmethod
    def canonical_source_language(cls, value: str) -> str:
        return canonicalize_source_language(value)

    @field_validator("source_ref")
    @classmethod
    def safe_source_ref(cls, value: str) -> str:
        return validate_safe_source_metadata(value, field_name="source_ref") or ""


class SourceDocumentImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=500)
    relative_path: str = Field(..., min_length=1, max_length=2048)
    media_type: Literal[
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    language: str = Field(..., min_length=1, max_length=35)
    byte_size: int = Field(..., ge=0)
    checksum_sha256: str = Field(..., min_length=64, max_length=64)
    extraction_status: Literal["ready", "failed"]
    extracted_text: str | None = None
    warnings: list[str] = Field(default_factory=list, max_length=32)
    error: str | None = Field(default=None, max_length=500)
    provenance: SourceImportProvenance

    @field_validator("language")
    @classmethod
    def canonical_language(cls, value: str) -> str:
        return canonicalize_source_language(value)


class SourceStructureDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_chapters: int = Field(12, ge=1, le=40)
    max_scenes_per_chapter: int = Field(8, ge=1, le=24)
    cross_language_policy: CrossLanguagePolicy = "project_only"


class SourceDocumentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(..., min_length=1, max_length=35)
    expected_updated_at: str = Field(..., min_length=1)

    @field_validator("language")
    @classmethod
    def canonical_language(cls, value: str) -> str:
        return canonicalize_source_language(value)


class SceneGenerationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_target: Literal["draft_store", "proposal_workspace"] = "draft_store"


class AgentDiscussionSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "imported_document"
    ref: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1, max_length=35)
    note: str | None = None

    @field_validator("language")
    @classmethod
    def canonical_language(cls, value: str) -> str:
        return canonicalize_source_language(value)

    @field_validator("ref", "title")
    @classmethod
    def safe_source_identity(cls, value: str) -> str:
        return validate_safe_source_metadata(value, field_name="inline source metadata") or ""

    @field_validator("note")
    @classmethod
    def safe_source_note(cls, value: str | None) -> str | None:
        return validate_safe_source_metadata(value, field_name="inline source note")


class AgentDiscussionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["discuss", "revise_selection", "revise_scene"] = "discuss"
    instruction: str = Field(..., min_length=1)
    selected_text: str | None = None
    base_text: str | None = None
    include_context_pack: bool = True
    include_latest_draft: bool = True
    local_sources: list[AgentDiscussionSourceRequest] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list, max_length=32)
    allow_web_search: bool = False
    web_search_query: str | None = None
    cross_language_policy: CrossLanguagePolicy = "project_only"


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


class ProposalApplyProjectStructureRequest(BaseModel):
    reviewer: str = Field("author", min_length=1)
    rationale: str = Field("作者确认导入文档生成的项目结构草稿。", min_length=1)
    source_ref: str | None = None
    expected_version: int = Field(..., ge=1)


class EditAcceptRequest(ReviewRequest):
    patch_properties: dict = Field(default_factory=dict)


def create_app(settings: StoryGraphSettings | None = None) -> FastAPI:
    app = FastAPI(title="StoryGraph Agent", version="0.1.9")

    @app.exception_handler(RequestValidationError)
    async def sanitized_request_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "type": error.get("type", "validation_error"),
                        "loc": list(error.get("loc", ())),
                        "msg": error.get("msg", "Invalid request."),
                    }
                    for error in exc.errors()
                ]
            },
        )

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
    source_store = SQLiteSourceDocumentStore(
        settings.source_store_path if use_persistent_stores else ":memory:"
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

    def build_project_structure_draft(
        *,
        project_id: str,
        title: str,
        source_text: str,
        source_ref: ProposalRef,
        max_chapters: int,
        max_scenes_per_chapter: int,
        source_language: str,
        cross_language_policy: CrossLanguagePolicy,
    ) -> dict:
        output_language = resolve_project_output_language(graph, project_id)
        enforce_source_language_policy(
            output_language=output_language,
            source_languages=[source_language],
            policy=cross_language_policy,
        )
        if _llm_is_configured(settings):
            analyzer = LLMProjectStructureAnalyzer(
                provider=create_llm_provider(settings),
                model=settings.llm_model,
                output_language=output_language,
                max_chapters=max_chapters,
                max_scenes_per_chapter=max_scenes_per_chapter,
            )
            model_ref = f"{agent_config.provider_label}/{settings.llm_model}"
        else:
            analyzer = RuleBasedProjectStructureAnalyzer(
                output_language=output_language,
                max_chapters=max_chapters,
                max_scenes_per_chapter=max_scenes_per_chapter,
            )
            model_ref = None
        draft = analyzer.analyze(
            project_id=project_id,
            title=title,
            source_text=source_text,
            source_language=source_language,
            cross_language_policy=cross_language_policy,
        )
        now = utc_now()
        proposal = ProposalArtifact(
            id=new_id("proposal"),
            project_id=project_id,
            content_language=output_language,
            artifact_type="project_structure_draft",
            status="agent_revised",
            title=localized(
                output_language,
                zh=f"项目结构草稿：{title}",
                en=f"Project structure draft: {title}",
            ),
            body=draft.body,
            body_format="structured_json",
            target_refs=[ProposalRef(kind="project", ref=project_id)],
            source_refs=[source_ref],
            provenance=ProposalProvenance(
                created_by="agent",
                created_via=draft.created_via,  # type: ignore[arg-type]
                model_ref=model_ref,
                note=localized(
                    output_language,
                    zh=(
                        "智能体根据导入资料生成了项目章节与场景提案；"
                        f"cross_language_policy={cross_language_policy}。"
                    ),
                    en=(
                        "Agent proposed project chapters and scenes from an imported "
                        f"document; cross_language_policy={cross_language_policy}."
                    ),
                ),
            ),
            version=1,
            created_at=now,
            updated_at=now,
        )
        stored = proposal_store.create(proposal)
        return {
            "proposal": stored.model_dump(),
            "outline": draft.outline,
            "truncated": draft.truncated,
            "output_language": output_language,
            "cross_language_policy": cross_language_policy,
        }

    def get_project_source(project_id: str, source_document_id: str) -> SourceDocument:
        _ensure_project_exists(graph, project_id)
        try:
            return source_store.get(
                project_id=project_id,
                source_id=source_document_id,
            )
        except ContractError as exc:
            raise HTTPException(
                status_code=404,
                detail="这个项目中没有找到该来源文档。",
            ) from exc

    def resolve_discussion_source_documents(
        project_id: str,
        source_document_ids: list[str],
    ) -> list[DiscussionSource]:
        resolved: list[DiscussionSource] = []
        seen: set[str] = set()
        for source_document_id in source_document_ids:
            if source_document_id in seen:
                continue
            seen.add(source_document_id)
            document = get_project_source(project_id, source_document_id)
            if document.extraction_status != "ready" or not document.extracted_text:
                raise HTTPException(
                    status_code=409,
                    detail="Agent 只能读取已成功提取正文的来源文档。",
                )
            resolved.append(
                DiscussionSource(
                    kind="source_document",
                    ref=document.id,
                    title=document.title,
                    text=document.extracted_text,
                    language=document.language,
                    note=document.relative_path,
                )
            )
        return resolved

    def resolve_inline_discussion_sources(
        sources: list[AgentDiscussionSourceRequest],
    ) -> list[DiscussionSource]:
        if any(source.kind == "source_document" for source in sources):
            raise HTTPException(
                status_code=409,
                detail=(
                    "持久化来源文档必须通过 source_document_ids 选择，"
                    "不能通过 local_sources 伪造来源引用。"
                ),
            )
        return [
            DiscussionSource(
                kind=source.kind,
                ref=source.ref,
                title=source.title,
                text=source.text,
                language=source.language,
                note=source.note,
            )
            for source in sources
        ]

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
        return {
            "project_id": project_id,
            "language": request.language,
            "language_status": "confirmed",
            "language_inferred": False,
        }

    @app.get("/projects")
    def list_projects() -> dict:
        return {"projects": graph_query.list_projects()}

    @app.get("/projects/{project_id}")
    def get_project(project_id: str) -> dict:
        try:
            project = _ensure_project_exists(graph, project_id)
            return {**project.model_dump(), **project_language_projection(project)}
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.patch("/projects/{project_id}")
    def update_project(project_id: str, request: UpdateProjectRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            project = _ensure_project_exists(graph, project_id)
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc
        stored_language = project.properties.get("language")
        current_language = (
            stored_language if stored_language is not None else DEFAULT_OUTPUT_LANGUAGE
        )
        language_write = (
            request.language is not None and request.language != stored_language
        )
        if language_write:
            if request.expected_language is None or request.language_change_policy is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "修改项目语言时必须提供 expected_language 和 "
                        "language_change_policy=future_outputs_only。"
                    ),
                )
            if request.expected_language != current_language:
                raise HTTPException(
                    status_code=409,
                    detail="项目语言已变化，请刷新后重试。",
                )
        properties = {
            key: value
            for key, value in {
                "title": request.title,
                "genre": request.genre,
                "language": request.language,
                "target_length": request.target_length,
                "narrative_pov": request.narrative_pov,
            }.items()
            if value is not None
        }
        try:
            if language_write:
                node = graph.update_project_language(
                    project_id,
                    expected_language=request.expected_language or current_language,
                    language=request.language or current_language,
                    properties={
                        key: value
                        for key, value in properties.items()
                        if key != "language"
                    },
                    reviewer=request.reviewer,
                    rationale=request.rationale,
                    source_ref=request.source_ref,
                )
            else:
                node = graph.update_node(
                    project_id,
                    properties,
                    reviewer=request.reviewer,
                    rationale=request.rationale,
                    source_ref=request.source_ref,
                )
            persist_graph()
            return {**node.model_dump(), **project_language_projection(node)}
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/outline")
    def get_project_outline(project_id: str) -> dict:
        try:
            return graph_query.project_outline(project_id=project_id)
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/characters")
    def list_characters(project_id: str) -> dict:
        try:
            return {
                "characters": graph_query.list_project_nodes(
                    project_id=project_id,
                    node_type="Character",
                )
            }
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

    @app.get("/projects/{project_id}/locations")
    def list_locations(project_id: str) -> dict:
        try:
            return {
                "locations": graph_query.list_project_nodes(
                    project_id=project_id,
                    node_type="Location",
                )
            }
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

    @app.patch("/projects/{project_id}/chapters/{chapter_id}")
    def update_chapter(
        project_id: str,
        chapter_id: str,
        request: ChapterUpdateRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            _ensure_chapter_project(graph, project_id=project_id, chapter_id=chapter_id)
            properties = _chapter_update_properties(request)
            if not properties:
                raise HTTPException(status_code=409, detail="没有可更新的章节字段。")
            node = graph.update_node(
                chapter_id,
                properties,
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
                language=resolve_project_output_language(graph, project_id),
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

    @app.post("/projects/{project_id}/sources")
    def import_source_document(
        project_id: str,
        request: SourceDocumentImportRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            _ensure_project_exists(graph, project_id)
            now = utc_now()
            document = SourceDocument(
                id=new_id("source"),
                project_id=project_id,
                title=request.title,
                relative_path=request.relative_path,
                media_type=request.media_type,
                language=request.language,
                byte_size=request.byte_size,
                checksum_sha256=request.checksum_sha256,
                extraction_status=request.extraction_status,
                extracted_text=request.extracted_text,
                character_count=len(request.extracted_text or ""),
                warnings=request.warnings,
                error=request.error,
                provenance=request.provenance,
                created_at=now,
                updated_at=now,
            )
            result = source_store.create_or_get(document)
            return {
                "document": result.document.to_summary().model_dump(),
                "created": result.created,
                "updated": result.updated,
            }
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "category": "invalid_source_document",
                    "errors": [
                        {
                            "type": error["type"],
                            "loc": error["loc"],
                            "message": error["msg"],
                        }
                        for error in exc.errors(
                            include_url=False,
                            include_context=False,
                            include_input=False,
                        )
                    ],
                },
            ) from exc
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/sources")
    def list_source_documents(
        project_id: str,
        include_archived: bool = False,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            _ensure_project_exists(graph, project_id)
            documents = source_store.list(
                project_id=project_id,
                include_archived=include_archived,
            )
            return {"sources": [document.model_dump() for document in documents]}
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/sources/{source_document_id}")
    def get_source_document(project_id: str, source_document_id: str) -> dict:
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return get_project_source(project_id, source_document_id).model_dump()
        except GraphStoreError as exc:
            raise _graph_http_exception(exc) from exc

    @app.post("/projects/{project_id}/sources/{source_document_id}/archive")
    def archive_source_document(project_id: str, source_document_id: str) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            get_project_source(project_id, source_document_id)
            archived = source_store.archive(
                project_id=project_id,
                source_id=source_document_id,
            )
            return archived.to_summary().model_dump()
        except GraphStoreError as exc:
            raise _graph_http_exception(exc) from exc
        except ContractError as exc:
            raise _contract_http_exception(exc) from exc

    @app.patch("/projects/{project_id}/sources/{source_document_id}")
    def update_source_document(
        project_id: str,
        source_document_id: str,
        request: SourceDocumentUpdateRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            get_project_source(project_id, source_document_id)
            return source_store.update_language(
                project_id=project_id,
                source_id=source_document_id,
                language=request.language,
                expected_updated_at=request.expected_updated_at,
            ).model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/sources/{source_document_id}/structure-draft")
    def create_source_project_structure_draft(
        project_id: str,
        source_document_id: str,
        request: SourceStructureDraftRequest | None = None,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        request = request or SourceStructureDraftRequest()
        try:
            document = get_project_source(project_id, source_document_id)
            if document.extraction_status != "ready" or not document.extracted_text:
                raise HTTPException(
                    status_code=409,
                    detail="只有已成功提取正文的来源文档可以生成项目结构草稿。",
                )
            return build_project_structure_draft(
                project_id=project_id,
                title=document.title,
                source_text=document.extracted_text,
                source_ref=ProposalRef(
                    kind="source_document",
                    ref=document.id,
                    note=document.title,
                ),
                max_chapters=request.max_chapters,
                max_scenes_per_chapter=request.max_scenes_per_chapter,
                source_language=document.language,
                cross_language_policy=request.cross_language_policy,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except GraphStoreError as exc:
            raise _graph_http_exception(exc) from exc
        except ContractError as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/imports/structure-draft")
    def create_project_structure_draft(
        project_id: str,
        request: ProjectStructureDraftRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            _ensure_project_exists(graph, project_id)
            output_language = resolve_project_output_language(graph, project_id)
            return build_project_structure_draft(
                project_id=project_id,
                title=request.title,
                source_text=request.text,
                source_ref=ProposalRef(
                    kind="imported_document",
                    ref=request.source_ref,
                    note=localized(
                        output_language,
                        zh=f"导入的来源资料：{request.title}",
                        en=f"Imported source document: {request.title}",
                    ),
                ),
                max_chapters=request.max_chapters,
                max_scenes_per_chapter=request.max_scenes_per_chapter,
                source_language=request.source_language,
                cross_language_policy=request.cross_language_policy,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
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
                content_language=resolve_project_output_language(graph, project_id),
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
            existing = proposal_store.get(proposal_id)
            _ensure_proposal_project(existing, project_id)
            current_language = resolve_project_output_language(graph, project_id)
            changes_natural_language = request.title is not None or request.body is not None
            if (
                existing.content_language != current_language
                and changes_natural_language
                and (request.title is None or request.body is None)
            ):
                raise ContractError(
                    "After a project language change, a Proposal content revision must "
                    "supply both title and body."
                )
            revision_language = (
                current_language
                if changes_natural_language
                else existing.content_language
            )
            proposal = proposal_store.revise(
                proposal_id,
                actor=request.actor,
                created_via=request.created_via,
                content_language=revision_language,
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
            current_language = resolve_project_output_language(graph, project_id)
            body = request.body
            title = request.title
            if body is None:
                _ensure_proposal_artifact_type(existing, "scene_draft")
                target_scene_id = _proposal_target_scene_id(existing)
                context_pack = context_builder.build(project_id=project_id, scene_id=target_scene_id)
                body = create_scene_writer(settings, draft_store).draft(context_pack).text
                current_language = context_pack.output_language
                if existing.content_language != current_language and title is None:
                    title = localized(
                        current_language,
                        zh=f"场景修订：{target_scene_id}",
                        en=f"Scene revision: {target_scene_id}",
                    )
            elif (
                existing.content_language != current_language
                and title is None
            ):
                raise ContractError(
                    "After a project language change, an explicit Proposal revision must "
                    "supply both title and body."
                )
            proposal = proposal_store.revise(
                proposal_id,
                actor=request.actor,
                created_via=request.created_via,
                content_language=current_language,
                title=title,
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
            existing = proposal_store.get(proposal_id)
            _ensure_proposal_project(existing, project_id)
            proposal = proposal_store.mark_ready(
                proposal_id,
                actor=request.actor,
                content_language=(
                    existing.content_language
                ),
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
            existing = proposal_store.get(proposal_id)
            _ensure_proposal_project(existing, project_id)
            proposal = proposal_store.review(
                proposal_id,
                decision=request.decision,
                reviewer=request.reviewer,
                content_language=(
                    existing.content_language
                ),
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
            existing = proposal_store.get(proposal_id)
            _ensure_proposal_project(existing, project_id)
            proposal = proposal_store.review(
                proposal_id,
                decision="accepted",
                reviewer=request.reviewer,
                content_language=(
                    existing.content_language
                ),
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
            existing = proposal_store.get(proposal_id)
            _ensure_proposal_project(existing, project_id)
            proposal = proposal_store.review(
                proposal_id,
                decision="rejected",
                reviewer=request.reviewer,
                content_language=(
                    existing.content_language
                ),
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
            content_language = _require_proposal_content_language(proposal)
            draft = draft_store.create_draft(
                project_id=project_id,
                scene_id=request.scene_id,
                content_language=content_language,
                text=proposal.body,
                summary=request.summary
                or localized(
                    content_language,
                    zh=f"由协作草稿 {proposal.id} v{proposal.version} 转为场景草稿。",
                    en=f"Converted collaboration proposal {proposal.id} v{proposal.version} to a scene draft.",
                ),
            )
            updated_proposal = proposal_store.record_derived_ref(
                proposal_id,
                derived_ref=ProposalRef(
                    kind="draft",
                    ref=draft.id,
                    note=localized(
                        content_language,
                        zh=f"当前场景草稿由提案 v{proposal.version} 派生。",
                        en=(
                            "Current scene draft derived from proposal "
                            f"v{proposal.version}."
                        ),
                    ),
                ),
                actor=request.actor,
                content_language=content_language,
                note=localized(
                    content_language,
                    zh="已将提案内容提升到草稿库。",
                    en="Promoted proposal content to Draft Store.",
                ),
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
            content_language = _require_proposal_content_language(proposal)
            source_draft = draft_store.get_draft(request.source_draft_id)
            if source_draft.project_id != project_id:
                raise HTTPException(status_code=404, detail="这个项目中没有找到来源草稿。")
            if source_draft.content_language != content_language:
                raise ContractError(
                    "The fact_draft and its source Draft must have the same resolved "
                    "content language before CandidateFact promotion."
                )
            candidates = _fact_draft_candidates(
                project_id=project_id,
                proposal=proposal,
                source_draft=source_draft,
                extractor=extractor,
                content_language=content_language,
            )
            candidates = [
                review.validate_candidate_scope(candidate, project_id=project_id)
                for candidate in candidates
            ]
            if not candidates:
                return {
                    "proposal": proposal.model_dump(),
                    "source_draft": source_draft.model_dump(),
                    "candidates": [],
                    "already_promoted": False,
                }
            existing = _existing_fact_draft_promotion(
                proposal=proposal,
                candidates=candidates,
                candidate_store=candidate_store,
            )
            already_promoted = existing is not None
            submitted = existing if existing is not None else review.submit(candidates)
            updated_proposal = proposal_store.record_derived_refs(
                proposal_id,
                derived_refs=[
                    ProposalRef(
                        kind="candidate_fact",
                        ref=candidate.id,
                        note=localized(
                            content_language,
                            zh="候选事实由此已接受的事实草稿提升而来。",
                            en=(
                                "CandidateFact promoted from this accepted "
                                "fact_draft."
                            ),
                        ),
                    )
                    for candidate in submitted
                ],
                actor=request.actor,
                content_language=content_language,
                note=localized(
                    content_language,
                    zh="已记录由已接受提案内容派生的候选事实。",
                    en="Recorded CandidateFacts derived from accepted proposal content.",
                ),
                expected_version=proposal.version,
            )
            return {
                "proposal": updated_proposal.model_dump(),
                "source_draft": source_draft.model_dump(),
                "candidates": [candidate.model_dump() for candidate in submitted],
                "already_promoted": already_promoted,
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="没有找到来源草稿。") from exc
        except (ContractError, GraphStoreError, ValueError) as exc:
            if isinstance(exc, ValueError):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/proposals/{proposal_id}/apply/project-structure")
    def apply_project_structure_proposal(
        project_id: str,
        proposal_id: str,
        request: ProposalApplyProjectStructureRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            proposal = proposal_store.get(proposal_id)
            _ensure_proposal_project(proposal, project_id)
            _ensure_proposal_promotable(proposal, request.expected_version)
            _ensure_proposal_artifact_type(proposal, "project_structure_draft")
            if proposal.body_format != "structured_json":
                raise HTTPException(status_code=409, detail="项目结构草稿必须使用 structured_json。")
            output_language = _require_proposal_content_language(proposal)
            outline = _project_structure_from_proposal(proposal)
            source_ref = request.source_ref or f"proposal:{proposal.id}@v{proposal.version}"
            chapters: list[dict] = []
            scenes: list[dict] = []
            previous_scene_id: str | None = None
            created_graph_nodes = False
            for chapter_index, chapter in enumerate(outline["chapters"], start=1):
                chapter_title = _structure_text(chapter.get("title")) or localized(
                    output_language,
                    zh=f"第 {chapter_index} 章",
                    en=f"Chapter {chapter_index}",
                )
                chapter_id = slug_id(
                    "chapter",
                    f"{project_id}_{chapter_index}_{chapter_title}",
                )
                chapter_node = _existing_project_structure_node(
                    graph,
                    node_id=chapter_id,
                    project_id=project_id,
                    proposal=proposal,
                    expected_type="Chapter",
                )
                if chapter_node is None:
                    chapter_node = canon_seed.add_chapter(
                        project_id=project_id,
                        node_id=chapter_id,
                        title=chapter_title,
                        properties={
                            "volume_index": 1,
                            "chapter_index": _structure_int(
                                chapter.get("chapter_index"), chapter_index
                            ),
                            "summary": _structure_text(chapter.get("summary")) or None,
                            "purpose": _structure_text(chapter.get("purpose")) or None,
                            "status": "planned",
                            "source_structure_proposal_id": proposal.id,
                            "source_structure_proposal_version": proposal.version,
                        },
                        reviewer=request.reviewer,
                        rationale=request.rationale,
                        source_ref=source_ref,
                    )
                    created_graph_nodes = True
                chapters.append(chapter_node.model_dump())
                for scene_index, scene in enumerate(chapter.get("scenes", []), start=1):
                    scene_title = _structure_text(scene.get("title")) or localized(
                        output_language,
                        zh=f"场景 {scene_index}",
                        en=f"Scene {scene_index}",
                    )
                    scene_id = slug_id(
                        "scene",
                        f"{project_id}_{chapter_index}_{scene_index}_{scene_title}",
                    )
                    scene_node = _existing_project_structure_node(
                        graph,
                        node_id=scene_id,
                        project_id=project_id,
                        proposal=proposal,
                        expected_type="Scene",
                    )
                    if scene_node is None:
                        scene_node = canon_seed.add_scene(
                            project_id=project_id,
                            chapter_id=chapter_node.id,
                            node_id=scene_id,
                            title=scene_title,
                            properties={
                                "scene_index": _structure_int(
                                    scene.get("scene_index"), scene_index
                                ),
                                "summary": _structure_text(scene.get("summary")) or None,
                                "goal": _structure_text(scene.get("goal")) or None,
                                "conflict": _structure_text(scene.get("conflict")) or None,
                                "timeline_position": _structure_text(
                                    scene.get("timeline_position")
                                ) or None,
                                "pov_character_id": None,
                                "location_id": None,
                                "pov_label": _structure_text(scene.get("pov_label")) or None,
                                "location_label": _structure_text(
                                    scene.get("location_label")
                                ) or None,
                                "status": "planned",
                                "source_structure_proposal_id": proposal.id,
                                "source_structure_proposal_version": proposal.version,
                            },
                            previous_scene_id=previous_scene_id,
                            reviewer=request.reviewer,
                            rationale=request.rationale,
                            source_ref=source_ref,
                        )
                        created_graph_nodes = True
                    previous_scene_id = scene_node.id
                    scenes.append(scene_node.model_dump())
            if created_graph_nodes:
                persist_graph()
            updated_proposal = proposal
            recorded_graph_refs = {
                ref.ref for ref in proposal.derived_refs if ref.kind == "graph_node"
            }
            for node in [*chapters, *scenes]:
                if node["id"] in recorded_graph_refs:
                    continue
                updated_proposal = proposal_store.record_derived_ref(
                    proposal_id,
                    derived_ref=ProposalRef(
                        kind="graph_node",
                        ref=node["id"],
                        note=localized(
                            output_language,
                            zh=(
                                f"{node['type']} 由项目结构提案 "
                                f"v{proposal.version} 创建。"
                            ),
                            en=(
                                f"{node['type']} created from project structure "
                                f"proposal v{proposal.version}."
                            ),
                        ),
                    ),
                    actor=request.reviewer,
                    content_language=output_language,
                    note=localized(
                        output_language,
                        zh="已将项目结构提案应用为章节与场景图谱节点。",
                        en=(
                            "Applied project structure proposal to Chapter/Scene "
                            "graph nodes."
                        ),
                    ),
                    expected_version=updated_proposal.version,
                )
                recorded_graph_refs.add(node["id"])
            return {
                "proposal": updated_proposal.model_dump(),
                "chapters": chapters,
                "scenes": scenes,
                "already_applied": not created_graph_nodes,
            }
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
        demo_graph = build_fantasy_demo_graph(locale=request.locale)
        nodes_created = 0
        nodes_updated = 0
        relationships_created = 0
        relationships_updated = 0
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
                if request.overwrite_existing:
                    try:
                        if node.type == "Project":
                            language = validate_output_language(
                                node.properties.get("language")
                            )
                            graph.update_project_language(
                                node.id,
                                expected_language=resolve_project_output_language(
                                    graph, node.id
                                ),
                                language=language,
                                properties={
                                    key: value
                                    for key, value in node.properties.items()
                                    if key != "language"
                                },
                                reviewer=request.reviewer,
                                rationale=request.rationale,
                                source_ref=request.source_ref,
                            )
                        else:
                            graph.update_node(
                                node.id,
                                node.properties,
                                reviewer=request.reviewer,
                                rationale=request.rationale,
                                source_ref=request.source_ref,
                            )
                        nodes_updated += 1
                    except GraphStoreError as update_exc:
                        raise _graph_http_exception(update_exc) from update_exc
                else:
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
                if request.overwrite_existing:
                    try:
                        graph.update_relation(
                            relation.id,
                            relation.properties,
                            reviewer=request.reviewer,
                            rationale=request.rationale,
                            source_ref=request.source_ref,
                        )
                        relationships_updated += 1
                    except GraphStoreError as update_exc:
                        raise _graph_http_exception(update_exc) from update_exc
                else:
                    relationships_skipped.append(relation.id)

        persist_graph()
        return {
            "project_id": PROJECT_ID,
            "scene_id": SCENE_ID,
            "nodes_created": nodes_created,
            "nodes_updated": nodes_updated,
            "relationships_created": relationships_created,
            "relationships_updated": relationships_updated,
            "nodes_skipped": nodes_skipped,
            "relationships_skipped": relationships_skipped,
        }

    @app.post("/demo/archive")
    def archive_demo() -> dict:
        require_permission(AgentPermissionLevel.FULL)
        if not isinstance(graph, InMemoryGraphStore):
            raise HTTPException(
                status_code=409,
                detail={
                    "category": "backend_unsupported",
                    "message": "当前 Graph backend 不支持本地归档内置演示项目。",
                },
            )
        demo_graph = build_fantasy_demo_graph(locale="zh-CN")
        now = utc_now()
        archived_nodes = 0
        archived_relationships = 0
        for relation_id in demo_graph.relationships:
            relation = graph.relationships.get(relation_id)
            if relation and relation.status == "CANON":
                graph.relationships[relation_id] = relation.model_copy(
                    update={
                        "status": "DEPRECATED",
                        "updated_at": now,
                        "reviewer": "author",
                        "reviewed_at": now,
                        "rationale": "作者从工作台移除内置演示项目。",
                        "source_ref": "demo:archive",
                    }
                )
                archived_relationships += 1
        for node_id in demo_graph.nodes:
            node = graph.nodes.get(node_id)
            if node and node.status == "CANON":
                graph.nodes[node_id] = node.model_copy(
                    update={
                        "status": "DEPRECATED",
                        "updated_at": now,
                        "reviewer": "author",
                        "reviewed_at": now,
                        "rationale": "作者从工作台移除内置演示项目。",
                        "source_ref": "demo:archive",
                    }
                )
                archived_nodes += 1
        persist_graph()
        return {
            "project_id": PROJECT_ID,
            "nodes_archived": archived_nodes,
            "relationships_archived": archived_relationships,
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

    @app.patch("/projects/{project_id}/scenes/{scene_id}")
    def update_scene(project_id: str, scene_id: str, request: SceneUpdateRequest) -> dict:
        require_permission(AgentPermissionLevel.FULL)
        try:
            graph_query.scene_node(project_id=project_id, scene_id=scene_id)
            properties = _scene_update_properties(request)
            if not properties:
                raise HTTPException(status_code=409, detail="没有可更新的场景字段。")
            canon_seed.validate_scene_references(
                project_id=project_id,
                properties=properties,
            )
            node = graph.update_node(
                scene_id,
                properties,
                reviewer=request.reviewer,
                rationale=request.rationale,
                source_ref=request.source_ref,
            )
            persist_graph()
            return node.model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/scenes/{scene_id}/context-pack")
    def build_context(project_id: str, scene_id: str) -> dict:
        try:
            return context_builder.build(project_id=project_id, scene_id=scene_id).model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.get("/projects/{project_id}/scenes/{scene_id}/draft")
    def latest_draft(project_id: str, scene_id: str) -> dict:
        try:
            graph_query.scene_node(project_id=project_id, scene_id=scene_id)
            draft = draft_store.latest_for_scene(project_id, scene_id)
            return {"draft": draft.model_dump() if draft else None}
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/scenes/{scene_id}/draft")
    def write_draft(project_id: str, scene_id: str, request: DraftRequest | None = None) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            graph_query.scene_node(project_id=project_id, scene_id=scene_id)
            if request and request.text is not None:
                output_language = resolve_project_output_language(graph, project_id)
                return draft_store.create_draft(
                    project_id=project_id,
                    scene_id=scene_id,
                    content_language=output_language,
                    text=request.text,
                    summary=request.summary,
                ).model_dump()
            context_pack = context_builder.build(project_id=project_id, scene_id=scene_id)
            return create_scene_writer(settings, draft_store).write_and_save(
                context_pack
            ).model_dump()
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

    @app.post("/projects/{project_id}/scenes/{scene_id}/agent-discussion")
    def discuss_scene_with_agent(
        project_id: str,
        scene_id: str,
        request: AgentDiscussionRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        _require_llm_configured(settings)
        try:
            graph_query.scene_node(project_id=project_id, scene_id=scene_id)
            output_language = resolve_project_output_language(graph, project_id)
            latest = (
                draft_store.latest_for_scene(project_id, scene_id)
                if request.include_latest_draft
                else None
            )
            context_pack = (
                context_builder.build(project_id=project_id, scene_id=scene_id)
                if request.include_context_pack
                else None
            )
            service = AgentDiscussionService(
                provider=create_llm_provider(settings),
                model=settings.llm_model,
            )
            selected_source_documents = resolve_discussion_source_documents(
                project_id,
                request.source_document_ids,
            )
            inline_sources = resolve_inline_discussion_sources(request.local_sources)
            result = service.discuss(
                project_id=project_id,
                scene_id=scene_id,
                instruction=request.instruction,
                mode=request.mode,
                output_language=output_language,
                cross_language_policy=request.cross_language_policy,
                selected_text=request.selected_text,
                base_text=request.base_text,
                context_pack=context_pack,
                latest_draft=latest,
                local_sources=[
                    *selected_source_documents,
                    *inline_sources,
                ],
                allow_web_search=request.allow_web_search,
                web_search_query=request.web_search_query,
            )
            now = utc_now()
            proposal = ProposalArtifact(
                id=new_id("proposal"),
                project_id=project_id,
                content_language=output_language,
                artifact_type=result.artifact_type,
                status="agent_revised",
                title=result.proposal_title,
                body=result.proposal_body,
                body_format=result.body_format,
                target_refs=result.target_refs,
                source_refs=result.source_refs,
                provenance=ProposalProvenance(
                    created_by="agent",
                    created_via="llm",
                    model_ref=settings.llm_model,
                    note=localized(
                        output_language,
                        zh=(
                            "智能体对话根据作者明确选择的上下文生成了非正典提案；"
                            f"cross_language_policy={request.cross_language_policy}。"
                        ),
                        en=(
                            "Agent discussion produced a non-canon proposal from "
                            "author-selected context; "
                            f"cross_language_policy={request.cross_language_policy}."
                        ),
                    ),
                ),
                version=1,
                created_at=now,
                updated_at=now,
            )
            stored = proposal_store.create(proposal)
            return {
                "proposal": stored.model_dump(),
                "reply": result.reply,
                "web_results": [
                    {
                        "title": item.title,
                        "url": item.url,
                        "snippet": item.snippet,
                    }
                    for item in result.web_results
                ],
                "truncated_sources": result.truncated_sources,
                "replacement_applied": result.replacement_applied,
                "output_language": output_language,
                "cross_language_policy": request.cross_language_policy,
            }
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except (ContractError, GraphStoreError) as exc:
            raise _contract_http_exception(exc) from exc

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
        output_language = resolve_project_output_language(graph, project_id)
        if draft.content_language != output_language:
            raise HTTPException(
                status_code=409,
                detail=(
                    "草稿语言快照缺失或与当前项目语言不一致；"
                    "请先由作者另存为当前项目语言的新草稿。"
                ),
            )
        candidates = extractor.extract(project_id=project_id, draft=draft)
        if request.output_target == "proposal_workspace":
            now = utc_now()
            content_language = output_language
            proposal = ProposalArtifact(
                id=new_id("proposal"),
                project_id=project_id,
                content_language=content_language,
                artifact_type="fact_draft",
                status="agent_revised",
                title=localized(
                    content_language,
                    zh=f"候选事实提案：{scene_id}",
                    en=f"Candidate fact proposal: {scene_id}",
                ),
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
                    note=localized(
                        content_language,
                        zh="状态提取已将候选事实预览写入提案库。",
                        en=(
                            "State extraction wrote CandidateFact previews to "
                            "Proposal Store."
                        ),
                    ),
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
            submitted = review.submit(candidates)
        except ContractError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"candidates": [candidate.model_dump() for candidate in submitted]}

    @app.post("/projects/{project_id}/scenes/{scene_id}/extract-document-facts")
    def extract_document_facts(
        project_id: str,
        scene_id: str,
        request: DocumentFactExtractionRequest,
    ) -> dict:
        require_permission(AgentPermissionLevel.READ_GENERATE)
        _require_llm_configured(settings)
        graph_query.scene_node(project_id=project_id, scene_id=scene_id)
        output_language = resolve_project_output_language(graph, project_id)
        try:
            enforce_source_language_policy(
                output_language=output_language,
                source_languages=[request.source_language],
                policy=request.cross_language_policy,
            )
            if request.source_language != output_language:
                raise ContractError(
                    "Cross-language document fact extraction cannot store raw source text "
                    "as a scene Draft; use a project-language source for this legacy route."
                )
        except ContractError as exc:
            raise _contract_http_exception(exc) from exc
        provisional_now = utc_now()
        source_draft = Draft(
            id=new_id("draft"),
            project_id=project_id,
            scene_id=scene_id,
            content_language=output_language,
            version=1,
            text=request.text,
            summary=localized(
                output_language,
                zh=f"导入资料源：{request.title}",
                en=f"Imported source: {request.title}",
            ),
            created_at=provisional_now,
            updated_at=provisional_now,
        )
        extractor_service = LLMDocumentFactExtractor(
            provider=create_llm_provider(settings),
            model=settings.llm_model,
            max_facts=request.max_facts,
        )
        fact_draft = extractor_service.extract(
            project_id=project_id,
            scene_id=scene_id,
            source_draft=source_draft,
            output_language=output_language,
            source_language=request.source_language,
            cross_language_policy=request.cross_language_policy,
        )
        source_draft = draft_store.create_draft(
            project_id=project_id,
            scene_id=scene_id,
            content_language=output_language,
            text=request.text,
            summary=source_draft.summary,
            draft_id=source_draft.id,
        )
        now = utc_now()
        proposal = ProposalArtifact(
            id=new_id("proposal"),
            project_id=project_id,
            content_language=output_language,
            artifact_type="fact_draft",
            status="agent_revised",
            title=localized(
                output_language,
                zh=f"资料设定提案：{request.title}",
                en=f"Source fact proposal: {request.title}",
            ),
            body=fact_draft.body,
            body_format="markdown",
            target_refs=[
                ProposalRef(kind="scene", ref=scene_id),
                ProposalRef(kind="draft", ref=source_draft.id),
            ],
            source_refs=[
                ProposalRef(kind="draft", ref=source_draft.id),
                ProposalRef(kind="import", ref=request.source_ref),
            ],
            provenance=ProposalProvenance(
                created_by="agent",
                created_via="llm",
                note=localized(
                    output_language,
                    zh=(
                        "大模型从导入资料中提取了显式候选事实标记；"
                        f"source_language={request.source_language}；"
                        f"cross_language_policy={request.cross_language_policy}；"
                        f"output_language={output_language}。"
                    ),
                    en=(
                        "LLM extracted explicit fact markers from imported source material; "
                        f"source_language={request.source_language}; "
                        f"cross_language_policy={request.cross_language_policy}; "
                        f"output_language={output_language}."
                    ),
                ),
            ),
            version=1,
            created_at=now,
            updated_at=now,
        )
        proposal = proposal_store.create(proposal)
        candidate_previews = extractor.extract_from_text(
            project_id=project_id,
            draft=source_draft,
            text=proposal.body,
            supporting_evidence=[
                EvidenceItem(
                    kind="proposal_artifact",
                    ref=proposal.id,
                    note=localized(
                        output_language,
                        zh="由导入资料生成的大模型候选事实草稿。",
                        en="LLM fact_draft generated from imported source material.",
                    ),
                )
            ],
        )
        return {
            "proposal": proposal.model_dump(),
            "source_draft": source_draft.model_dump(),
            "candidate_previews": [candidate.model_dump() for candidate in candidate_previews],
            "truncated": fact_draft.truncated,
            "source_language": request.source_language,
            "output_language": output_language,
            "cross_language_policy": request.cross_language_policy,
        }

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
        except ContractError as exc:
            raise _contract_http_exception(exc) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "category": "workflow_failed",
                    "message": f"工作流运行失败：{exc}",
                },
            ) from exc
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


def _ensure_project_exists(graph, project_id: str):
    project = graph.get_node(project_id)
    if project.type != "Project":
        raise GraphStoreError("not_found", f"Project not found: {project_id}")
    return project


def _ensure_chapter_project(graph, *, project_id: str, chapter_id: str) -> None:
    graph.get_node(project_id)
    chapter = graph.get_node(chapter_id)
    if chapter.type != "Chapter" or chapter.properties.get("project_id") != project_id:
        raise ContractError("Chapter does not belong to the requested project.")


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


def _require_proposal_content_language(
    proposal: ProposalArtifact,
) -> OutputLanguage:
    if proposal.content_language is None:
        raise ContractError(
            "Legacy ProposalArtifact language is unresolved; revise its complete title "
            "and body before review, promotion, or derivation."
        )
    return proposal.content_language


def _fact_draft_candidates(
    *,
    project_id: str,
    proposal: ProposalArtifact,
    source_draft: Draft,
    extractor: RuleBasedStateExtractor,
    content_language: OutputLanguage,
) -> list[CandidateFact]:
    proposal_evidence = EvidenceItem(
        kind="proposal_artifact",
        ref=proposal.id,
        note=localized(
            content_language,
            zh="候选事实由此已接受的事实草稿提升而来。",
            en="CandidateFact promoted from this accepted fact_draft.",
        ),
    )
    if proposal.body_format == "structured_json":
        candidates = _structured_fact_draft_candidates(
            proposal=proposal,
            source_draft=source_draft,
            proposal_evidence=proposal_evidence,
        )
        strict_spans = True
    else:
        candidates = extractor.extract_from_text(
            project_id=project_id,
            draft=source_draft,
            text=proposal.body,
            supporting_evidence=[proposal_evidence],
        )
        candidates = [
            _relocate_marker_candidate_span(candidate, source_draft=source_draft)
            for candidate in candidates
        ]
        strict_spans = False

    validated = [
        _validate_fact_draft_candidate(
            candidate,
            project_id=project_id,
            source_draft=source_draft,
            strict_span=strict_spans,
        )
        for candidate in candidates
    ]
    return _deduplicate_fact_draft_candidates(validated)


def _structured_fact_draft_candidates(
    *,
    proposal: ProposalArtifact,
    source_draft: Draft,
    proposal_evidence: EvidenceItem,
) -> list[CandidateFact]:
    try:
        payload = json.loads(proposal.body)
    except json.JSONDecodeError as exc:
        raise ContractError("Structured fact_draft body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ContractError("Structured fact_draft body must be a JSON object.")
    payload_source_draft_id = payload.get("source_draft_id")
    if payload_source_draft_id is not None and payload_source_draft_id != source_draft.id:
        raise ContractError("Structured fact_draft source_draft_id does not match the request.")
    raw_candidates = payload.get("candidate_previews")
    if not isinstance(raw_candidates, list):
        raise ContractError("Structured fact_draft requires candidate_previews array.")

    candidates: list[CandidateFact] = []
    for index, raw_candidate in enumerate(raw_candidates):
        try:
            candidate = CandidateFact.model_validate(raw_candidate)
        except ValueError as exc:
            raise ContractError(
                f"Structured fact_draft candidate_previews[{index}] is invalid: {exc}"
            ) from exc
        evidence = list(candidate.evidence)
        if not any(
            item.kind == "proposal_artifact" and item.ref == proposal.id
            for item in evidence
        ):
            evidence.append(proposal_evidence)
        candidates.append(candidate.model_copy(update={"evidence": evidence}))
    return candidates


def _relocate_marker_candidate_span(
    candidate: CandidateFact,
    *,
    source_draft: Draft,
) -> CandidateFact:
    quote = candidate.source_span.quote
    if not quote:
        raise ContractError(f"CandidateFact {candidate.id} requires a non-empty source quote.")
    start_offset = source_draft.text.find(quote)
    if start_offset < 0:
        raise ContractError(
            f"CandidateFact {candidate.id} quote was not found in source draft {source_draft.id}."
        )
    return candidate.model_copy(
        update={
            "source_span": candidate.source_span.model_copy(
                update={
                    "start_offset": start_offset,
                    "end_offset": start_offset + len(quote),
                }
            )
        }
    )


def _validate_fact_draft_candidate(
    candidate: CandidateFact,
    *,
    project_id: str,
    source_draft: Draft,
    strict_span: bool,
) -> CandidateFact:
    if not candidate.id.strip():
        raise ContractError("CandidateFact id cannot be empty.")
    if not candidate.subject_id.strip() or not candidate.relation.strip():
        raise ContractError(f"CandidateFact {candidate.id} requires subject_id and relation.")
    if candidate.project_id != project_id:
        raise ContractError(f"CandidateFact {candidate.id} belongs to another project.")
    if candidate.source_draft_id != source_draft.id:
        raise ContractError(
            f"CandidateFact {candidate.id} source_draft_id does not match {source_draft.id}."
        )
    if candidate.source_scene_id != source_draft.scene_id:
        raise ContractError(
            f"CandidateFact {candidate.id} source_scene_id does not match its source draft."
        )
    if candidate.proposed_graph_patch.source_ref != source_draft.id:
        raise ContractError(
            f"CandidateFact {candidate.id} graph patch must cite source draft {source_draft.id}."
        )
    if (
        candidate.review.status != "pending"
        or candidate.review.reviewer is not None
        or candidate.review.reviewed_at is not None
    ):
        raise ContractError(f"CandidateFact {candidate.id} must be pending before promotion.")
    if candidate.status not in {"DRAFT_FACT", "HYPOTHESIS", "CONFLICT"}:
        raise ContractError(
            f"CandidateFact {candidate.id} has invalid pre-review status {candidate.status}."
        )

    span = candidate.source_span
    if not span.quote:
        raise ContractError(f"CandidateFact {candidate.id} requires a non-empty source quote.")
    if span.start_offset >= span.end_offset or span.end_offset > len(source_draft.text):
        raise ContractError(f"CandidateFact {candidate.id} has an invalid source span.")
    source_text = source_draft.text[span.start_offset : span.end_offset]
    if source_text != span.quote:
        if strict_span and source_text.startswith(span.quote) and len(span.quote) == 200:
            candidate = candidate.model_copy(
                update={
                    "source_span": span.model_copy(
                        update={"end_offset": span.start_offset + len(span.quote)}
                    )
                }
            )
        else:
            raise ContractError(
                f"CandidateFact {candidate.id} source span does not match its quote."
            )
    return candidate


def _deduplicate_fact_draft_candidates(
    candidates: list[CandidateFact],
) -> list[CandidateFact]:
    unique: dict[str, CandidateFact] = {}
    for candidate in candidates:
        previous = unique.get(candidate.id)
        if previous is None:
            unique[candidate.id] = candidate
            continue
        if _candidate_promotion_payload(previous) != _candidate_promotion_payload(candidate):
            raise ContractError(
                f"Conflicting duplicate CandidateFact id in fact_draft: {candidate.id}"
            )
    return list(unique.values())


def _existing_fact_draft_promotion(
    *,
    proposal: ProposalArtifact,
    candidates: list[CandidateFact],
    candidate_store: CandidateStore,
) -> list[CandidateFact] | None:
    candidate_ids = {candidate.id for candidate in candidates}
    derived_ids = {
        ref.ref for ref in proposal.derived_refs if ref.kind == "candidate_fact"
    }
    unexpected_refs = derived_ids - candidate_ids
    if unexpected_refs:
        raise ContractError(
            "fact_draft derived CandidateFact refs do not match the accepted proposal body: "
            + ", ".join(sorted(unexpected_refs))
        )

    stored_by_id = {
        candidate.id: candidate
        for candidate in candidate_store.list()
        if candidate.id in candidate_ids
    }
    if derived_ids and len(stored_by_id) != len(candidate_ids):
        raise ContractError("fact_draft promotion has incomplete derived CandidateFact records.")
    if not derived_ids and not stored_by_id:
        return None
    if len(stored_by_id) != len(candidate_ids):
        raise ContractError(
            "CandidateFact id conflict would leave a partial fact_draft promotion."
        )

    ordered: list[CandidateFact] = []
    for candidate in candidates:
        stored = stored_by_id[candidate.id]
        if _candidate_promotion_payload(stored) != _candidate_promotion_payload(candidate):
            raise ContractError(f"CandidateFact id already exists with different data: {candidate.id}")
        ordered.append(stored)
    return ordered


def _candidate_promotion_payload(candidate: CandidateFact) -> dict:
    payload = candidate.model_dump()
    payload.pop("created_at", None)
    payload.pop("review", None)
    payload.pop("status", None)
    return payload


def _project_structure_from_proposal(proposal: ProposalArtifact) -> dict:
    try:
        payload = json.loads(proposal.body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=409, detail="项目结构草稿不是有效 JSON。") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=409, detail="项目结构草稿必须是 JSON object。")
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise HTTPException(status_code=409, detail="项目结构草稿缺少 chapters。")
    normalized_chapters = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        scenes = chapter.get("scenes")
        if not isinstance(scenes, list):
            scenes = []
        normalized_chapters.append({**chapter, "scenes": [scene for scene in scenes if isinstance(scene, dict)]})
    if not normalized_chapters:
        raise HTTPException(status_code=409, detail="项目结构草稿没有可应用的章节。")
    return {**payload, "chapters": normalized_chapters}


def _chapter_update_properties(request: ChapterUpdateRequest) -> dict:
    fields = ["title", "volume_index", "chapter_index", "summary", "purpose", "status"]
    properties: dict = {}
    explicitly_set = request.model_fields_set
    for field_name in fields:
        if field_name not in explicitly_set:
            continue
        value = getattr(request, field_name)
        if isinstance(value, str):
            value = value.strip() or None
        properties[field_name] = value
    title = properties.get("title")
    if title is None and "title" in properties:
        raise HTTPException(status_code=409, detail="章节标题不能为空。")
    return properties


def _scene_update_properties(request: SceneUpdateRequest) -> dict:
    scalar_fields = [
        "title",
        "scene_index",
        "pov_character_id",
        "location_id",
        "timeline_position",
        "goal",
        "conflict",
        "outcome",
        "emotional_turn",
        "previous_scene_id",
        "status",
    ]
    list_fields = ["required_characters", "must_include", "must_not_violate"]
    properties: dict = {}
    explicitly_set = request.model_fields_set
    for field_name in scalar_fields:
        if field_name not in explicitly_set:
            continue
        value = getattr(request, field_name)
        if isinstance(value, str):
            value = value.strip() or None
        properties[field_name] = value
    for field_name in list_fields:
        if field_name not in explicitly_set:
            continue
        value = getattr(request, field_name)
        properties[field_name] = [
            item.strip() for item in (value or []) if isinstance(item, str) and item.strip()
        ]
    if "style_constraints" in explicitly_set:
        properties["style_constraints"] = request.style_constraints or {}
    title = properties.get("title")
    if title is None and "title" in properties:
        raise HTTPException(status_code=409, detail="场景标题不能为空。")
    return properties


def _existing_project_structure_node(
    graph,
    *,
    node_id: str,
    project_id: str,
    proposal: ProposalArtifact,
    expected_type: str,
):
    try:
        node = graph.get_node(node_id)
    except GraphStoreError as exc:
        if exc.category == "not_found":
            return None
        raise
    if (
        node.type == expected_type
        and node.properties.get("project_id") == project_id
        and node.properties.get("source_structure_proposal_id") == proposal.id
        and _structure_source_version_matches(
            node.properties.get("source_structure_proposal_version"),
            proposal.version,
        )
    ):
        return node
    raise ContractError(
        f"{expected_type} id already exists outside this project structure proposal: {node_id}"
    )


def _structure_source_version_matches(source_version, current_version: int) -> bool:
    try:
        version = int(source_version)
    except (TypeError, ValueError):
        return False
    return 0 < version <= current_version


def _structure_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _structure_int(value, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def _llm_is_configured(settings: StoryGraphSettings) -> bool:
    return bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)


def _require_llm_configured(settings: StoryGraphSettings) -> None:
    missing = []
    if not settings.llm_base_url:
        missing.append("base URL")
    if not settings.llm_api_key:
        missing.append("API key")
    if not settings.llm_model:
        missing.append("model")
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "category": "llm_not_configured",
                "message": "LLM 功能需要先配置：" + "、".join(missing),
            },
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
