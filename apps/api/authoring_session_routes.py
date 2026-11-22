"""Author-facing, project-scoped creative collaboration and policy compilation."""
from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from storygraph.core.agent_config import AgentPermissionLevel, settings_for_task
from storygraph.core.errors import ContractError, GraphStoreError, ModelOutputError
from storygraph.models.authoring import AuthoringDraftPin, AuthoringSourcePin
from storygraph.models.authoring import AuthoringMessage, AuthoringNavigationContext
from storygraph.services.authoring_passage import AuthoringSelectedPassage, resolve_selected_passage
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.writer_visibility import WriterVisibilityRecord
from storygraph.services.authoring import (
    AuthoringService, authoring_proposal_diff, authoring_inputs_hash, workspace_hash,
)
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.graph_query import GraphQueryService
from storygraph.services.writer_routes import available_writers
from storygraph.services.llm_provider import ProviderError
from storygraph.services.project_language import resolve_project_output_language
from storygraph.services.scene_writer import LLMSceneWriter
from storygraph.services.writer_visibility import (
    resolve_writer_visibility, writer_source_context_sha256, preflight_writer_context,
)
from storygraph.services.writer_visibility_sources import validate_writer_policy_sources
from storygraph.stores.authoring_store import SQLiteAuthoringStore


class AuthoringCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    idea: str = Field(min_length=1, max_length=12000)
    source_document_ids: list[str] = Field(default_factory=list, max_length=40)
    outline_proposal_ids: list[str] = Field(default_factory=list, max_length=40)
    draft_ids: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def selected_source_limit(self):
        if len(set(self.source_document_ids)) + len(set(self.outline_proposal_ids)) > 40:
            raise ValueError("At most 40 distinct Source/outline references may be selected in total.")
        return self


class AuthoringVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)


class AuthoringTurnRequest(AuthoringVersionRequest):
    message: str = Field(min_length=1, max_length=12000)
    max_steps: int = Field(default=6, ge=1, le=8, strict=True)
    navigation_context: AuthoringNavigationContext | None = None
    collaboration_mode: Literal["collaborate", "discuss", "review"] = "collaborate"
    selected_passage: AuthoringSelectedPassage | None = None


class AuthoringDraftPinsRequest(AuthoringVersionRequest):
    draft_ids: list[str] = Field(default_factory=list, max_length=2000)


class AuthoringSourcesRequest(AuthoringVersionRequest):
    source_document_ids: list[str] = Field(default_factory=list, max_length=40)
    outline_proposal_ids: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def selected_source_limit(self):
        if len(set(self.source_document_ids)) + len(set(self.outline_proposal_ids)) > 40:
            raise ValueError("At most 40 distinct Source/outline references may be selected in total.")
        return self


class AuthoringDecisionRequest(AuthoringVersionRequest):
    decision: Literal["adopt", "reject"]


class AuthoringPreviewRequest(AuthoringVersionRequest):
    target_scene_id: str = Field(min_length=1, max_length=200)


class AuthoringCompileRequest(AuthoringPreviewRequest):
    expected_policy_version: int = Field(ge=0, strict=True)
    expected_source_context_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AuthoringReconcileRequest(AuthoringVersionRequest):
    draft_id: str = Field(min_length=1, max_length=200)
    draft_version: int = Field(ge=1, strict=True)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    card_id: str = Field(min_length=1, max_length=200)
    card_version: int = Field(ge=1, strict=True)
    max_steps: int = Field(default=6, ge=1, le=8, strict=True)


class AuthoringStructureRequest(AuthoringVersionRequest):
    card_version: int = Field(ge=1, strict=True)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=4000)


