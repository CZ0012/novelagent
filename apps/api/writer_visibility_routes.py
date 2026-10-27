"""Local writing visibility configuration and exact model-message preview; never canon writes."""
from __future__ import annotations
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from storygraph.core.agent_config import AgentPermissionLevel
from storygraph.core.errors import ContractError, GraphStoreError
from storygraph.core.time import utc_now
from storygraph.services.writer_visibility_sources import validate_writer_policy_sources
from storygraph.models.writer_visibility import WriterVisibilityPolicy, WriterVisibilityRecord
from storygraph.services.writer_visibility import writer_source_context_sha256, resolve_writer_visibility, preflight_writer_context
from storygraph.services.graph_query import GraphQueryService
from storygraph.services.scene_writer import LLMSceneWriter


class VisibilitySaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, strict=True)
    spec: WriterVisibilityPolicy | None = None
    expected_source_context_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


def register_writer_visibility_routes(app, *, graph, store, drafts, context_builder, require_permission):
    query = GraphQueryService(graph)

    def scoped(project_id, scene_id=None):
        node = graph.get_node(project_id)
        if node.type != "Project" or node.status != "CANON":
            raise ContractError("writer_visibility_project_unavailable")
        if scene_id is not None:
            query.scene_node(project_id=project_id, scene_id=scene_id)

    def fail(exc):
        if isinstance(exc, GraphStoreError) and exc.category == "not_found":
            return HTTPException(404, detail="Writing scope is unavailable.")
        return HTTPException(409, detail={"category": "writer_visibility_invalid", "message": str(exc) if isinstance(exc, ContractError) and str(exc).startswith("writer_visibility_") else "Policy scope, version or source changed; refresh and confirm the writing policy."})

    def check_spec(project_id, spec):
        validate_writer_policy_sources(graph, drafts, project_id, spec)

    def response(project_id, scene_id=None):
        scoped(project_id, scene_id)
        pack = context_builder.build(project_id=project_id, scene_id=scene_id) if scene_id else None
        return {"project_policy": store.get(project_id), "scene_policy": store.get(project_id, scene_id) if scene_id else None,
                "effective_policy": store.effective(project_id, scene_id) if scene_id else store.get(project_id),
                "source_context_sha256": writer_source_context_sha256(pack) if pack else None,
                "required": pack.writer_visibility_required if pack else bool(graph.get_node(project_id).properties.get("require_semantic_review") or graph.get_node(project_id).properties.get("longform_blueprint_id"))}

    def save(project_id, scene_id, request):
        scoped(project_id, scene_id)
        check_spec(project_id, request.spec)
        source_hash = None
        if scene_id and request.spec is not None:
            pack = context_builder.build(project_id=project_id, scene_id=scene_id)
            source_hash = writer_source_context_sha256(pack)
            if request.expected_source_context_sha256 != source_hash:
                raise ContractError("writer_visibility_source_changed")
            record = {"contract_version": "writer_visibility_v1", "project_id": project_id, "scene_id": scene_id, "version": request.expected_version + 1,
                      "spec": request.spec.model_dump(mode="json"), "source_context_sha256": source_hash, "configured_by": "author", "configured_at": utc_now()}
            resolve_writer_visibility(pack, WriterVisibilityRecord.model_validate(record), reader_source_resolver=drafts.get_draft, character_scope_resolver=graph.get_node)
        store.save(project_id=project_id, scene_id=scene_id, expected_version=request.expected_version,
                   spec=request.spec.model_dump(mode="json") if request.spec else None, source_context_sha256=source_hash)
        return response(project_id, scene_id)

    @app.get("/projects/{project_id}/writer-visibility")
    def get_project_policy(project_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return response(project_id)
        except (ContractError, GraphStoreError) as exc:
            raise fail(exc) from None

    @app.put("/projects/{project_id}/writer-visibility")
    def save_project_policy(project_id: str, request: VisibilitySaveRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            return save(project_id, None, request)
        except (ContractError, GraphStoreError) as exc:
            raise fail(exc) from None

    @app.get("/projects/{project_id}/scenes/{scene_id}/writer-visibility")
    def get_scene_policy(project_id: str, scene_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return response(project_id, scene_id)
        except (ContractError, GraphStoreError) as exc:
            raise fail(exc) from None

    @app.put("/projects/{project_id}/scenes/{scene_id}/writer-visibility")
    def save_scene_policy(project_id: str, scene_id: str, request: VisibilitySaveRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            return save(project_id, scene_id, request)
        except (ContractError, GraphStoreError) as exc:
            raise fail(exc) from None

    @app.post("/projects/{project_id}/scenes/{scene_id}/writer-visibility/preview")
    def preview_scene_policy(project_id: str, scene_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            scoped(project_id, scene_id)
            pack = context_builder.build(project_id=project_id, scene_id=scene_id)
            record = store.effective(project_id, scene_id)
            if record:
                check_spec(project_id, WriterVisibilityRecord.model_validate(record).spec)
                pack.writer_visibility_required = True
                pack.writer_visibility = resolve_writer_visibility(pack, WriterVisibilityRecord.model_validate(record), reader_source_resolver=drafts.get_draft, character_scope_resolver=graph.get_node)
            actual = preflight_writer_context(pack)
            messages = LLMSceneWriter(provider=None, model="preview_no_call")._messages(pack)
            return {"mode": "isolated" if record else "legacy_unisolated", "policy": record,
                    "source_context_sha256": writer_source_context_sha256(pack), "writer_view": actual,
                    "messages": [{"role": m.role, "content": m.content} for m in messages]}
        except (ContractError, GraphStoreError) as exc:
            raise fail(exc) from None