def register_authoring_session_routes(app, *, graph, settings, proposals, drafts, sources,
                                     visibility, context_builder, require_permission,
                                     require_llm, provider_factory, persist_snapshot):
    store = SQLiteAuthoringStore(proposals)
    app.state.authoring_store = store
    query = GraphQueryService(graph)
    with store._lock, store._connection:
        store._connection.execute("CREATE TABLE IF NOT EXISTS authoring_policy_bindings "
            "(project_id TEXT, scene_id TEXT, policy_version INTEGER, session_id TEXT, "
            "card_id TEXT, card_sha256 TEXT, PRIMARY KEY(project_id,scene_id,policy_version))")

    def scope(project_id):
        node = graph.get_node(project_id)
        if node.type != "Project" or node.status != "CANON":
            raise ContractError("authoring_project_unavailable")
        return resolve_project_output_language(graph, project_id)

    def source_text(project_id, pin):
        language = scope(project_id)
        if pin.kind == "source_document":
            source = sources.get(project_id=project_id, source_id=pin.id)
            if source.extraction_status != "ready" or not source.extracted_text:
                raise ContractError("authoring_source_unavailable")
            if source.language != language:
                raise ContractError("authoring_source_language_mismatch")
            return source.extracted_text
        proposal = proposals.get(pin.id, version=pin.version)
        if (proposal.project_id != project_id or proposal.artifact_type != "outline_draft"
                or proposal.content_language != language):
            raise ContractError("authoring_outline_scope")
        # Proposal versions are immutable references. An explicitly selected old
        # outline remains readable; it is not silently upgraded to the latest.
        return proposal.body

    def draft_for(project_id, pin):
        draft = drafts.get_draft(pin.draft_id)
        if draft.project_id != project_id or draft.content_language != scope(project_id):
            raise ContractError("authoring_draft_scope")
        query.scene_node(project_id=project_id, scene_id=draft.scene_id)
        return draft

    def canon_for(project_id):
        local = query._snapshot()
        nodes = sorted([n.model_dump(mode="json") for n in local.nodes.values()
                 if n.status == "CANON" and (n.id == project_id or n.properties.get("project_id") == project_id)], key=lambda n: n["id"])
        relations = sorted([r.model_dump(mode="json") for r in local.relationships.values()
                            if r.status == "CANON" and r.properties.get("project_id") == project_id], key=lambda r: r["id"])
        targets = {n["id"] for n in nodes} | {r["id"] for r in relations}
        events = [e.model_dump(mode="json") for e in local.event_log.list() if e.target in targets]
        fingerprint = content_hash(canonical_json({"nodes": nodes, "relations": relations, "events": events}))
        if len(canonical_json({"nodes": nodes, "relations": relations})) > 26000:
            return {"complete": False, "note": "Select a scene or exact source for detailed reading.",
                    "node_index": [{"id": n["id"], "type": n["type"],
                        "name": n["properties"].get("name", n["properties"].get("title", ""))}
                        for n in nodes], "fingerprint": fingerprint}
        return {"complete": True, "nodes": nodes, "relations": relations, "fingerprint": fingerprint}

    def canon_query(project_id, text, limit):
        local = query._snapshot()
        needle = text.casefold()
        nodes = sorted([n.model_dump(mode="json") for n in local.nodes.values()
            if n.status == "CANON" and (n.id == project_id or n.properties.get("project_id") == project_id)
            and (not needle or needle in canonical_json(n.model_dump(mode="json")).casefold())],
            key=lambda n: (n["id"] != text, n["id"]))
        chosen = nodes[:limit]
        owned_ids = {n.id for n in local.nodes.values() if n.status == "CANON"
                     and (n.id == project_id or n.properties.get("project_id") == project_id)}
        relations = sorted([r.model_dump(mode="json") for r in local.relationships.values()
            if r.status == "CANON" and r.properties.get("project_id") == project_id
            and r.source_id in owned_ids and r.target_id in owned_ids
            and (not needle or needle in canonical_json(r.model_dump(mode="json")).casefold())], key=lambda r: r["id"])
        result = {"query": text, "total_matches": len(nodes), "returned_count": len(chosen),
                  "complete": len(chosen) == len(nodes) and len(relations) <= limit, "nodes": chosen,
                  "relationship_matches": len(relations), "relationships": relations[:limit]}
        # A large exact entity is reported as such, never silently shortened into
        # allegedly complete canon. Narrow queries retain real properties.
        if len(canonical_json(result)) > 26000:
            result.update(nodes=[], relationships=[], returned_count=0, complete=False,
                node_index=[{"id": n["id"], "type": n["type"], "name": n["properties"].get("name", n["properties"].get("title", ""))} for n in chosen],
                note="This selection exceeds the tool view budget; query an exact node ID or a narrower set.")
        return result

    def character_for(project_id, character_id, scene_id=None, session_id=None):
        # No story-time target means no inferred canonical knowledge. Local design
        # beliefs remain available in the separate noncanon authoring workspace.
        if not scene_id:
            return {"observations": [], "beliefs": []}
        query.scene_node(project_id=project_id, scene_id=scene_id)
        try:
            node = query.get_node(project_id=project_id, node_id=character_id)
        except GraphStoreError as exc:
            if exc.category == "not_found":
                mapped = None
                with store._lock:
                    table = store._connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='authoring_structure_receipts'").fetchone()
                    if table and session_id:
                        rows = store._connection.execute("SELECT payload FROM authoring_structure_receipts WHERE project_id=? AND session_id=?", (project_id, session_id))
                        for row in rows:
                            receipt = json.loads(row[0])
                            if receipt.get("completed") and receipt.get("scene_id") == scene_id:
                                mapped = receipt.get("character_mapping", {}).get(character_id)
                if not mapped:
                    return {"observations": [], "beliefs": []}
                node = query.get_node(project_id=project_id, node_id=mapped)
                character_id = mapped
            else:
                raise
        if node.type != "Character":
            raise ContractError("authoring_character_scope")
        boundary = graph.get_character_knowledge(character_id, scene_id=scene_id,
                                                at_scene_start=True)
        def own_text(ids):
            values = []
            for ref in ids:
                fact = query.get_node(project_id=project_id, node_id=ref)
                value = fact.properties.get("content") or fact.properties.get("description")
                if isinstance(value, str):
                    values.append(value)
            return values
        # Never transport truth labels, evidence identifiers or other actor dossiers.
        # A BELIEVES_FALSELY/SUSPECTS edge identifies a topic, not a safe text
        # version of the actor's proposition. Do not expose that Secret's truth
        # as their belief. Explicit subjective text lives in reviewed design.
        return {"observations": own_text(boundary.knows), "beliefs": []}

    def impacts(project_id, scene_ids):
        local = query._snapshot()
        affected = set(scene_ids)
        while True:
            before = len(affected)
            for node in local.nodes.values():
                if (node.type == "Scene" and node.status == "CANON"
                        and node.properties.get("project_id") == project_id
                        and node.properties.get("previous_scene_id") in affected):
                    affected.add(node.id)
            if len(affected) == before:
                break
        return [{"scene_id": sid, "draft_id": draft.id, "version": draft.version,
                 "text_sha256": content_hash(draft.text), "requires_review": True}
                for sid in sorted(affected)
                if (draft := drafts.latest_for_scene(project_id, sid)) is not None]

    def navigation_for(project_id, focus):
        scope(project_id)
        chapter_id, scene_id = focus.get("chapter_id"), focus.get("scene_id")
        if chapter_id:
            chapter = query.get_node(project_id=project_id, node_id=chapter_id)
            if chapter.type != "Chapter":
                raise ContractError("authoring_navigation_chapter_scope")
        if scene_id:
            query.scene_node(project_id=project_id, scene_id=scene_id)
            if chapter_id:
                outline = query.project_outline(project_id=project_id)
                chapter = next((c for c in outline["chapters"] if c["id"] == chapter_id), None)
                if not chapter or not any(v["id"] == scene_id for v in chapter["scenes"]):
                    raise ContractError("authoring_navigation_scene_chapter_scope")

    def project_for(project_id, args):
        outline = query.project_outline(project_id=project_id)
        rows = []
        for chapter in outline["chapters"]:
            rows.append({"kind": "chapter", "id": chapter["id"], "title": chapter.get("title"), "scene_count": len(chapter["scenes"])})
            for scene in chapter["scenes"]:
                rows.append({"kind": "scene", "chapter_id": chapter["id"], "id": scene["id"], "title": scene.get("title"),
                             "draft_selected": False})
        rows = [r for r in rows if args["query"].casefold() in canonical_json(r).casefold()]
        selected = rows[args["offset"]:args["offset"] + args["limit"]]
        return {"project_id": project_id, "title": outline["title"], "entries": selected,
                **AuthoringService._page_metadata(len(rows), args["offset"], len(selected)),
                "note": "Structure metadata only. Navigation does not select saved prose or grant Writer access."}

    def reviews_for(session, args):
        artifacts = proposals.list(project_id=session.project_id)
        items = [{"kind": "proposal", "id": p.id, "version": p.version, "artifact_type": p.artifact_type, "status": p.status,
                  "summary": p.title} for p in artifacts]
        reports = getattr(app.state, "generation_review_store", None)
        # Only explicit pins permit semantic evidence which may quote saved prose.
        if reports is not None:
            for pin in session.draft_pins:
                for report in reports.list(project_id=session.project_id, target_type="draft", target_id=pin.draft_id):
                    if report.target_version != pin.version or report.target_text_sha256 != pin.text_sha256:
                        continue
                    value = report.model_dump(mode="json", exclude={"model_execution", "issues"})
                    value["freshness"] = "not_revalidated"
                    items.append({"kind": "semantic_report", **value, "issues_total": len(report.issues)})
                    for issue in report.issues:
                        items.append({"kind": "semantic_issue", "report_id": report.id, "target_id": report.target_id,
                                      "freshness": "not_revalidated", **issue.model_dump(mode="json")})
        items = [i for i in items if args["query"].casefold() in canonical_json(i).casefold()]
        selected = AuthoringService._bounded_rows([(None, i) for i in items[args["offset"]:args["offset"] + args["limit"]]])
        return {"records": [v for _, v in selected], **AuthoringService._page_metadata(len(items), args["offset"], len(selected)),
                "note": "Report issues/evidence are limited to explicitly selected exact Drafts. Missing reports are not passes. Freshness and gates remain with the existing review workflow."}

    def passage_for(project_id, scene_id, pin):
        draft = drafts.get_draft(pin.draft_id)
        if draft.content_language != scope(project_id):
            raise ContractError("authoring_draft_scope")
        query.scene_node(project_id=project_id, scene_id=scene_id)
        return resolve_selected_passage(pin, project_id, scene_id, draft)

    def service(paid=False, session_id=None):
        provider, model, execution = None, "", None
        if paid:
            runtime = settings_for_task(settings, "discussion")
            require_llm(runtime)
            provider, model = provider_factory(runtime), runtime.llm_model
            execution = runtime.model_execution
        def language_scope(project_id):
            if paid:
                require_permission(AgentPermissionLevel.READ_GENERATE)
            return scope(project_id)
        return AuthoringService(store=store, provider=provider, model=model,
            source_resolver=source_text, draft_resolver=draft_for, canon_resolver=canon_for,
            character_resolver=lambda pid, cid, sid: character_for(pid, cid, sid, session_id),
            impact_resolver=impacts, project_language_resolver=language_scope,
            canon_query_resolver=canon_query, model_execution=execution, project_resolver=project_for,
            reviews_resolver=reviews_for, navigation_validator=navigation_for, passage_resolver=passage_for,
            writer_resolver=lambda _project_id: available_writers(settings))

    def envelope(session):
        result = session.model_dump(mode="json")
        for proposal in result["proposals"]:
            if proposal["status"] == "pending":
                proposal["stale"] = (proposal["base_workspace_sha256"] != workspace_hash(session.workspace)
                    or proposal.get("inputs_sha256") != authoring_inputs_hash(session))
                try:
                    proposal["diff"] = authoring_proposal_diff(session.workspace,
                        next(p.patch for p in session.proposals if p.id == proposal["id"]))
                except ContractError:
                    proposal["diff"] = []
        return {"session": result}

    def writable_session(project_id, session_id):
        session = service().get(project_id, session_id)
        if session.content_language != scope(project_id):
            raise ContractError("authoring_project_language_changed")
        if session.turn_status == "running":
            raise ContractError("authoring_turn_running")
        return session

    def execute(project_id, permission, operation):
        require_permission(permission)
        try:
            scope(project_id)
            return operation()
        except HTTPException:
            raise
        except ProviderError as exc:
            raise HTTPException(502, detail={"category": exc.category,
                "message": "本回合已停止；请刷新查看已保存状态，系统不会继续自动调用。"}) from None
        except ModelOutputError:
            raise HTTPException(502, detail={"category": "authoring_invalid_model_output",
                "message": "智能体回复未通过结构校验，本回合已停止；先前设计已保留，请查看记录后再决定是否继续。"}) from None
        except (ContractError, GraphStoreError, KeyError) as exc:
            category = str(exc) if str(exc).startswith("authoring_") else "authoring_scope_or_version_invalid"
            raise HTTPException(409, detail={"category": category,
                "message": "资料、场景或版本需要重新核对；请刷新后再操作。"}) from None

    def binding_current(record):
        if record.get("configured_by") != "authoring":
            return True
        with store._lock:
            row = store._connection.execute("SELECT session_id,card_id,card_sha256 FROM authoring_policy_bindings "
                "WHERE project_id=? AND scene_id=? AND policy_version=?",
                (record["project_id"], record["scene_id"], record["version"])).fetchone()
            if not row:
                return False
            try:
                svc = service()
                session = svc.get(record["project_id"], row[0])
                svc._validate_pins(session)
                card = next(c for c in session.workspace.scene_cards if c.id == row[1])
                return card.status == "approved" and content_hash(canonical_json(card.model_dump(mode="json"))) == row[2]
            except (ContractError, GraphStoreError, StopIteration):
                return False
    app.state.authoring_policy_binding_current = binding_current
    def scene_enrolled(project_id, scene_id):
        with store._lock:
            return store._connection.execute(
                "SELECT 1 FROM authoring_policy_bindings WHERE project_id=? AND scene_id=? LIMIT 1",
                (project_id, scene_id)).fetchone() is not None
    app.state.authoring_scene_requires_review = scene_enrolled

    base = "/projects/{project_id}/authoring-sessions"

    @app.get(base)
    def list_sessions(project_id: str):
        return execute(project_id, AgentPermissionLevel.READ_ONLY, lambda: {"sessions": [
            s.model_dump(mode="json", include={"id", "title", "version", "turn_status", "updated_at"})
            for s in service().list(project_id)]})

    @app.post(base)
    def create_session(project_id: str, request: AuthoringCreateRequest):
        def operation():
            language = scope(project_id)
            pins = []
            for source_id in dict.fromkeys(request.source_document_ids):
                source = sources.get(project_id=project_id, source_id=source_id)
                pin = AuthoringSourcePin(kind="source_document", id=source_id,
                    sha256=content_hash(source.extracted_text or ""))
                source_text(project_id, pin)
                pins.append(pin)
            for proposal_id in dict.fromkeys(request.outline_proposal_ids):
                proposal = proposals.get(proposal_id)
                pin = AuthoringSourcePin(kind="outline", id=proposal.id, version=proposal.version,
                                        sha256=content_hash(proposal.body))
                source_text(project_id, pin)
                pins.append(pin)
            draft_pins = []
            for draft_id in dict.fromkeys(request.draft_ids):
                draft = drafts.get_draft(draft_id)
                pin = AuthoringDraftPin(scene_id=draft.scene_id, draft_id=draft.id,
                    version=draft.version, text_sha256=content_hash(draft.text))
                draft_for(project_id, pin)
                draft_pins.append(pin)
            return envelope(service().create(project_id=project_id, content_language=language,
                title=request.title, idea=request.idea, source_pins=pins, draft_pins=draft_pins))
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)

    @app.get(base + "/{session_id}")
    def get_session(project_id: str, session_id: str):
        return execute(project_id, AgentPermissionLevel.READ_ONLY,
                       lambda: envelope(service().get(project_id, session_id)))

    @app.get(base + "/{session_id}/history")
    def history(project_id: str, session_id: str, kind: Literal["messages", "proposals"] = "messages",
                query: str = "", offset: int = 0, limit: int = 40):
        return execute(project_id, AgentPermissionLevel.READ_ONLY,
            lambda: service().history(project_id, session_id, kind=kind, query=query,
                                      offset=offset, limit=limit))

    @app.get(base + "/{session_id}/proposals/{proposal_id}")
    def proposal_detail(project_id: str, session_id: str, proposal_id: str):
        return execute(project_id, AgentPermissionLevel.READ_ONLY, lambda: {
            "proposal": service().get_proposal(project_id, session_id, proposal_id).model_dump(mode="json")})

    @app.post(base + "/{session_id}/sources")
    def update_sources(project_id: str, session_id: str, request: AuthoringSourcesRequest):
        def operation():
            session = writable_session(project_id, session_id)
            if session.version != request.expected_version:
                raise ContractError("authoring_stale_version")
            pins = []
            for ident in dict.fromkeys(request.source_document_ids):
                doc = sources.get(project_id=project_id, source_id=ident)
                pin = AuthoringSourcePin(kind="source_document", id=ident,
                                        sha256=content_hash(doc.extracted_text or ""))
                source_text(project_id, pin)
                pins.append(pin)
            for ident in dict.fromkeys(request.outline_proposal_ids):
                item = proposals.get(ident)
                pin = AuthoringSourcePin(kind="outline", id=item.id, version=item.version,
                                        sha256=content_hash(item.body))
                source_text(project_id, pin)
                pins.append(pin)
            if pins == session.source_pins:
                return envelope(session)
            session.source_pins = pins
            session.workspace.scene_cards = [card.model_copy(update={"status": "proposed", "version": card.version + 1})
                                             for card in session.workspace.scene_cards]
            message = ("作者明确更新了参考资料版本。先前讨论仍保留为历史，不能当作当前资料依据；"
                       "相关场景卡需重新核对。已保存的正文引用、正式设定和正文均未改动。"
                       if session.content_language == "zh-CN" else
                       "The author explicitly updated reference versions. Earlier discussion remains historical, not current source evidence. Recheck scene cards; saved Draft references, canon and prose remain unchanged.")
            session.messages.append(AuthoringMessage(id=new_id("amsg"), role="author", content=message, created_at=utc_now()))
            return envelope(service()._save(session))
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)

    @app.post(base + "/{session_id}/draft-pins")
    def update_draft_pins(project_id: str, session_id: str, request: AuthoringDraftPinsRequest):
        def operation():
            session = writable_session(project_id, session_id)
            if session.version != request.expected_version:
                raise ContractError("authoring_stale_version")
            pins = []
            for identity in dict.fromkeys(request.draft_ids):
                draft = drafts.get_draft(identity)
                pin = AuthoringDraftPin(scene_id=draft.scene_id, draft_id=draft.id,
                    version=draft.version, text_sha256=content_hash(draft.text))
                draft_for(project_id, pin)
                pins.append(pin)
            if pins == session.draft_pins:
                return envelope(session)
            removed = {p.draft_id for p in session.draft_pins} - {p.draft_id for p in pins}
            if removed:
                cited = {r.draft_id for r in session.workspace.reader_records}
                for item in session.workspace.items:
                    cited.update(e.draft.draft_id for e in item.evidence)
                for card in session.workspace.scene_cards:
                    for entry in card.entry_knowledge + card.acquisitions:
                        cited.update(e.draft.draft_id for e in entry.evidence)
                if removed & cited:
                    raise ContractError("authoring_draft_pin_in_use")
                session.workspace.scene_cards = [
                    card.model_copy(update={"status": "proposed", "version": card.version + 1})
                    for card in session.workspace.scene_cards
                ]
            session.draft_pins = pins
            svc = service()
            svc._validate_pins(session)
            return envelope(svc._save(session))
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)

    @app.post(base + "/{session_id}/turn")
    def turn(project_id: str, session_id: str, request: AuthoringTurnRequest):
        def operation():
            writable_session(project_id, session_id)
            return envelope(service(True, session_id).turn(project_id=project_id,
                session_id=session_id, **request.model_dump()))
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)

    @app.post(base + "/{session_id}/recover")
    def recover(project_id: str, session_id: str, request: AuthoringVersionRequest):
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, lambda: envelope(
            service().recover_turn(project_id=project_id, session_id=session_id, **request.model_dump())))

    @app.post(base + "/{session_id}/proposals/{proposal_id}/decision")
    def decision(project_id: str, session_id: str, proposal_id: str, request: AuthoringDecisionRequest):
        def operation():
            writable_session(project_id, session_id)
            return envelope(service().review(project_id=project_id, session_id=session_id, proposal_id=proposal_id,
                expected_version=request.expected_version,
                decision="adopted" if request.decision == "adopt" else "rejected"))
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)

    def preview(project_id, session_id, card_id, request):
        from storygraph.services.authoring_structure import resolve_card_policy, preview_structure
        svc = service()
        session = svc._cas(project_id, session_id, request.expected_version)
        svc._validate_pins(session)
        card = next((c for c in session.workspace.scene_cards if c.id == card_id), None)
        if card is None or card.status != "approved":
            raise ContractError("authoring_card_not_approved")
        query.scene_node(project_id=project_id, scene_id=request.target_scene_id)
        plan_session = session.model_copy(deep=True)
        plan_card = next(c for c in plan_session.workspace.scene_cards if c.id == card_id)
        plan_card.scene_id = request.target_scene_id
        plan = preview_structure(graph, plan_session, card_id)
        if plan["gaps"] or plan.get("changes"):
            raise ContractError("authoring_scene_plan_review_required")
        policy = resolve_card_policy(graph, store, session, card, request.target_scene_id)
        validate_writer_policy_sources(graph, drafts, project_id, policy)
        pack = context_builder.build(project_id=project_id, scene_id=request.target_scene_id)
        source_hash = writer_source_context_sha256(pack)
        existing = visibility.get(project_id, request.target_scene_id)
        version = (existing["version"] if existing else 0) + 1
        record = WriterVisibilityRecord(project_id=project_id, scene_id=request.target_scene_id,
            version=version, spec=policy, source_context_sha256=source_hash,
            configured_by="authoring", configured_at=session.updated_at)
        pack.writer_visibility_required = True
        pack.writer_visibility = resolve_writer_visibility(pack, record,
            reader_source_resolver=drafts.get_draft, character_scope_resolver=graph.get_node)
        view = preflight_writer_context(pack)
        messages = LLMSceneWriter(provider=None, model="preview_no_call")._messages(pack)
        return session, card, {"mode": "isolated", "writer_view": view,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "source_context_sha256": source_hash, "policy": policy.model_dump(mode="json"),
            "card_id": card.id, "card_version": card.version,
            "expected_policy_version": version - 1}

    @app.post(base + "/{session_id}/cards/{card_id}/preview")
    def preview_card(project_id: str, session_id: str, card_id: str, request: AuthoringPreviewRequest):
        return execute(project_id, AgentPermissionLevel.READ_ONLY,
                       lambda: preview(project_id, session_id, card_id, request)[2])

    @app.post(base + "/{session_id}/cards/{card_id}/compile")
    def compile_card(project_id: str, session_id: str, card_id: str, request: AuthoringCompileRequest):
        def operation():
            guard = getattr(graph, "persistence_guard", None)
            with guard() if callable(guard) else nullcontext(), store._lock:
                writable_session(project_id, session_id)
                session, card, result = preview(project_id, session_id, card_id, request)
                if result["source_context_sha256"] != request.expected_source_context_sha256:
                    raise ContractError("authoring_source_stale")
                if result["expected_policy_version"] != request.expected_policy_version:
                    raise ContractError("authoring_policy_version_changed")
                if card.scene_id is None:
                    card.scene_id = request.target_scene_id
                    card.version += 1
                    session = service()._save(session)
                elif card.scene_id != request.target_scene_id:
                    raise ContractError("authoring_scene_binding_conflict")
                record = visibility.save(project_id=project_id, scene_id=request.target_scene_id,
                    expected_version=request.expected_policy_version, spec=result["policy"],
                    source_context_sha256=result["source_context_sha256"], configured_by="authoring")
                with store._connection:
                    store._connection.execute("INSERT INTO authoring_policy_bindings VALUES (?,?,?,?,?,?)",
                        (project_id, request.target_scene_id, record["version"], session.id,
                         card.id, content_hash(canonical_json(card.model_dump(mode="json")))))
                return {**envelope(session), "policy_record": record}
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)

    @app.post(base + "/{session_id}/cards/{card_id}/structure-preview")
    def structure_preview(project_id: str, session_id: str, card_id: str, request: AuthoringVersionRequest):
        from storygraph.services.authoring_structure import preview_structure
        def operation():
            svc = service()
            session = svc._cas(project_id, session_id, request.expected_version)
            svc._validate_pins(session)
            return preview_structure(graph, session, card_id)
        return execute(project_id, AgentPermissionLevel.READ_ONLY, operation)

    @app.post(base + "/{session_id}/cards/{card_id}/structure-apply")
    def structure_apply(project_id: str, session_id: str, card_id: str, request: AuthoringStructureRequest):
        from storygraph.services.authoring_structure import apply_structure
        def operation():
            svc = service()
            svc._validate_pins(writable_session(project_id, session_id))
            result = apply_structure(graph, store, project_id, session_id, card_id,
                                    persist_snapshot=persist_snapshot, **request.model_dump())
            return {**result, **envelope(result["session"])}
        return execute(project_id, AgentPermissionLevel.FULL, operation)

    @app.post(base + "/{session_id}/reconcile")
    def reconcile(project_id: str, session_id: str, request: AuthoringReconcileRequest):
        def operation():
            writable_session(project_id, session_id)
            draft = drafts.get_draft(request.draft_id)
            pin = AuthoringDraftPin(scene_id=draft.scene_id, draft_id=request.draft_id,
                                   version=request.draft_version, text_sha256=request.text_sha256)
            draft_for(project_id, pin)
            return envelope(service(True, session_id).reconcile(project_id=project_id, session_id=session_id,
                expected_version=request.expected_version, draft_pin=pin.model_dump(mode="json"),
                max_steps=request.max_steps, card_id=request.card_id, card_version=request.card_version))
        return execute(project_id, AgentPermissionLevel.READ_GENERATE, operation)
